# Port Detective (`portdetect`)

> **"Who is using my port?"** — A zero-bloat, developer diagnostics CLI for Linux, macOS, and Windows.

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-26%20passed-brightgreen.svg)]()

Developers frequently encounter `EADDRINUSE` or `bind: address already in use` when launching web servers, background workers, or Docker containers. Standard tools like `netstat` and `lsof` can be arcane or inconsistent across operating systems. 

**Port Detective** immediately unmasks whatever is occupying your port:
- Probes port status via loopback TCP handshake.
- Identifies the host process name, PID, user, status, and full command line.
- Unmasks Docker containers publishing ports through Docker Desktop / WSL2 proxies.
- Provides interactive, graceful termination (`--kill`) with built-in system safety guards.
- Supports multi-port and range scanning (`8080-8090`).
- Discovers all system-wide listening services in milliseconds (`--all`).
- Emits structured JSON (`--json`) for automation, CI/CD, and AI agents.
- Delivers blazing-fast concurrent range scanning via `concurrent.futures`.

---

## Installation

### Editable / Local Install
```bash
# Clone the repository
git clone https://github.com/NANDAVELAN/portdetect.git
cd portdetect

# Install in editable mode
pip install -e .
```

Now you can invoke `portdetect` directly from any shell (PowerShell, CMD, Bash, Zsh).

---

## Quick Start

### 1. Inspect a Single Port
```bash
portdetect 8080
```
**Output**:
```text
Port 8080 is IN USE (listening).

Found 1 host process(es) associated with port 8080:

  [1] Process   : python.exe (PID: 16568)
      Bind Addr : 0.0.0.0:8080, [::]:8080
      State     : LISTEN
      User      : NANDAVELAN\NANDAVELAN SPS
      Started   : 2026-10-06 13:17:46
      Command   : python.exe -m http.server 8080
```

### 2. Discover All Listening Ports Across the System
```bash
portdetect --all
```
**Output**:
```text
PORT     STATUS     PID        PROCESS / CONTAINER          USER                
--------------------------------------------------------------------------------
8080     IN USE     16568      python.exe                   NANDAVELAN\NANDAVEL 
11434    IN USE     15132      ollama.exe                   NANDAVELAN\NANDAVEL 
5432     IN USE     6868       postgres.exe                 [Access Denied]     
3306     IN USE     9108       mysqld.exe                   [Access Denied]     
```

### 3. Scan Port Ranges & Multiple Ports
```bash
portdetect 8080-8085
portdetect 3000 5432 8080
portdetect 8000-8005,9000
```

### 4. Machine-Readable JSON Output
```bash
portdetect 8080-8082 --json
```
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
    "docker_containers": []
  },
  {
    "port": 8081,
    "status": "free",
    "processes": [],
    "docker_containers": []
  }
]
```

### 5. Safe Interactive Termination (`--kill`)
```bash
portdetect 8080 --kill
```
Port Detective **never** terminates processes silently. It:
1. Prompts for interactive confirmation (`[y/N]`).
2. Sends a graceful termination signal first (`SIGTERM` / `proc.terminate()`).
3. Waits up to 3 seconds for clean exit before escalating to force kill (`proc.kill()`).
4. Re-checks the socket to verify the port is free.
5. Protects critical system processes: **PID 0**, **PID 4** (Windows System), and **self PID** cannot be terminated.

---

## CLI Options Reference

```text
usage: portdetect [-h] [-a] [--json] [-k] [--host HOST] [--timeout TIMEOUT]
                  [-w WORKERS] [-v] [ports ...]

Port Detective - Discover and manage processes and Docker containers using network ports.

positional arguments:
  ports                 Port number(s) or range(s) to inspect (e.g. 8080, 8000-8005, 3000,5432)

options:
  -h, --help            Show this help message and exit
  -a, --all             Scan and list all actively listening ports on the host system
  --json                Output results in JSON format
  -k, --kill            Interactively terminate process or stop container using the port
  --host HOST           Host address for loopback socket probe (default: 127.0.0.1)
  --timeout TIMEOUT     Socket timeout in seconds (default: 1.0)
  -w, --workers WORKERS Maximum concurrent worker threads for multi-port scanning (default: 32)
  -v, --version         Show program version and exit
```

---

## Architecture

```text
                        CLI Invocation
              (portdetect 8000-8005 | --all | --json | -k)
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
                                     v  inspect_ports_concurrently()
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

---

## Running Automated Tests

Port Detective comes with a 26-test unit test suite covering argument parsing, mock socket handshakes, process attribution, Docker parsing, offline daemon fallbacks, safety invariants, and concurrent thread-pool execution.

```bash
python -m unittest discover tests
```
or with `pytest`:
```bash
pytest -v
```

---

## Documentation

The complete technical manual, systems deep dive, and CLI reference are available in:
- **[docs/docs.md](docs/docs.md)**: Product specification, CLI options, internal architecture, cross-platform details, and the complete step-by-step learning guide (Phases 1–8).

