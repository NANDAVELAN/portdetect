"""Unit tests for Port Detective."""

import json
import os
import subprocess
import unittest
from unittest.mock import MagicMock, patch

import psutil

from portdetect import (
    DockerContainerInfo,
    ProcessInfo,
    find_docker_containers_on_port,
    find_processes_on_port,
    is_port_in_use,
    parse_args,
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


if __name__ == "__main__":
    unittest.main()
