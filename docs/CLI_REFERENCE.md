# Port Detective — CLI Command Reference

## Synopsis
```bash
portdetect [-h] [-a] [--json] [-k] [--host HOST] [--timeout TIMEOUT]
           [-w WORKERS] [-v] [ports ...]
```

---

## Positional Arguments

### `ports`
- **Type**: String(s) (zero or more positional arguments).
- **Description**: Port numbers, comma-separated lists, or inclusive ranges to inspect.
- **Accepted Syntaxes**:
  - Single integer: `8080`
  - Multiple space-separated integers: `3000 5432 8080`
  - Comma-separated: `8080,3000,5432`
  - Inclusive hyphenated range: `8000-8005` (expands to `8000, 8001, 8002, 8003, 8004, 8005`)
  - Combined syntax: `8080,8000-8002 9000`
- **Validation**:
  - Ports must be integers in the range `1` to `65535`.
  - In ranges (`start-end`), `start` must be $\le$ `end`.

---

## Options & Flags

### `-a, --all`
- **Type**: Boolean flag (default: `False`).
- **Description**: Queries the operating system connection table and Docker daemon to discover and list **all** actively listening TCP ports on the system.
- **Example**:
  ```bash
  portdetect --all
  ```

### `--json`
- **Type**: Boolean flag (default: `False`).
- **Description**: Emits complete diagnostic results as a JSON array of `PortReport` objects to standard output.
- **Example**:
  ```bash
  portdetect 8080-8082 --json
  ```

### `-k, --kill`
- **Type**: Boolean flag (default: `False`).
- **Description**: Interactively terminates host processes or stops Docker containers occupying any of the targeted ports.
- **Behavior**:
  - Never kills automatically; requires `[y/N]` confirmation.
  - Sits behind system safety invariants protecting PID 0, PID 4, and the current PID.
  - Escalates from graceful `SIGTERM` to forced `SIGKILL` after 3 seconds.
- **Example**:
  ```bash
  portdetect 8080 --kill
  ```

### `--host HOST`
- **Type**: String (default: `127.0.0.1`).
- **Description**: Target host or IP address for the socket handshake probe.
- **Example**:
  ```bash
  portdetect 8080 --host 0.0.0.0
  ```

### `--timeout TIMEOUT`
- **Type**: Float (default: `1.0`).
- **Description**: Socket connection probe timeout in seconds.
- **Example**:
  ```bash
  portdetect 8080 --timeout 0.25
  ```

### `-w, --workers WORKERS`
- **Type**: Integer (default: `32`).
- **Description**: Maximum number of concurrent worker threads used when inspecting multiple ports.
- **Example**:
  ```bash
  portdetect 8000-8100 --workers 64
  ```

### `-v, --version`
- **Type**: Flag.
- **Description**: Displays the installed version of Port Detective and exits.

### `-h, --help`
- **Type**: Flag.
- **Description**: Displays the standard CLI help message and exits.

---

## Exit Codes

| Exit Code | Meaning |
| :---: | :--- |
| `0` | Success (diagnostic report generated and printed successfully). |
| `1` | Error (invalid port number, inverted range, or invalid arguments). |

---

## JSON Output Schema

When invoked with `--json`, output adheres to:

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
