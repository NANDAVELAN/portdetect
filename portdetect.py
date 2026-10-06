"""Port Detective - Developer diagnostic tool answering 'Who is using my port?'"""

import argparse
import concurrent.futures
import datetime
from dataclasses import dataclass
import json
import os
import re
import socket
import subprocess
import sys
from typing import Any

import psutil

__version__ = "1.0.0"



@dataclass
class ProcessInfo:
    """Information about a process holding a network port."""

    pid: int | None
    name: str
    bind_addresses: list[str]
    status: str
    cmdline: str
    username: str
    created_at: str


@dataclass
class DockerContainerInfo:
    """Information about a Docker container publishing a network port."""

    container_id: str
    name: str
    image: str
    port_mapping: str
    status: str


@dataclass
class PortReport:
    """Consolidated diagnostic report for a single network port."""

    port: int
    in_use: bool
    processes: list[ProcessInfo]
    docker_containers: list[DockerContainerInfo]

    def to_dict(self) -> dict[str, Any]:
        """Convert report to JSON-serializable dictionary."""
        return {
            "port": self.port,
            "status": "in_use" if self.in_use else "free",
            "processes": [
                {
                    "pid": p.pid,
                    "name": p.name,
                    "bind_addresses": p.bind_addresses,
                    "status": p.status,
                    "username": p.username,
                    "cmdline": p.cmdline,
                    "created_at": p.created_at,
                }
                for p in self.processes
            ],
            "docker_containers": [
                {
                    "container_id": c.container_id,
                    "name": c.name,
                    "image": c.image,
                    "port_mapping": c.port_mapping,
                    "status": c.status,
                }
                for c in self.docker_containers
            ],
        }


def is_port_in_use(port: int, host: str = "127.0.0.1", timeout: float = 1.0) -> bool:
    """Check if a TCP port is in use via loopback connection attempt."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        return result == 0


def get_process_info_by_pid(
    pid: int | None,
    bind_addresses: list[str],
    status: str,
) -> ProcessInfo:
    """Safely inspect a process by PID, handling permission and lifecycle errors."""
    if pid is None:
        return ProcessInfo(
            pid=None,
            name="[Unknown - System/Kernel]",
            bind_addresses=bind_addresses,
            status=status,
            cmdline="N/A",
            username="N/A",
            created_at="N/A",
        )

    try:
        proc = psutil.Process(pid)
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        return ProcessInfo(
            pid=pid,
            name="[Process terminated]",
            bind_addresses=bind_addresses,
            status=status,
            cmdline="N/A",
            username="N/A",
            created_at="N/A",
        )
    except psutil.AccessDenied:
        return ProcessInfo(
            pid=pid,
            name="[Access Denied]",
            bind_addresses=bind_addresses,
            status=status,
            cmdline="[Access Denied - run as Administrator]",
            username="[Access Denied]",
            created_at="N/A",
        )

    # Resolve name
    try:
        name = proc.name()
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        name = "[Access Denied]"

    # Resolve cmdline
    try:
        raw_cmd = proc.cmdline()
        cmdline = " ".join(raw_cmd) if raw_cmd else "[Empty or inaccessible]"
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        cmdline = "[Access Denied - run as Administrator]"

    # Resolve username
    try:
        username = proc.username()
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        username = "[Access Denied]"

    # Resolve creation time
    try:
        created_at = datetime.datetime.fromtimestamp(proc.create_time()).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
        created_at = "N/A"

    return ProcessInfo(
        pid=pid,
        name=name,
        bind_addresses=bind_addresses,
        status=status,
        cmdline=cmdline,
        username=username,
        created_at=created_at,
    )


def find_processes_on_port(port: int) -> list[ProcessInfo]:
    """Find all processes listening on or connected to the specified port."""
    connections_by_pid: dict[int | None, dict[str, Any]] = {}

    try:
        all_conns = psutil.net_connections(kind="inet")
    except psutil.AccessDenied:
        return []

    for conn in all_conns:
        if conn.laddr and conn.laddr.port == port:
            ip_str = conn.laddr.ip
            bind_str = (
                f"[{ip_str}]:{conn.laddr.port}"
                if ":" in ip_str
                else f"{ip_str}:{conn.laddr.port}"
            )

            pid = conn.pid
            if pid not in connections_by_pid:
                connections_by_pid[pid] = {
                    "addresses": [bind_str],
                    "status": conn.status,
                }
            else:
                if bind_str not in connections_by_pid[pid]["addresses"]:
                    connections_by_pid[pid]["addresses"].append(bind_str)

    results: list[ProcessInfo] = []
    for pid, conn_data in connections_by_pid.items():
        results.append(
            get_process_info_by_pid(
                pid=pid,
                bind_addresses=conn_data["addresses"],
                status=conn_data["status"],
            )
        )

    return results


def find_docker_containers_on_port(port: int) -> list[DockerContainerInfo]:
    """Inspect running Docker containers to find any publishing the given host port."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{json .}}"],
            capture_output=True,
            text=True,
            timeout=2.5,
            check=False,
        )
        if result.returncode != 0:
            return []
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []

    containers: list[DockerContainerInfo] = []
    # Pattern matching port mappings like ":8080->" or "0.0.0.0:8080->"
    port_pattern = re.compile(rf"(?:0\.0\.0\.0|127\.0\.0\.1|::|\[::\])?:{port}->")

    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            ports_str = data.get("Ports", "")
            if port_pattern.search(ports_str) or f":{port}->" in ports_str:
                raw_id = data.get("ID", "N/A")
                short_id = raw_id[:12] if len(raw_id) > 12 else raw_id
                containers.append(
                    DockerContainerInfo(
                        container_id=short_id,
                        name=data.get("Names", "N/A"),
                        image=data.get("Image", "N/A"),
                        port_mapping=ports_str,
                        status=data.get("Status", "N/A"),
                    )
                )
        except json.JSONDecodeError:
            continue

    return containers


