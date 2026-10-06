# Port Detective — Technical Architecture & Internals

## 1. High-Level Architecture Overview

Port Detective is structured as a layered diagnostic pipeline designed for speed, safety, and defense-in-depth against OS permission errors and missing daemon services.

```text
                     +-----------------------------------+
                     |         CLI Entry Point           |
                     |  (argparse, parse_port_specs)     |
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

---

## 2. Component Breakdown

### 2.1 Target Resolution Engine
Before performing any I/O, user arguments are parsed:
- **`parse_port_specs(specs: list[str]) -> list[int]`**:
  - Handles comma separation (`8080,3000`) and hyphenated ranges (`8000-8005`).
  - Enforces `1 <= port <= 65535` and `start <= end`.
  - Deduplicates and returns an ascending, sorted integer list.
- **`find_all_listening_ports() -> list[int]`**:
  - Queries `psutil.net_connections(kind="inet")` directly from the OS kernel.
  - Filters for connections in state `psutil.CONN_LISTEN` where `laddr.port` exists.
  - Queries the Docker daemon to capture published container ports.
  - Operates in $< 20\text{ ms}$ without probing 65,535 sockets.

### 2.2 Concurrent Inspection Engine
- **`inspect_ports_concurrently(ports, host, timeout, max_workers)`**:
  - When inspecting multiple ports, creates a `concurrent.futures.ThreadPoolExecutor` with `workers = min(max_workers, len(ports))`.
  - Submits individual `inspect_port()` tasks as asynchronous futures.
  - Collects results using `as_completed()`, maintaining a hash map keyed by port number to preserve deterministic, sorted order.
  - Single port checks bypass thread creation overhead entirely.

### 2.3 Diagnostic Probing Layers
Each port undergoes three independent checks:

1. **Socket Layer (`is_port_in_use`)**:
   - Opens an `AF_INET` / `SOCK_STREAM` socket with the specified timeout.
   - Executes `connect_ex((host, port))`.
   - Returns `True` if `0` (SYN-ACK received), `False` if error code returned (RST / connection refused).

2. **OS Process Layer (`find_processes_on_port`)**:
   - Iterates through `psutil.net_connections(kind="inet")`.
   - Identifies matching local ports (`conn.laddr.port == port`).
   - Resolves PID and instantiates `psutil.Process(pid)`.
   - Safely reads `name()`, `cmdline()`, `username()`, and `create_time()`.
   - Catches `psutil.AccessDenied`, `psutil.NoSuchProcess`, and `psutil.ZombieProcess`.

3. **Container Layer (`find_docker_containers_on_port`)**:
   - Executes `docker ps --format "{{json .}}"` with a strict 2.5s timeout.
   - Evaluates the `Ports` field using regex `(?:0\.0\.0\.0|127\.0\.0\.1|\[::\]):(\d+)->`.
   - If the host port matches, extracts container name, ID, image, and mapping string.
   - Silently catches `FileNotFoundError` (Docker not installed) and `subprocess.TimeoutExpired` (Docker daemon frozen/offline).

### 2.4 Safety & Termination Engine
- **`terminate_process_safely(proc: ProcessInfo) -> bool`**:
  - Validates hard invariants:
    - `pid == 0`: Aborts with protected system message.
    - `pid == 4`: Aborts with protected system message.
    - `pid == os.getpid()`: Aborts with self-termination guard.
  - Interactive Confirmation: Prompts `Terminate process <name> (PID <pid>)? [y/N]: `.
  - Two-Phase Signal Escalation:
    1. Calls `target.terminate()` (`SIGTERM` on POSIX, `TerminateProcess` on Windows).
    2. Waits `target.wait(timeout=3.0)`.
    3. If process remains alive, escalates to `target.kill()` (`SIGKILL`).
- **`stop_docker_container_safely(container: DockerContainerInfo) -> bool`**:
  - Prompts `Stop Docker container <name> (ID <id>)? [y/N]: `.
  - Runs `docker stop <container_id>`.

---

## 3. Data Models

```python
@dataclass
class ProcessInfo:
    pid: int | None
    name: str
    bind_addresses: list[str]
    status: str
    cmdline: str
    username: str
    created_at: str

@dataclass
class DockerContainerInfo:
    container_id: str
    name: str
    image: str
    port_mapping: str
    status: str

@dataclass
class PortReport:
    port: int
    in_use: bool
    processes: list[ProcessInfo]
    docker_containers: list[DockerContainerInfo]

    def to_dict(self) -> dict[str, Any]:
        ...
```

---

## 4. Cross-Platform Considerations

| Operating System | Process Query | Signals | Docker IPC |
| :--- | :--- | :--- | :--- |
| **Windows 10/11** | `psutil` reads Win32 MIB-II connection table via IP Helper API. | `proc.terminate()` uses `TerminateProcess`. Sockets and PIDs 0 & 4 protected. | Communicates via named pipe `\\.\pipe\docker_engine`. |
| **Linux** | `psutil` reads `/proc/net/tcp` and `/proc/net/tcp6`. | Sends standard POSIX `SIGTERM`, escalates to `SIGKILL`. | Communicates via `/var/run/docker.sock`. |
| **macOS** | `psutil` queries `sysctl` kernel MIBs. | Sends standard POSIX `SIGTERM`, escalates to `SIGKILL`. | Communicates via Unix domain socket `/var/run/docker.sock`. |
