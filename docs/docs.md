# Port Detective — Technical Documentation & Manual

> **"Who is using my port?"** — A zero-bloat, developer diagnostics CLI for Linux, macOS, and Windows.

---

## Table of Contents
1. [Overview & Product Specification](#1-overview--product-specification)
2. [CLI Reference & Usage](#2-cli-reference--usage)
3. [Architecture & System Internals](#3-architecture--system-internals)
4. [Systems & Networking Deep Dive (Phases 1–8)](#4-systems--networking-deep-dive)
5. [Development Milestones](#5-development-milestones)

---

## 1. Overview & Product Specification

### 1.1 The Core Problem
When launching local development servers, database engines, or containerized services, developers frequently encounter:
```text
Error: listen EADDRINUSE: address already in use :::8080
bind: address already in use
```
Traditional tools (`netstat`, `lsof`, `ss`) present significant friction:
- Platform-dependent syntax that differs across Windows, Linux, and macOS.
- Difficult-to-read output tables with hundreds of unrelated connections.
- Virtualization opacity: on Windows/macOS, host proxies like `com.docker.backend.exe` or `wslhost.exe` hide the real Docker container publishing the port.

**Port Detective** (`portdetect`) solves this by identifying the exact process (PID, name, command line, user) and unmasking any Docker container publishing the port in a single command.

### 1.2 Functional Capabilities
- **Socket-Level Connectivity Probing**: Loopback TCP handshake via `socket.connect_ex((host, port))`.
- **Operating System Process Attribution**: Inspects OS connection tables via `psutil` to extract PID, binary name, username, start time, and full command-line arguments.
- **Docker Container Attribution**: Queries Docker daemon via `docker ps --format "{{json .}}"` to correlate host proxy ports with container names, images, and port mappings.
- **Safe Interactive Termination (`--kill` / `-k`)**: Gracefully stops processes or Docker containers with mandatory interactive `[y/N]` confirmation.
- **Multi-Port & Range Parsing**: Inspects individual ports (`8080`), multiple ports (`3000 5432`), comma-separated lists (`8080,3000`), and inclusive ranges (`8000-8005`).
- **System-Wide Listening Discovery (`--all` / `-a`)**: Discovers all active listening ports on the host in $< 20\text{ ms}$ by querying kernel connection tables directly.
- **Machine-Readable JSON Output (`--json`)**: Emits structured JSON adhering to the `PortReport` schema for CI/CD pipelines and developer tooling.
- **High-Throughput Concurrency**: Scans port ranges in parallel using Python's standard `concurrent.futures.ThreadPoolExecutor`.

### 1.3 Safety Invariants & Guardrails
1. **No Silent Termination**: Port Detective is an informational tool first. Termination requires explicit interactive user confirmation.
2. **Protected System Invariants**: Hard-coded refusal to terminate:
   - **PID 0**: System Idle Process / Swapper
   - **PID 4**: Windows System Kernel
   - **Self PID**: Current running `portdetect` process (`os.getpid()`)
3. **Graceful Escalation**: Always sends a graceful termination signal first (`SIGTERM` / `proc.terminate()`), waits 3.0 seconds, and only escalates to force kill (`SIGKILL` / `proc.kill()`) if the process refuses to exit.
4. **Resilience**: If Docker Desktop is stopped or named pipes are unavailable, Port Detective degrades gracefully and reports host processes without crashing.

---

## 2. CLI Reference & Usage

### 2.1 Synopsis
```bash
portdetect [-h] [-a] [--json] [-k] [--host HOST] [--timeout TIMEOUT]
           [-w WORKERS] [-v] [ports ...]
```

### 2.2 Arguments & Options Reference

| Argument / Flag | Type | Default | Description |
| :--- | :--- | :---: | :--- |
| `ports` | Positional | `None` | Port numbers, comma lists, or ranges to inspect (e.g. `8080`, `8000-8005`, `3000,5432`). |
| `-a, --all` | Flag | `False` | Scan and list all actively listening ports across the host system. |
| `--json` | Flag | `False` | Output results in structured JSON format. |
| `-k, --kill` | Flag | `False` | Interactively terminate process or stop container using the port (`[y/N]` prompt). |
| `--host HOST` | Option | `127.0.0.1` | Target host address for loopback socket probe. |
| `--timeout SEC`| Option | `1.0` | Socket probe timeout in seconds. |
| `-w, --workers`| Option | `32` | Maximum concurrent worker threads for multi-port scanning. |
| `-v, --version`| Flag | — | Display installed version and exit. |
| `-h, --help` | Flag | — | Show CLI help message and exit. |

### 2.3 Exit Codes
- `0`: Success (diagnostics executed and displayed).
- `1`: Error (invalid port number, inverted range, or missing arguments).

### 2.4 JSON Output Schema
```json
[
  {
    "port": 8080,
    "status": "in_use",
    "processes": [
      {
        "pid": 16568,
        "name": "python.exe",
        "bind_addresses": ["0.0.0.0:8080", "[::]:8080"],
        "status": "LISTEN",
        "username": "NANDAVELAN\\NANDAVELAN SPS",
        "cmdline": "python -m http.server 8080",
        "created_at": "2026-10-06 13:17:46"
      }
    ],
    "docker_containers": [
      {
        "container_id": "c3a9f0e1b2d4",
        "name": "my-nginx",
        "image": "nginx:alpine",
        "port_mapping": "0.0.0.0:8080->80/tcp",
        "status": "Up 3 hours"
      }
    ]
  }
]
```

---

## 3. Architecture & System Internals

### 3.1 Component Pipeline

```text
                     +-----------------------------------+
                     |         CLI Entry Point           |
                     |     (argparse, parse_args)        |
                     +-----------------+-----------------+
                                       |
                     +-----------------v-----------------+
                     |    Target Resolution Engine       |
                     | - Explicit Port Specs (e.g. 8080) |
                     | - Range Expansion (8000-8010)     |
                     | - System Discovery (--all)        |
                     +-----------------+-----------------+
                                       |
                     +-----------------v-----------------+
                     |   Concurrent Inspection Engine    |
                     | (concurrent.futures.ThreadPool)   |
                     +-----------------+-----------------+
                                       |
          +----------------------------+----------------------------+
          |                            |                            |
+---------v---------+        +---------v---------+        +---------v---------+
|   Socket Layer    |        | OS Process Layer  |        | Container Layer   |
| (connect_ex loop) |        | (psutil tables)   |        | (docker ps json)  |
+---------+---------+        +---------+---------+        +---------+---------+
          \                            |                            /
           \                           |                           /
            +--------------------------v--------------------------+
                                       |
                     +-----------------v-----------------+
                     |     Consolidated PortReport       |
                     |   (Data Model & Serialization)    |
                     +-----------------+-----------------+
                                       |
          +----------------------------+----------------------------+
          |                                                         |
+---------v---------+                                     +---------v---------+
|   JSON Formatter  |                                     | Terminal Renderer |
| (json.dumps dict) |                                     | (Table / Detail)  |
+-------------------+                                     +---------+---------+
                                                                    |
                                                          +---------v---------+
                                                          | Safe Termination  |
                                                          |  (Interactive -k) |
                                                          +-------------------+
```

### 3.2 The 3 Diagnostic Probing Layers
1. **Socket Layer (`is_port_in_use`)**:
   - Opens an `AF_INET` / `SOCK_STREAM` socket.
   - Probes `connect_ex((host, port))`. Returns `0` if listening; non-zero (`10061` / `111`) if closed.
2. **OS Process Layer (`find_processes_on_port`)**:
   - Queries `psutil.net_connections(kind="inet")` to locate matching `laddr.port`.
   - Reads process attributes defensively to handle `psutil.AccessDenied` when encountering privileged services.
3. **Container Layer (`find_docker_containers_on_port`)**:
   - Queries `docker ps --format "{{json .}}"` with a 2.5s timeout.
   - Regex-parses published host ports (`(?:0\.0\.0\.0|127\.0\.0\.1|\[::\]):(\d+)->`) and extracts container metadata.

### 3.3 Concurrency Model
- When scanning multiple ports or ranges, `inspect_ports_concurrently()` distributes workload across a `ThreadPoolExecutor(max_workers=32)`.
- Because socket handshakes and process lookups are I/O bound, Python threads achieve high parallelism without GIL contention.
- Results collected via `as_completed()` are keyed into a dictionary by port number to preserve the original sorted order.

---

## 4. Systems & Networking Deep Dive

### Phase 1: TCP Handshakes & Socket Sockets
- **TCP 3-Way Handshake**: A client initiates communication with `SYN`. A listening server responds with `SYN-ACK`. A closed port responds with `RST` (Reset).
- **`connect_ex()` vs `connect()`**: `connect()` raises Python exceptions (`ConnectionRefusedError`), introducing overhead. `connect_ex()` returns the C-level error integer directly (`0` for success, non-zero for failure).
- **Loopback (`127.0.0.1`)**: Packets route directly through kernel memory without transmitting over physical network interfaces.

### Phase 2: Process Attribution & OS Tables
- **Process ID (PID)**: A kernel-assigned integer uniquely identifying an executing process instance.
- **Connection Tables**: The OS maintains a global socket table mapping file descriptors/handles to `(local_ip, local_port, remote_ip, remote_port, state)`.
- **Privilege Separation**: On Windows, services running as `NT AUTHORITY\SYSTEM` allow basic process identification (`proc.name()`) but reject command-line inspection (`proc.cmdline()`). Handled defensively with `try/except psutil.AccessDenied`.

### Phase 3: Signals & Safe Process Termination
- **Signals**: Asynchronous notifications sent by the OS kernel to a process:
  - `SIGTERM` (`proc.terminate()`): Request to terminate gracefully, allowing the process to flush file buffers and close database connections.
  - `SIGKILL` (`proc.kill()`): Immediate kernel-level destruction. Cannot be caught or ignored.
- **Two-Phase Escalation**: Port Detective requests graceful termination first, waits up to 3 seconds, and only escalates to forced termination if necessary.

### Phase 4: Docker Network Bridges & Host Proxies
- **Network Namespaces**: Docker containers run inside isolated network namespaces with private IP addresses (e.g. `172.17.0.2`).
- **Port Publishing (`-p 8080:80`)**: The Docker daemon binds a host proxy (`docker-proxy` on Linux, `com.docker.backend.exe` on Windows WSL2) to listen on the host and forward traffic into the container.
- **Container Unmasking**: Port Detective parses `docker ps` JSON outputs to attribute the host port to the actual container.

### Phase 5: Deterministic Unit Testing & Mocking
- **Mocking Strategy**: Systems tests must run reliably without opening real network ports or killing host processes:
  - `@patch("socket.socket")`: Injects simulated `connect_ex()` responses.
  - `@patch("psutil.net_connections")`: Injects simulated connection tables.
  - `@patch("subprocess.run")`: Injects simulated Docker CLI JSON responses.
  - `@patch("builtins.input")`: Simulates user terminal responses (`y` vs `n`).

### Phase 6: Range Parsing & System-Wide Listening Discovery
- **Syntax Tokenization**: `parse_port_specs()` normalizes diverse CLI inputs (integers, commas, hyphens) into sorted, deduplicated integer lists.
- **Kernel-Level Discovery**: Rather than probing 65,535 ports sequentially with sockets (taking $> 60\text{ s}$), `find_all_listening_ports()` queries connections in `psutil.CONN_LISTEN` state, completing in $< 20\text{ ms}$.

### Phase 7: Concurrent Multi-Threading
- **Throughput**: Thread-pool concurrency enables scanning hundreds of ports in fractions of a second.
- **Sorted Consistency**: Thread completion order is non-deterministic, but results are mapped back to an ordered array.

### Phase 8: Packaging & CLI Distribution
- **PEP 517 / PEP 621**: Configured via `pyproject.toml` with `[project.scripts] portdetect = "portdetect:main"`.
- **Zero Binary Bloat**: Standard installation via `pip install -e .` provides a native `portdetect` command across all shells.

---

## 5. Development Milestones

| Milestone | Phase | Description | Status |
| :---: | :--- | :--- | :---: |
| **01** | Phase 1 | Minimum socket check via `socket.connect_ex` | Completed |
| **02** | Phase 2 | Process attribution via `psutil` (PID, name, cmdline, user) | Completed |
| **03** | Phase 3 | Safe interactive termination (`--kill`) with signal escalation | Completed |
| **04** | Phase 4 | Docker container detection & port unmasking | Completed |
| **05** | Phase 5 | Automated unit test suite with mocking & invariants | Completed |
| **06** | Phase 6 | Multi-port ranges, `--all` system discovery, and `--json` | Completed |
| **07** | Phase 7 | Concurrent multi-threaded range scanning (`ThreadPoolExecutor`) | Completed |
| **08** | Phase 8 | Standard packaging (`pyproject.toml`) and documentation consolidation | Completed |