def terminate_process_safely(proc_info: ProcessInfo) -> bool:
    """Prompt the user and safely terminate a process holding a port."""
    if proc_info.pid is None:
        print(f"Cannot terminate process: PID is unknown for {proc_info.name}.")
        return False

    current_pid = os.getpid()
    if proc_info.pid == current_pid:
        print("Safety check: Cannot terminate Port Detective itself.")
        return False

    # Prevent terminating critical OS system PIDs
    if proc_info.pid in (0, 4):
        print(f"Safety check: Refusing to terminate protected system process (PID {proc_info.pid}).")
        return False

    prompt = f"Kill process {proc_info.pid} ({proc_info.name})? [y/N]: "
    try:
        response = input(prompt).strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\nOperation cancelled.")
        return False

    if response not in ("y", "yes"):
        print(f"Skipped PID {proc_info.pid}.")
        return False

    try:
        proc = psutil.Process(proc_info.pid)
        proc.terminate()
        try:
            proc.wait(timeout=3.0)
            print(f"Successfully terminated PID {proc_info.pid} ({proc_info.name}).")
            return True
        except psutil.TimeoutExpired:
            print(f"Process {proc_info.pid} did not exit after 3s. Force killing...")
            proc.kill()
            proc.wait(timeout=2.0)
            print(f"Force killed PID {proc_info.pid}.")
            return True
    except psutil.NoSuchProcess:
        print(f"Process {proc_info.pid} has already exited.")
        return True
    except psutil.AccessDenied:
        print(
            f"Permission denied to terminate PID {proc_info.pid} ({proc_info.name}).\n"
            f"Try running PowerShell as Administrator."
        )
        return False


def stop_docker_container_safely(container: DockerContainerInfo) -> bool:
    """Prompt the user and gracefully stop a Docker container publishing the port."""
    prompt = f"Stop Docker container '{container.name}' ({container.image})? [y/N]: "
    try:
        response = input(prompt).strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\nOperation cancelled.")
        return False

    if response not in ("y", "yes"):
        print(f"Skipped Docker container '{container.name}'.")
        return False

    try:
        result = subprocess.run(
            ["docker", "stop", container.name],
            capture_output=True,
            text=True,
            timeout=15.0,
            check=False,
        )
        if result.returncode == 0:
            print(f"Successfully stopped Docker container '{container.name}'.")
            return True
        else:
            print(f"Failed to stop container: {result.stderr.strip()}")
            return False
    except Exception as exc:
        print(f"Error stopping Docker container: {exc}")
        return False


