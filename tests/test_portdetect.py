"""Unit tests for Port Detective."""

import json
import os
import subprocess
import unittest
from unittest.mock import MagicMock, patch

import psutil

from portdetect import (
    DockerContainerInfo,
    PortReport,
    ProcessInfo,
    __version__,
    find_all_listening_ports,
    find_docker_containers_on_port,
    find_processes_on_port,
    inspect_port,
    inspect_ports_concurrently,
    is_port_in_use,
    parse_args,
    parse_port_specs,
    terminate_process_safely,
)




class TestArgParsing(unittest.TestCase):
    """Test CLI argument parsing."""

    def test_valid_port(self):
        args = parse_args(["8080"])
        self.assertEqual(args.port, 8080)
        self.assertFalse(args.kill)
        self.assertEqual(args.host, "127.0.0.1")

    def test_kill_flag(self):
        args = parse_args(["3000", "--kill"])
        self.assertEqual(args.port, 3000)
        self.assertTrue(args.kill)

    def test_custom_host_and_timeout(self):
        args = parse_args(["5432", "--host", "0.0.0.0", "--timeout", "2.5"])
        self.assertEqual(args.host, "0.0.0.0")
        self.assertEqual(args.timeout, 2.5)


class TestSocketCheck(unittest.TestCase):
    """Test socket level port checks."""

    @patch("socket.socket")
    def test_port_in_use_open(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0
        mock_socket_class.return_value.__enter__.return_value = mock_sock

        self.assertTrue(is_port_in_use(8080))
        mock_sock.connect_ex.assert_called_with(("127.0.0.1", 8080))

    @patch("socket.socket")
    def test_port_in_use_closed(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 10061  # WSAECONNREFUSED
        mock_socket_class.return_value.__enter__.return_value = mock_sock

        self.assertFalse(is_port_in_use(8080))


class TestProcessDetection(unittest.TestCase):
    """Test OS process lookup via psutil."""

    @patch("psutil.net_connections")
    @patch("psutil.Process")
    def test_find_processes_success(self, mock_process_class, mock_net_conns):
        # Setup mock connection
        mock_conn = MagicMock()
        mock_conn.laddr.ip = "127.0.0.1"
        mock_conn.laddr.port = 8080
        mock_conn.status = "LISTEN"
        mock_conn.pid = 9999
        mock_net_conns.return_value = [mock_conn]

        # Setup mock process
        mock_proc = MagicMock()
        mock_proc.name.return_value = "test_server.exe"
        mock_proc.cmdline.return_value = ["test_server.exe", "--port", "8080"]
        mock_proc.username.return_value = "TEST_USER"
        mock_proc.create_time.return_value = 1700000000.0
        mock_process_class.return_value = mock_proc

        results = find_processes_on_port(8080)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].pid, 9999)
        self.assertEqual(results[0].name, "test_server.exe")
        self.assertIn("127.0.0.1:8080", results[0].bind_addresses)

    @patch("psutil.net_connections")
    def test_find_processes_access_denied(self, mock_net_conns):
        mock_net_conns.side_effect = psutil.AccessDenied()
        results = find_processes_on_port(8080)
        self.assertEqual(results, [])


class TestDockerDetection(unittest.TestCase):
    """Test Docker container detection."""

    @patch("subprocess.run")
    def test_find_docker_containers_match(self, mock_run):
        mock_output = json.dumps({
            "ID": "abc123def456",
            "Names": "web-container",
            "Image": "nginx:alpine",
            "Ports": "0.0.0.0:8080->80/tcp, [::]:8080->80/tcp",
            "Status": "Up 5 minutes",
        })
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)

        containers = find_docker_containers_on_port(8080)
        self.assertEqual(len(containers), 1)
        self.assertEqual(containers[0].name, "web-container")
        self.assertEqual(containers[0].image, "nginx:alpine")
        self.assertEqual(containers[0].container_id, "abc123def456")

    @patch("subprocess.run")
    def test_find_docker_daemon_offline(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="daemon offline")
        containers = find_docker_containers_on_port(8080)
        self.assertEqual(containers, [])


class TestSafetyGuardrails(unittest.TestCase):
    """Test safety invariants for process termination."""

    def test_refuse_system_pids(self):
        for sys_pid in (0, 4):
            proc_info = ProcessInfo(
                pid=sys_pid,
                name="System",
                bind_addresses=["0.0.0.0:135"],
                status="LISTEN",
                cmdline="N/A",
                username="NT AUTHORITY\\SYSTEM",
                created_at="N/A",
            )
            # Should immediately return False without prompting
            result = terminate_process_safely(proc_info)
            self.assertFalse(result)

    def test_refuse_self_pid(self):
        proc_info = ProcessInfo(
            pid=os.getpid(),
            name="python.exe",
            bind_addresses=["127.0.0.1:8080"],
            status="LISTEN",
            cmdline="portdetect",
            username="CURRENT_USER",
            created_at="N/A",
        )
        result = terminate_process_safely(proc_info)
        self.assertFalse(result)

    @patch("builtins.input", return_value="n")
    def test_user_rejection_at_prompt(self, mock_input):
        proc_info = ProcessInfo(
            pid=12345,
            name="node.exe",
            bind_addresses=["127.0.0.1:3000"],
            status="LISTEN",
            cmdline="node server.js",
            username="DEV_USER",
            created_at="N/A",
        )
        result = terminate_process_safely(proc_info)
        self.assertFalse(result)


