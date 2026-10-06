# Port Detective - Technical Documentation & Learning Guide

## Project Overview
**Port Detective** (`portdetect`) is a developer-focused diagnostic tool that answers:
> *"Who is using my port?"*

Developers frequently encounter `EADDRINUSE` or `bind: address already in use` errors when launching local dev servers, containers, or background workers. Port Detective identifies whether a port is occupied, unmasks the exact operating system process (PID, name, full command line, user), and checks for Docker container port mappings.

### Table of Contents
- [Phase 1: Minimum Socket-Based Port Check](#phase-1-minimum-socket-based-port-check)
- [Phase 2: Process Detection & Attribution](#phase-2-process-detection--attribution)
- [Phase 3: Safe Interactive Process Termination (`--kill`)](#phase-3-safe-interactive-process-termination---kill)
- [Phase 4: Docker Container Detection & Attribution](#phase-4-docker-container-detection--attribution)
- [Phase 5: Automated Testing Suite (`unittest` & `pytest`)](#phase-5-automated-testing-suite-unittest--pytest)
- [Phase 6: Multi-Port Scanning, System-Wide Discovery (`--all`), and JSON Output (`--json`)](#phase-6-multi-port-scanning-system-wide-discovery---all-and-json-output---json)
- [Phase 7: High-Throughput Concurrent Range Scanning (`concurrent.futures`)](#phase-7-high-throughput-concurrent-range-scanning-concurrentfutures)
- [Phase 8: Modern Packaging & Cross-Platform CLI Distribution](#phase-8-modern-packaging--cross-platform-cli-distribution)

---


## Phase 1: Minimum Socket-Based Port Check

### 1. The Core Problem
Before determining *who* owns a port, the operating system must first answer: **Is anything listening on this port right now?**

### 2. Networking Fundamentals

#### Ports & The TCP Handshake
- **Port**: A 16-bit number (`1` to `65535`) identifying a communication endpoint on a host.
  - System ports: `1`–`1023` (e.g. `80`, `443`, `22`)
  - Registered ports: `1024`–`49151` (e.g. `8080`, `3000`, `5432`)
  - Dynamic / Ephemeral ports: `49152`–`65535`
- **TCP (Transmission Control Protocol)**: Connection-oriented protocol using a 3-way handshake:
  1. Client sends `SYN` (Synchronize).
  2. Server responds with `SYN-ACK` (Synchronize-Acknowledge) if listening, or `RST` (Reset) if closed.
  3. Client replies with `ACK` (Acknowledge) to establish the connection.
- **Listening State**: A process has invoked `socket()`, `bind((ip, port))`, and `listen()`. The OS kernel queues incoming connections on that port.

#### `127.0.0.1` vs `localhost`
- `127.0.0.1` is the IPv4 **loopback address**. Traffic stays entirely within the OS kernel network stack without leaving the physical network interface.
- `localhost` is a domain name that may resolve to `127.0.0.1` (IPv4) or `::1` (IPv6). Targeting `127.0.0.1` avoids DNS lookup overhead and IPv4/IPv6 resolution ambiguity.

#### Python `connect_ex()` vs `connect()`
- `socket.connect((host, port))`: Attempts connection. Raises `ConnectionRefusedError` or `TimeoutError` on failure.
- `socket.connect_ex((host, port))`: Returns C errno code directly without raising exceptions:
  - `0`: Connection succeeded (port is open and listening).
  - Non-zero (e.g., Windows `10061` / `WSAECONNREFUSED` or POSIX `111` / `ECONNREFUSED`): Port is closed or unreachable.

### 3. Architecture Diagram

```text
               +---------------------------+
               |  CLI: python portdetect   |
               |       args: <port>        |
               +-------------+-------------+
                             |
                             v
               +---------------------------+
               | socket(AF_INET,SOCK_STREAM|
               | settimeout(1.0)           |
               +-------------+-------------+
                             |
                             | connect_ex(("127.0.0.1", port))
                             v
               +---------------------------+
               | Windows TCP/IP Stack      |
               | Loopback (127.0.0.1)      |
               +-------------+-------------+
                            / \
             Return == 0   /   \  Return != 0 (e.g., 10061)
                          /     \
                         v       v
            +----------------+  +-----------------+
            |  PORT IN USE   |  |    PORT FREE    |
            |  (Listening)   |  |    (Closed)     |
            +----------------+  +-----------------+
```

### 4. Implementation Details
The minimal script [portdetect.py](file:///c:/Python/port_detect/portdetect.py):
- Uses standard library modules: `socket`, `argparse`, `sys`.
- Sets a non-blocking timeout (`1.0s`) to avoid hanging on silent firewalls.
- Validates port range (`1 <= port <= 65535`).
- Returns exit code `0` on success and `1` on invalid arguments.

---

## Phase 2: Process Detection & Attribution

### 1. The Core Problem
Knowing a port is occupied is only half the diagnosis. Developers must find out **which program is occupying it**:
- What is its Process ID (PID)?
- What is the binary name (e.g. `python.exe`, `node.exe`, `postgres.exe`)?
- What was the full command line used to launch it?
- Which user account owns it?

### 2. Operating System Concepts

#### Process ID (PID)
A PID is a unique positive integer assigned by the OS kernel to an executing process instance. Sockets created by a process are held as open file/socket handles registered in the kernel's file descriptor table.

#### OS Socket-to-PID Mapping
- **Windows**: The OS kernel maintains an Extended TCP Table (`GetExtendedTcpTable` via IP Helper API `iphlpapi.dll`). This table maps every local IP:port and connection state to the owning PID. Native tools like `netstat -ano` and `Get-NetTCPConnection` query this table.
- **Linux**: The kernel exposes `/proc/net/tcp` (and `/proc/net/tcp6`) with socket inode numbers. Tools match these inodes against `/proc/<pid>/fd/*` socket descriptors.
- **`psutil`**: A battle-tested cross-platform library that wraps these low-level OS APIs. `psutil.net_connections(kind="inet")` queries all active sockets, and `psutil.Process(pid)` retrieves process metadata.

#### Permissions & `psutil.AccessDenied`
On Windows and Linux:
- Normal (non-administrator) users can often see connection entries and PIDs.
- However, calling `proc.cmdline()`, `proc.username()`, or `proc.environ()` on elevated processes (like system services or tasks owned by other users) fails with `AccessDenied` / `PermissionError`.
- **Defensive handling**: Wrap individual property lookups in `try...except psutil.AccessDenied` so the CLI degrades gracefully and still reports PID, binary name, and binding addresses instead of crashing.

### 3. Architecture Diagram

```text
               +-----------------------------+
               |   CLI: python portdetect    |
               |        port: 8080           |
               +--------------+--------------+
                              |
              +---------------+---------------+
              |                               |
              v                               v
    +--------------------+          +--------------------+
    | is_port_in_use()   |          | find_processes()   |
    | (Socket Handshake) |          | (psutil)           |
    +---------+----------+          +---------+----------+
              |                               |
              | SYN / SYN-ACK                 | net_connections(kind="inet")
              v                               v
    +--------------------+          +--------------------+
    | Port Open Check    |          | Filter by Port     |
    +---------+----------+          | Match: laddr.port  |
              |                     +---------+----------+
              |                               |
              |                               v
              |                     +--------------------+
              |                     | psutil.Process(PID)|
              |                     | Name, Cmdline, User|
              |                     | (Handle AccessDeny)|
              |                     +---------+----------+
              \                               /
               \                             /
                v                           v
              +-------------------------------+
              |   Structured Formatted Output |
              |  - Port Status: IN USE        |
              |  - PID & Executable Name      |
              |  - Bind Address & State       |
              |  - Full Command Line & User   |
              +-------------------------------+
```

### 4. Implementation Details
In [portdetect.py](file:///c:/Python/port_detect/portdetect.py):
- `ProcessInfo` dataclass encapsulates all attributes cleanly.
- `find_processes_on_port(port)` groups bindings by PID (handling IPv4 `0.0.0.0` and IPv6 `[::]` dual-stack bindings).
- `get_process_info_by_pid(pid, ...)` uses granular `try/except` blocks around `name()`, `cmdline()`, `username()`, and `create_time()` to safeguard against `psutil.NoSuchProcess` (race conditions) and `psutil.AccessDenied` (privilege boundaries).

### 5. Verified Experiment
Running `python portdetect.py 11434` against an active local service:
```text
Port 11434 is IN USE (listening).

Found 1 process(es) associated with port 11434:

  [1] Process: ollama.exe (PID: 15132)
      Bind Address : 127.0.0.1:11434
      State        : LISTEN
      User         : NANDAVELAN\NANDAVELAN SPS
      Started      : 2026-10-05 21:00:27
      Command      : C:\Users\NANDAVELAN SPS\AppData\Local\Programs\Ollama\ollama.exe serve
```
Verification confirmed:
1. Identified the owning PID (`15132`).
2. Identified the executable (`ollama.exe`).
3. Captured the full command line arguments (`serve`).
4. Resolved the owning user account and exact start timestamp.

---

## Phase 3: Safe Interactive Process Termination (`--kill`)

### 1. The Core Problem
When a port is occupied by an orphaned worker or zombie background process, developers often need to terminate it immediately. However, an unconstrained or automated kill tool is dangerous—it can terminate critical system services, databases with uncommitted transactions, or the developer tool itself.

### 2. Operating System Concepts

#### Signals & Termination Mechanics
- **Graceful Termination (`SIGTERM` / `proc.terminate()`)**:
  - In Unix-like systems, `SIGTERM` (signal 15) politely requests a process to exit. The process can catch this signal, flush in-memory buffers to disk, close database connections, and shut down cleanly.
  - In Windows, processes do not have Unix-style signals. `proc.terminate()` issues a `TerminateProcess` Windows API call.
- **Force Kill (`SIGKILL` / `proc.kill()`)**:
  - If a process hangs in an uninterruptible state or ignores `SIGTERM`, `proc.kill()` (or `SIGKILL` signal 9) directs the OS kernel to instantly deallocate the process memory space.
- **Two-Phase Termination Strategy**:
  1. Call `proc.terminate()` and wait with a timeout (e.g., 3 seconds).
  2. If the process has not terminated when the timeout expires, escalate to `proc.kill()`.

#### Safety Guardrails
To prevent catastrophic accidental termination:
1. **Interactive Prompt**: Always require explicit user confirmation (`Kill process <pid> (<name>)? [y/N]: `) with `N` as default.
2. **Protected PIDs**: Explicitly block PID 0 (System Idle) and PID 4 (Windows System Kernel).
3. **Self-Termination Guard**: Block `os.getpid()` to prevent Port Detective from terminating itself.
4. **Post-Termination Verification**: Re-probe the port with `is_port_in_use()` to confirm that the port was actually freed.

### 3. Architecture Diagram

```text
       CLI: python portdetect 8080 --kill
                       |
                       v
       +--------------------------------+
       |   find_processes_on_port(8080) |
       +---------------+----------------+
                       |
                       v
       +--------------------------------+
       |  Display Process Information   |
       |  PID: 14320 (python.exe)       |
       +---------------+----------------+
                       |
                       v
       +--------------------------------+
       | Safety Checks:                 |
       | - PID != 0, 4 (System)         |
       | - PID != os.getpid() (Self)    |
       +---------------+----------------+
                       |
                       v
       +--------------------------------+
       | Interactive Prompt [y/N]       |
       +---------------+----------------+
             /                  \
      [No]  /                    \  [Yes]
           v                      v
     +------------+      +-------------------------------+
     | Skip / Exit|      | proc.terminate()              |
     +------------+      | wait(3.0s)                    |
                         +---------------+---------------+
                                         |
                            +------------+------------+
                            |                         |
                       Exited in 3s             TimeoutExpired
                            |                         |
                            v                         v
                   +-----------------+       +-----------------+
                   | Graceful Exit   |       | proc.kill()     |
                   | Confirmed       |       | Force Killed    |
                   +--------+--------+       +--------+--------+
                            \                         /
                             \                       /
                              v                     v
                             +-----------------------+
                             | Re-probe Port Status  |
                             | "Port 8080 is FREE"   |
                             +-----------------------+
```

### 4. Implementation Details
In [portdetect.py](file:///c:/Python/port_detect/portdetect.py):
- Added `-k` / `--kill` argument via `argparse`.
- Added `terminate_process_safely()` function implementing safety checks, interactive input, `terminate()` with 3s timeout, and fallback to `kill()`.
- Added post-termination verification loop in `main()`.

### 5. Windows PowerShell Execution & CLI Wrappers
When executing Python CLI tools on Windows PowerShell:
1. **Bare Command Resolution (`portdetect.py`)**: PowerShell does not search the current directory `.` unless prefixed with `.\` or `./` (for security).
2. **The `.\portdetect.py` Silent Output Pitfall**: `.PY` is not present in Windows `$env:PATHEXT`. Running `.\portdetect.py` invokes the Windows file association launcher (`py.exe`) via `ShellExecute`, which runs detached from PowerShell's console stdout stream, causing stdout to be silently swallowed.
3. **The Solution**:
   - Explicit invocation: `python portdetect.py <port>`
   - Native wrappers: [portdetect.cmd](file:///c:/Python/port_detect/portdetect.cmd) and [portdetect.ps1](file:///c:/Python/port_detect/portdetect.ps1) allow developers to run `.\portdetect <port>` or `portdetect <port>` directly with full standard I/O attached.

---

## Phase 4: Docker Container Detection & Attribution

### 1. The Core Problem
In modern software engineering, services frequently run inside Docker containers (PostgreSQL on 5432, Redis on 6379, microservices on 8080).
When a developer investigates who is holding port 8080 on Windows:
- Phase 2 identifies the host process: `com.docker.backend.exe` or `wslhost.exe`.
- However, knowing that the Docker daemon or WSL proxy owns the port does **not** explain which container is actually running or why.
Phase 4 unmasks the container behind the proxy: container name, container ID, image, and internal-to-external port mapping.

### 2. Systems & Docker Concepts

#### How Docker Publishes Ports (`-p host:container`)
- When running `docker run -p 8080:80 nginx`, the container has its own private network namespace and IP address inside the Docker bridge network.
- Docker configures network translation:
  - On Linux: `iptables` / `nftables` rules forward traffic arriving at the host port to the container's private IP and port.
  - On Windows (Docker Desktop): Docker runs inside a WSL2 VM. The Windows host forwards traffic through `com.docker.backend.exe` or `wslhost.exe` into the container engine.
- The published port mapping looks like: `0.0.0.0:8080->80/tcp, [::]:8080->80/tcp`.

#### Querying Docker Without Extra Dependencies
- To keep `portdetect` lightweight and compliant with zero-extra-framework rules, we query the Docker CLI directly using standard library `subprocess`:
  ```bash
  docker ps --format "{{json .}}"
  ```
- This yields structured JSON objects for all running containers, including `ID`, `Names`, `Image`, `Status`, and `Ports`.
- **Daemon Safety & Graceful Fallback**: If Docker Desktop is installed but the daemon is not running (or Docker is not installed), `subprocess.run()` catches `FileNotFoundError` or non-zero exit codes immediately with a short timeout (`2.5s`), ensuring `portdetect` never hangs or crashes.

#### Graceful Docker Shutdown vs Host Process Killing
- Killing the host process (`com.docker.backend.exe`) is destructive because it can crash the entire Docker Desktop environment.
- The correct action when `--kill` targets a Docker-published port is to invoke `docker stop <container_name>`, allowing the container to receive `SIGTERM` and shut down gracefully.

### 3. Architecture Diagram

```text
               CLI: python portdetect 8080
                            |
            +---------------+---------------+
            |                               |
            v                               v
    OS Process Query                Docker Engine Query
  (psutil.net_connections)       (docker ps --format json)
            |                               |
            v                               v
   Host PID & Binary              Match Host Port (:8080->)
 (com.docker.backend.exe)                   |
            |                               v
            |                      Container Metadata:
            |                      - Name: web-service
            |                      - Image: nginx:alpine
            |                      - Port: 0.0.0.0:8080->80/tcp
            \                               /
             \                             /
              v                           v
            +-------------------------------+
            | Combined Detective Report     |
            | 🐳 Docker: web-service        |
            | 💻 Host  : com.docker.backend |
            +-------------------------------+
```

### 4. Implementation Details
In [portdetect.py](file:///c:/Python/port_detect/portdetect.py):
- `DockerContainerInfo` dataclass models container attribution.
- `find_docker_containers_on_port(port)` executes `docker ps --format "{{json .}}"`, filters published host ports using regular expressions, and extracts container details.
- `stop_docker_container_safely(container)` interactively prompts the user before running `docker stop <container>`.

---

## Phase 5: Automated Testing Suite (`unittest` & `pytest`)

### 1. The Core Problem
Relying exclusively on manual terminal experiments (`python -m http.server`, starting/stopping Docker containers) is slow and cannot reliably test edge cases such as:
- Operating system permission denials (`psutil.AccessDenied`)
- Malformed Docker output or offline Docker daemons
- Hard-coded safety invariants (refusal to terminate PID 0, PID 4, or self)
Phase 5 introduces an isolated, deterministic automated test suite in [tests/test_portdetect.py](file:///c:/Python/port_detect/tests/test_portdetect.py).

### 2. Testing Concepts & Mocking

#### The Mocking Strategy (`unittest.mock`)
Systems code interacts directly with the OS kernel (sockets, process tables, Docker pipes). In automated testing:
- **`@patch("socket.socket")`**: Simulates TCP handshakes returning `0` (listening) or `10061` (connection refused) without opening real OS sockets.
- **`@patch("psutil.net_connections")`**: Simulates arbitrary connection tables and tests `psutil.AccessDenied` exception handling.
- **`@patch("subprocess.run")`**: Injects simulated JSON responses for `docker ps` and tests offline daemon fallback.
- **`@patch("builtins.input")`**: Simulates user terminal responses (`y`, `n`, Enter) to verify interactive confirmation gates non-interactively.

#### Dual Runner Compatibility
Tests are written using Python's standard library `unittest` framework:
- Can be executed with zero third-party packages:
  ```bash
  python -m unittest discover tests
  ```
- Also natively discoverable and runnable by `pytest`:
  ```bash
  pytest -v
  ```

### 3. Architecture Diagram

```text
                        Test Suite Entrypoint
                   (python -m unittest discover)
                                 |
                 +---------------+---------------+
                 |                               |
                 v                               v
         Unit Tests (Pure)             Mocked Integration Tests
         - Argument parsing            - Sockets: connect_ex (0 vs 10061)
         - Port bounds (1-65535)       - Process: psutil & AccessDenied
         - Safety invariant checks:    - Docker: JSON parsing & daemon offline
           PID 0, 4, Self PID          - Input prompt: 'y' vs 'n'
                 |                               |
                 +---------------+---------------+
                                 |
                                 v
                       12 / 12 Tests Passing
                        (Zero Dependencies)
```

### 4. Implementation Details
In [tests/test_portdetect.py](file:///c:/Python/port_detect/tests/test_portdetect.py):
- `TestArgParsing`: Verifies positional and optional flags (`--kill`, `--host`, `--timeout`).
- `TestSocketCheck`: Verifies socket handling with mocked `connect_ex`.
- `TestProcessDetection`: Verifies connection table parsing and `psutil.AccessDenied` resilience.
- `TestDockerDetection`: Verifies JSON parsing and daemon offline handling.
- `TestSafetyGuardrails`: Verifies hard invariants blocking PID 0, PID 4, and self PID termination.

---

## Phase 6: Multi-Port Scanning, System-Wide Discovery (`--all`), and JSON Output (`--json`)

### 1. The Core Problem
In production and development workflows, debugging network conflicts requires more than probing single isolated ports:
1. **Multi-Port & Range Checks**: Microservices, web dev stacks, and database clusters bind multiple ports (e.g., frontend on 3000, backend on 8000, Postgres on 5432, Redis on 6379). Developers need to inspect entire ranges (`8000-8010`) or comma-separated lists (`8080,3000,5432`) in a single execution.
2. **System-Wide Listening Discovery (`--all` / `-a`)**: Answering *"What is listening on my machine right now?"* without guessing port numbers beforehand.
3. **Machine-Readable Automation (`--json`)**: Devops, CI pipelines, and AI agent harnesses require machine-parseable structured output rather than ANSI terminal strings.

### 2. Networking & Systems Concepts

#### 1. Port Range & Spec Tokenization
Users provide port specifications in diverse CLI formats:
- Individual ports: `8080`
- Comma-separated: `8080,3000`
- Inclusive ranges: `8000-8005`
- Combinations: `8080,9000-9003,5432`

`parse_port_specs()` tokenizes the input, expands hyphenated ranges (`range(start, end + 1)`), validates port boundaries (`1 <= port <= 65535`), enforces `start <= end`, and deduplicates into a sorted list of integer ports.

#### 2. System-Wide Listening Port Discovery
Instead of scanning all 65,535 TCP ports with sequential `connect_ex()` handshakes (which takes several minutes), `find_all_listening_ports()` leverages the operating system's kernel connection table:
- Calls `psutil.net_connections(kind="inet")` to retrieve connections in state `psutil.CONN_LISTEN`.
- Extracts local endpoint ports (`conn.laddr.port`).
- Queries active Docker containers (`docker ps --format "{{json .}}"`) to extract published host ports.
- Merges and sorts all unique listening ports in milliseconds (`< 0.05s`).

#### 3. Structured Data Modeling (`PortReport`)
A unified dataclass `PortReport` consolidates diagnostic results for each inspected port:
- `port`: Port number (`int`).
- `in_use`: Boolean state.
- `processes`: List of `ProcessInfo` objects.
- `docker_containers`: List of `DockerContainerInfo` objects.
- `to_dict()`: Serializes into a clean dictionary ready for `json.dumps()`.

### 3. Architecture Diagram

```text
                        CLI Invocation
         (portdetect 8000-8005 | --all | --json)
                           |
             +-------------+-------------+
             |                           |
             v                           v
     Positional Specs            System Discovery (--all)
    (parse_port_specs)          (find_all_listening_ports)
             |                           |
             +-------------+-------------+
                           |
                           v
                 Target Port List [ports]
                           |
                           v  inspect_port()
           +---------------+---------------+
           |               |               |
           v               v               v
     Socket Probe    OS Processes     Docker Engine
     (connect_ex)   (psutil tables)  (docker ps json)
           \               |               /
            \              |              /
             v             v             v
            +------------------------------+
            |      List[PortReport]        |
            +--------------+---------------+
                           |
             +-------------+-------------+
             |                           |
    Flag: --json?              Flag: Multiple Ports?
             |                           |
             v                           v
     Structured JSON             Summary Table / Rich View
```

### 4. Implementation Details
In [portdetect.py](file:///c:/Python/port_detect/portdetect.py):
- `PortReport`: Consolidated dataclass with `.to_dict()` serialization.
- `parse_port_specs(specs)`: Robust parser supporting commas, ranges, bounds validation, and sorting.
- `find_all_listening_ports()`: Blazing-fast system discovery combining `psutil` connection states with Docker published ports.
- `inspect_port(port)`: Unifies socket, process, and container diagnostic queries.
- `display_multi_port_table(reports)`: Formats multiple results into a high-density tabular terminal view.
- `parse_args()`: Adds `--all`, `--json`, and accepts variable positional `ports` while retaining full backward compatibility for `args.port`.

---

## Phase 7: High-Throughput Concurrent Range Scanning (`concurrent.futures`)

### 1. The Core Problem
When inspecting large ranges (e.g. `8000-8100`), sequential socket probes across dozens of closed ports cause noticeable latency if remote hosts or filtered networks don't respond immediately with `RST`.
Sequentially checking 100 ports at 1.0s timeout could theoretically take up to 100 seconds in worst-case conditions.

### 2. Multi-Threading with `ThreadPoolExecutor`
- **I/O Bound Workload**: Socket connects and process queries are primarily network and OS kernel I/O bound. This makes Python threads (`threading` / `concurrent.futures.ThreadPoolExecutor`) ideal without being bottlenecked by the Global Interpreter Lock (GIL).
- **Worker Concurrency**: Slices multi-port workloads across up to 32 worker threads (configurable via `-w/--workers`).
- **Deterministic Port Ordering**: While threads complete asynchronously via `as_completed()`, results are mapped back to a dictionary keyed by port number and returned in original sorted order.

### 3. Implementation Details
In [portdetect.py](file:///c:/Python/port_detect/portdetect.py):
- `inspect_ports_concurrently(ports, host, timeout, max_workers)`: Dynamically spins up worker threads (`min(max_workers, len(ports))`) to probe all targets concurrently, reducing scan times from seconds to fractions of a second.
- Single-port queries (`len(ports) <= 1`) bypass thread creation overhead completely.

---

## Phase 8: Modern Packaging & Cross-Platform CLI Distribution

### 1. The Core Problem
Relying on direct script invocations (`python portdetect.py` or `.cmd` wrappers) creates developer friction. Users expect a first-class command (`portdetect 8080`) executable from any directory across PowerShell, CMD, Bash, and Zsh.

### 2. Standards-Compliant Packaging (`pyproject.toml`)
Port Detective follows modern PEP 517 / PEP 621 packaging specifications:
- **Build Backend**: `setuptools.build_meta`
- **Console Script Entrypoint**: `[project.scripts] portdetect = "portdetect:main"`
- **Dependencies**: Explicitly requires `psutil>=5.9.0`
- **Zero Global Pollution**: Enables standard local installation via `pip install -e .`

### 3. Implementation Details
- [pyproject.toml](file:///c:/Python/port_detect/pyproject.toml): Configures metadata, entry points, and dependencies.
- [README.md](file:///c:/Python/port_detect/README.md): Full user and developer guide with quick start examples and option references.
- [tests/test_portdetect.py](file:///c:/Python/port_detect/tests/test_portdetect.py): Full 26-test suite testing all core functionality, safety guardrails, and concurrent execution.