def parse_port_specs(specs: list[str]) -> list[int]:
    """Parse port specifications (individual, comma-separated, or ranges) into sorted unique ports.

    Examples:
        ["8080"] -> [8080]
        ["8080,3000"] -> [3000, 8080]
        ["8000-8003"] -> [8000, 8001, 8002, 8003]
        ["8080", "9000-9002", "5432"] -> [5432, 8080, 9000, 9001, 9002]
    """
    ports: set[int] = set()
    for spec in specs:
        for part in spec.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                tokens = part.split("-")
                if len(tokens) != 2:
                    raise ValueError(f"Invalid port range format: '{part}'")
                try:
                    start, end = int(tokens[0]), int(tokens[1])
                except ValueError:
                    raise ValueError(f"Port range endpoints must be integers: '{part}'")
                if start > end:
                    raise ValueError(f"Start port ({start}) cannot exceed end port ({end}) in range '{part}'")
                if not (1 <= start <= 65535 and 1 <= end <= 65535):
                    raise ValueError(f"Ports in range '{part}' must be between 1 and 65535")
                for p in range(start, end + 1):
                    ports.add(p)
            else:
                try:
                    p = int(part)
                except ValueError:
                    raise ValueError(f"Invalid port number: '{part}'")
                if not (1 <= p <= 65535):
                    raise ValueError(f"Port number {p} must be between 1 and 65535")
                ports.add(p)
    return sorted(ports)


def find_all_listening_ports() -> list[int]:
    """Discover all unique TCP ports currently listening on the host system."""
    listening_ports: set[int] = set()

    # 1. Discover via psutil system connection table
    try:
        connections = psutil.net_connections(kind="inet")
        for conn in connections:
            if conn.status == psutil.CONN_LISTEN and conn.laddr:
                listening_ports.add(conn.laddr.port)
    except (psutil.AccessDenied, PermissionError):
        pass

    # 2. Discover via published Docker host ports
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{json .}}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2.5,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                if not line.strip():
                    continue
                try:
                    container = json.loads(line)
                    ports_str = container.get("Ports", "")
                    for match in re.finditer(r"(?:0\.0\.0\.0|127\.0\.0\.1|\[::\]):(\d+)->", ports_str):
                        listening_ports.add(int(match.group(1)))
                except json.JSONDecodeError:
                    continue
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return sorted(listening_ports)


def inspect_port(port: int, host: str = "127.0.0.1", timeout: float = 1.0) -> PortReport:
    """Perform diagnostic investigation on a single network port."""
    processes = find_processes_on_port(port)
    docker_containers = find_docker_containers_on_port(port)
    socket_open = is_port_in_use(port, host=host, timeout=timeout)
    in_use = bool(processes or docker_containers or socket_open)
    return PortReport(
        port=port,
        in_use=in_use,
        processes=processes,
        docker_containers=docker_containers,
    )


def inspect_ports_concurrently(
    ports: list[int],
    host: str = "127.0.0.1",
    timeout: float = 1.0,
    max_workers: int = 32,
) -> list[PortReport]:
    """Inspect multiple ports concurrently using a ThreadPoolExecutor for high throughput."""
    if len(ports) <= 1:
        return [inspect_port(p, host=host, timeout=timeout) for p in ports]

    workers = min(max(1, max_workers), len(ports))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_port = {
            executor.submit(inspect_port, p, host, timeout): p
            for p in ports
        }
        results_by_port: dict[int, PortReport] = {}
        for future in concurrent.futures.as_completed(future_to_port):
            report = future.result()
            results_by_port[report.port] = report

    return [results_by_port[p] for p in ports]


def display_single_port_report(report: PortReport, host: str) -> None:
    """Display rich diagnostic report for a single port."""
    if report.in_use:
        print(f"Port {report.port} is IN USE (listening).\n")

        if report.docker_containers:
            print(f"Found {len(report.docker_containers)} Docker container(s) publishing port {report.port}:\n")
            for idx, c in enumerate(report.docker_containers, start=1):
                print(f"  [{idx}] Container : {c.name} (ID: {c.container_id})")
                print(f"      Image     : {c.image}")
                print(f"      Status    : {c.status}")
                print(f"      Ports     : {c.port_mapping}")
                print()

        if report.processes:
            print(f"Found {len(report.processes)} host process(es) associated with port {report.port}:\n")
            for idx, proc in enumerate(report.processes, start=1):
                pid_display = str(proc.pid) if proc.pid is not None else "Unknown"
                addrs_display = ", ".join(proc.bind_addresses)
                print(f"  [{idx}] Process   : {proc.name} (PID: {pid_display})")
                print(f"      Bind Addr : {addrs_display}")
                print(f"      State     : {proc.status}")
                print(f"      User      : {proc.username}")
                print(f"      Started   : {proc.created_at}")
                print(f"      Command   : {proc.cmdline}")
                print()
        elif not report.docker_containers:
            print(
                "  Note: Port is responding to TCP connections, but process details\n"
                "  could not be retrieved from the OS connection table.\n"
                "  Try running the command in an elevated PowerShell (Run as Administrator)."
            )
    else:
        print(f"Port {report.port} on {host} is FREE (closed).")


