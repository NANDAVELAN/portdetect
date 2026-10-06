"""Port Detective - Phase 4: Docker container detection & attribution."""

import argparse
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


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="portdetect",
        description="Port Detective - Discover and manage processes and Docker containers using network ports.",
    )
    parser.add_argument(
        "port",
        type=int,
        help="Port number to inspect (1-65535)",
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
    return parser.parse_args(args)


def main() -> int:
    """CLI entrypoint for Phase 4."""
    parsed = parse_args()

    if not (1 <= parsed.port <= 65535):
        print(f"Error: Invalid port {parsed.port}. Must be between 1 and 65535.", file=sys.stderr)
        return 1

    # Step 1: Query process table
    processes = find_processes_on_port(parsed.port)

    # Step 2: Query Docker containers
    docker_containers = find_docker_containers_on_port(parsed.port)

    # Step 3: Probe port with socket handshake
    socket_open = is_port_in_use(parsed.port, host=parsed.host, timeout=parsed.timeout)

    if processes or docker_containers or socket_open:
        print(f"Port {parsed.port} is IN USE (listening).\n")

        # Display Docker containers if found
        if docker_containers:
            print(f"Found {len(docker_containers)} Docker container(s) publishing port {parsed.port}:\n")
            for idx, c in enumerate(docker_containers, start=1):
                print(f"  [{idx}] Container : {c.name} (ID: {c.container_id})")
                print(f"      Image     : {c.image}")
                print(f"      Status    : {c.status}")
                print(f"      Ports     : {c.port_mapping}")
                print()

        # Display host processes
        if processes:
            print(f"Found {len(processes)} host process(es) associated with port {parsed.port}:\n")
            for idx, proc in enumerate(processes, start=1):
                pid_display = str(proc.pid) if proc.pid is not None else "Unknown"
                addrs_display = ", ".join(proc.bind_addresses)
                print(f"  [{idx}] Process   : {proc.name} (PID: {pid_display})")
                print(f"      Bind Addr : {addrs_display}")
                print(f"      State     : {proc.status}")
                print(f"      User      : {proc.username}")
                print(f"      Started   : {proc.created_at}")
                print(f"      Command   : {proc.cmdline}")
                print()
        elif not docker_containers:
            print(
                "  Note: Port is responding to TCP connections, but process details\n"
                "  could not be retrieved from the OS connection table.\n"
                "  Try running the command in an elevated PowerShell (Run as Administrator)."
            )

        if parsed.kill:
            print("--- Termination / Shutdown Requested ---")
            action_taken = False

            # If Docker container found, prompt to stop container first
            if docker_containers:
                for c in docker_containers:
                    if stop_docker_container_safely(c):
                        action_taken = True

            # If host processes found and not just docker-proxy/wsl backend handled by docker stop
            if processes:
                # If docker was stopped, re-check before terminating host processes
                for proc in processes:
                    if terminate_process_safely(proc):
                        action_taken = True

            if action_taken:
                rem_processes = find_processes_on_port(parsed.port)
                rem_docker = find_docker_containers_on_port(parsed.port)
                rem_open = is_port_in_use(parsed.port, host=parsed.host, timeout=parsed.timeout)
                if not rem_processes and not rem_docker and not rem_open:
                    print(f"\nVerification: Port {parsed.port} is now FREE.")
                else:
                    print(f"\nNotice: Port {parsed.port} is still active with other listeners.")
    else:
        print(f"Port {parsed.port} on {parsed.host} is FREE (closed).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