class TestPortSpecParsing(unittest.TestCase):
    """Test port specification parsing (individual, comma-separated, ranges)."""

    def test_single_port(self):
        self.assertEqual(parse_port_specs(["8080"]), [8080])

    def test_comma_separated(self):
        self.assertEqual(parse_port_specs(["8080,3000"]), [3000, 8080])

    def test_range(self):
        self.assertEqual(parse_port_specs(["8000-8003"]), [8000, 8001, 8002, 8003])

    def test_mixed_specs_and_deduplication(self):
        specs = ["8080", "8000-8002", "8080", "5432,8001"]
        self.assertEqual(parse_port_specs(specs), [5432, 8000, 8001, 8002, 8080])

    def test_invalid_syntax(self):
        with self.assertRaises(ValueError):
            parse_port_specs(["invalid"])

    def test_out_of_bounds(self):
        with self.assertRaises(ValueError):
            parse_port_specs(["0"])
        with self.assertRaises(ValueError):
            parse_port_specs(["70000"])

    def test_inverted_range(self):
        with self.assertRaises(ValueError):
            parse_port_specs(["8005-8000"])


class TestMultiPortAndJson(unittest.TestCase):
    """Test multi-port arguments, JSON reporting, and listening port discovery."""

    def test_parse_args_all_and_json(self):
        args = parse_args(["--all", "--json"])
        self.assertTrue(args.all)
        self.assertTrue(args.json)
        self.assertEqual(args.ports, [])

    def test_parse_args_multi_ports(self):
        args = parse_args(["8080", "3000-3002", "--json"])
        self.assertEqual(args.ports, ["8080", "3000-3002"])
        self.assertEqual(args.port, 8080)
        self.assertTrue(args.json)

    def test_port_report_to_dict(self):
        report = PortReport(
            port=8080,
            in_use=True,
            processes=[
                ProcessInfo(
                    pid=1234,
                    name="python.exe",
                    bind_addresses=["127.0.0.1:8080"],
                    status="LISTEN",
                    cmdline="python server.py",
                    username="TESTUSER",
                    created_at="2026-10-06 12:00:00",
                )
            ],
            docker_containers=[
                DockerContainerInfo(
                    container_id="c1a2b3",
                    name="web-server",
                    image="nginx",
                    port_mapping="0.0.0.0:8080->80/tcp",
                    status="Up 2 hours",
                )
            ],
        )
        d = report.to_dict()
        self.assertEqual(d["port"], 8080)
        self.assertEqual(d["status"], "in_use")
        self.assertEqual(len(d["processes"]), 1)
        self.assertEqual(d["processes"][0]["pid"], 1234)
        self.assertEqual(len(d["docker_containers"]), 1)
        self.assertEqual(d["docker_containers"][0]["name"], "web-server")

    @patch("psutil.net_connections")
    @patch("subprocess.run")
    def test_find_all_listening_ports(self, mock_subproc, mock_net_conns):
        # Setup mock connection
        mock_conn = MagicMock()
        mock_conn.status = psutil.CONN_LISTEN
        mock_conn.laddr = MagicMock(port=8080)
        mock_net_conns.return_value = [mock_conn]

        # Setup mock docker
        mock_subproc.return_value.returncode = 0
        mock_subproc.return_value.stdout = json.dumps({"Ports": "0.0.0.0:3000->3000/tcp"}) + "\n"

        ports = find_all_listening_ports()
        self.assertEqual(ports, [3000, 8080])


class TestConcurrentInspection(unittest.TestCase):
    """Test concurrent multi-port scanning."""

    @patch("portdetect.inspect_port")
    def test_inspect_ports_concurrently(self, mock_inspect):
        def side_effect(port, host="127.0.0.1", timeout=1.0):
            return PortReport(port=port, in_use=False, processes=[], docker_containers=[])

        mock_inspect.side_effect = side_effect
        ports = [8080, 8081, 8082, 8083]
        reports = inspect_ports_concurrently(ports, max_workers=4)

        self.assertEqual(len(reports), 4)
        self.assertEqual([r.port for r in reports], [8080, 8081, 8082, 8083])
        self.assertEqual(mock_inspect.call_count, 4)

    def test_single_port_concurrent_bypass(self):
        reports = inspect_ports_concurrently([8080])
        self.assertEqual(len(reports), 1)

    def test_parse_args_workers(self):
        args = parse_args(["8080", "--workers", "16"])
        self.assertEqual(args.workers, 16)


if __name__ == "__main__":
    unittest.main()


