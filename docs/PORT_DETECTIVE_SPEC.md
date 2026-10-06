# Port Detective — Product & Technical Specification

## 1. Executive Summary
**Port Detective** (`portdetect`) is a developer-centric diagnostics command-line interface (CLI) created to answer a universal question:
> **"Who is using my port?"**

When launching web applications, database servers, background queues, or containers, developers routinely hit `EADDRINUSE` or `bind: address already in use`. Standard utilities like `netstat`, `lsof`, and `ss` are platform-dependent, produce dense unformatted output, and fail to correlate host proxy processes (like Docker Desktop's `com.docker.backend.exe`) with the actual container responsible.

Port Detective provides instant clarity with single-command inspection, rich process attribution, Docker container unmasking, safe termination, concurrent range scanning, and structured JSON output.

---

## 2. Functional Requirements

### FR-1: Socket-Level TCP Connectivity Probing
- Perform non-blocking loopback TCP handshakes using Python's `socket.connect_ex((host, port))`.
- Classify ports as open/listening (`0`) or closed/refused (`WSAECONNREFUSED` / `ECONNREFUSED`).
- Configurable host (default: `127.0.0.1`) and socket timeout (default: `1.0s`).

### FR-2: Host Operating System Process Attribution
- Query kernel connection tables via `psutil.net_connections(kind="inet")` to identify sockets in state `LISTEN`.
- Extract the owning Process ID (PID).
- Safely inspect the process via `psutil.Process(pid)` to retrieve:
  - Process Name (e.g. `python.exe`, `node.exe`, `postgres.exe`)
  - Binding Addresses (e.g. `127.0.0.1:8080`, `0.0.0.0:8080`, `[::]:8080`)
  - Username / Domain
  - Process start time formatted as `YYYY-MM-DD HH:MM:SS`
  - Complete command line string with arguments
- Defensively handle permission exceptions (`psutil.AccessDenied`) when encountering elevated system services.

### FR-3: Docker Container Attribution & Unmasking
- When a port is owned by a virtualization backend (`com.docker.backend.exe`, `wslhost.exe`, `docker-proxy`), inspect the Docker daemon.
- Execute `docker ps --format "{{json .}}"` with a fail-safe 2.5s timeout.
- Parse published port mappings (e.g., `0.0.0.0:8080->80/tcp`).
- Extract container metadata:
  - Container ID (short hash)
  - Container Name
  - Base Image
  - Port mapping string
  - Runtime status

### FR-4: Safe Interactive Termination Engine (`--kill` / `-k`)
- **Mandatory User Confirmation**: Never terminate any process or container without explicit interactive `[y/N]` confirmation.
- **Critical Process Invariants**: Hard-coded refusal to terminate:
  - PID 0 (System Idle / Swapper)
  - PID 4 (Windows System Kernel)
  - Self PID (`os.getpid()`)
- **Graceful Escalation Strategy**:
  1. Send graceful termination request (`SIGTERM` / `proc.terminate()`).
  2. Wait up to 3.0 seconds for the process to clean up and exit.
  3. If still active, escalate to forced kill (`SIGKILL` / `proc.kill()`).
  4. Container targets are stopped via `docker stop <container>`.
- **Post-Action Verification**: Automatically probe the port again after termination and inform the user if the port is now free.

### FR-5: Flexible Port Specification & Range Parsing
- Accept single ports: `portdetect 8080`
- Accept multiple ports: `portdetect 3000 5432 8080`
- Accept comma-separated lists: `portdetect 8080,3000`
- Accept inclusive ranges: `portdetect 8000-8005`
- Accept mixed specifications: `portdetect 8080,9000-9002 5432`
- Validate 16-bit boundaries (`1 <= port <= 65535`), enforce `start <= end`, and return sorted deduplicated integers.

### FR-6: Kernel-Level System-Wide Listening Discovery (`--all` / `-a`)
- Discover all actively listening services across the machine without brute-force port probing.
- Filter `psutil.net_connections(kind="inet")` for sockets where `status == psutil.CONN_LISTEN`.
- Query Docker daemon for published ports.
- Merge, sort, and display all listening ports in under 20 milliseconds.

### FR-7: Machine-Readable Structured JSON Output (`--json`)
- Serialize diagnostic results into clean JSON adhering to the `PortReport` schema.
- Suitable for ingestion by CI pipelines, dev scripts, and automated orchestration tools.

### FR-8: High-Throughput Concurrent Range Scanning (`--workers` / `-w`)
- Parallelize multi-port inspections across a worker pool using Python's standard `concurrent.futures.ThreadPoolExecutor`.
- Default pool size: 32 workers (configurable via `-w/--workers`).
- Single-port scans bypass pool overhead.
- Deterministic result ordering matching input sort order.

### FR-9: Standards-Compliant Packaging
- Standard PEP 517 / PEP 621 `pyproject.toml` configuration.
- Exposes `portdetect` console script entry point.
- Zero non-Python dependencies (only requires `psutil>=5.9.0`).

---

## 3. Non-Functional Requirements

| Metric | Target | Verification |
| :--- | :--- | :--- |
| **Startup Latency** | $< 100\text{ ms}$ for single port probe | Measured via PowerShell `Measure-Command` |
| **Full System Scan** | $< 50\text{ ms}$ across all active ports | `portdetect --all` connection table inspection |
| **Range Scan (100 ports)** | $< 1.0\text{ s}$ across 100 ports | Multi-threaded `ThreadPoolExecutor` |
| **Test Coverage** | 100% core path coverage | 26 unit tests covering mock sockets, Docker, psutil, and invariants |
| **Portability** | Windows, Linux, macOS | Python 3.10+ standard library + psutil |
| **Binary Footprint** | Zero external binaries | Pure Python package installable via `pip` |

---

## 4. Safety Guardrails & Principles
1. **Never Kill Silently**: Port Detective acts as an informative tool first, action tool second. `--kill` requires deliberate interactive confirmation.
2. **Never Crash on Offline Daemon**: If Docker Desktop is stopped or named pipes are unavailable, fallback gracefully and report host processes without crashing.
3. **Never Crash on Permission Denied**: On Windows, services running as `NT AUTHORITY\SYSTEM` restrict command-line inspection; degrade gracefully to reporting PID and process name.