def display_multi_port_table(reports: list[PortReport]) -> None:
    """Display tabular summary for multiple inspected ports."""
    header = f"{'PORT':<8} {'STATUS':<10} {'PID':<10} {'PROCESS / CONTAINER':<28} {'USER':<20}"
    print(header)
    print("-" * len(header))
    for r in reports:
        status_str = "IN USE" if r.in_use else "FREE"
        if r.docker_containers:
            c = r.docker_containers[0]
            ident = f"docker:{c.name}"
            print(f"{r.port:<8} {status_str:<10} {'-':<10} {ident[:27]:<28} {'-':<20}")
        elif r.processes:
            p = r.processes[0]
            pid_str = str(p.pid) if p.pid is not None else "Unknown"
            print(f"{r.port:<8} {status_str:<10} {pid_str:<10} {p.name[:27]:<28} {p.username[:19]:<20}")
        elif r.in_use:
            print(f"{r.port:<8} {status_str:<10} {'-':<10} {'[Listening - No PID]':<28} {'-':<20}")
        else:
            print(f"{r.port:<8} {status_str:<10} {'-':<10} {'-':<28} {'-':<20}")


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="portdetect",
        description="Port Detective - Discover and manage processes and Docker containers using network ports.",
    )
    parser.add_argument(
        "ports",
        nargs="*",
        help="Port number(s) or range(s) to inspect (e.g. 8080, 8000-8005, 3000,5432)",
    )
    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Scan and list all actively listening ports on the host system",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format",
    )
    parser.add_argument(
        "-k",
        "--kill",
        action="store_true",
        help="Interactively terminate process or stop container using the port (prompts for confirmation)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host address for loopback socket probe (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=1.0,
        help="Socket timeout in seconds (default: 1.0)",
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=32,
        help="Maximum concurrent worker threads for multi-port scanning (default: 32)",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program version and exit",
    )
    parsed = parser.parse_args(args)

    # Maintain backward compatibility with single-port access (args.port)
    if parsed.ports:
        try:
            parsed.port = int(parsed.ports[0])
        except (ValueError, IndexError):
            parsed.port = None
    else:
        parsed.port = None

    return parsed


def main() -> int:
    """CLI entrypoint for Port Detective."""
    parsed = parse_args()

    # Determine ports to scan
    if parsed.all:
        target_ports = find_all_listening_ports()
        if not target_ports:
            if parsed.json:
                print(json.dumps([]))
            else:
                print("No actively listening ports detected on the system.")
            return 0
    else:
        if not parsed.ports:
            print(
                "Error: Please specify one or more ports (e.g. 8080, 8000-8005) or use --all.",
                file=sys.stderr,
            )
            return 1
        try:
            target_ports = parse_port_specs(parsed.ports)
        except ValueError as err:
            print(f"Error: {err}", file=sys.stderr)
            return 1
        if not target_ports:
            print("Error: No valid ports specified.", file=sys.stderr)
            return 1

    # Run concurrent inspection
    reports = inspect_ports_concurrently(
        target_ports,
        host=parsed.host,
        timeout=parsed.timeout,
        max_workers=parsed.workers,
    )

    # Output formatting
    if parsed.json:
        print(json.dumps([r.to_dict() for r in reports], indent=2))

    elif len(reports) == 1 and not parsed.all:
        display_single_port_report(reports[0], host=parsed.host)
    else:
        display_multi_port_table(reports)

    # Termination handling if --kill requested
    if parsed.kill:
        print("\n--- Termination / Shutdown Requested ---")
        occupied_reports = [r for r in reports if r.in_use]
        if not occupied_reports:
            print("No active processes or containers to terminate.")
            return 0

        for r in occupied_reports:
            action_taken = False
            if r.docker_containers:
                for c in r.docker_containers:
                    if stop_docker_container_safely(c):
                        action_taken = True
            if r.processes:
                for proc in r.processes:
                    if terminate_process_safely(proc):
                        action_taken = True

            if action_taken:
                rem_report = inspect_port(r.port, host=parsed.host, timeout=parsed.timeout)
                if not rem_report.in_use:
                    print(f"Verification: Port {r.port} is now FREE.")
                else:
                    print(f"Notice: Port {r.port} is still active with other listeners.")

    return 0


if __name__ == "__main__":
    sys.exit(main())

