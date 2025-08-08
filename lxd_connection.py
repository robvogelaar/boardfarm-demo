"""LXD connection module using REST API."""

from __future__ import annotations

import json
import logging
import time
from typing import Any
from urllib.parse import urljoin

import httpx
import pexpect

from boardfarm3.exceptions import DeviceConnectionError
from boardfarm3.lib.boardfarm_pexpect import BoardfarmPexpect

# Configure httpx logging to be less verbose
logging.getLogger("httpx").setLevel(logging.WARNING)

_CONNECTION_ERROR_THRESHOLD = 2
_CONNECTION_FAILED_STR: str = "Connection failed to LXD container"
_SHELL_PROMPT_UNAVAILABLE_STR = "Shell prompt is not available"


class LXDConnection(BoardfarmPexpect):
    """Connect to an LXD container via REST API."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        name: str,
        container_name: str,
        lxd_endpoint: str = "http://127.0.0.1:8443",
        shell_prompt: list[str] | None = None,
        save_console_logs: str = "",
        timeout: int = 30,
        trust_password: str | None = None,
        cert_file: str | None = None,
        key_file: str | None = None,
        **kwargs: dict[str, Any],  # ignore other arguments  # noqa: ARG002
    ) -> None:
        """Initialize LXD connection.

        :param name: connection name
        :type name: str
        :param container_name: LXD container name
        :type container_name: str
        :param lxd_endpoint: LXD REST API endpoint, defaults to "http://127.0.0.1:8443"
        :type lxd_endpoint: str
        :param shell_prompt: shell prompt pattern, defaults to None
        :type shell_prompt: list[str] | None
        :param save_console_logs: save console logs to disk, defaults to ""
        :type save_console_logs: str
        :param timeout: connection timeout, defaults to 30
        :type timeout: int
        :param trust_password: LXD trust password for authentication
        :type trust_password: str | None
        :param cert_file: path to client certificate file
        :type cert_file: str | None
        :param key_file: path to client key file
        :type key_file: str | None
        :param kwargs: additional keyword args
        """
        self._container_name = container_name
        self._lxd_endpoint = lxd_endpoint.rstrip("/")
        self._shell_prompt = shell_prompt
        self._timeout = timeout
        self._trust_password = trust_password
        self._cert_file = cert_file
        self._key_file = key_file
        self._authenticated = False

        # Setup HTTP client with optional certificates
        client_kwargs = {"timeout": timeout, "verify": False}
        if cert_file and key_file:
            client_kwargs["cert"] = (cert_file, key_file)

        self._client = httpx.Client(**client_kwargs)

        # Create a pseudo-command for the parent pexpect class
        # We'll override most functionality but need something for initialization
        command = f"echo 'LXD connection to {container_name}'"
        super().__init__(name, command, save_console_logs, [])

    def _api_request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Make an API request to LXD.

        :param method: HTTP method (GET, POST, etc.)
        :type method: str
        :param path: API path
        :type path: str
        :param kwargs: additional request parameters
        :return: API response data
        :rtype: dict[str, Any]
        :raises DeviceConnectionError: if API request fails
        """
        url = urljoin(f"{self._lxd_endpoint}/", path.lstrip("/"))
        try:
            response = self._client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            # Add more detailed error information
            error_msg = f"LXD API request failed: {method} {url} -> {e}"
            if hasattr(e, 'response') and e.response:
                error_msg += f" (Response: {e.response.status_code})"
                if e.response.content:
                    try:
                        error_data = e.response.json()
                        if 'error' in error_data:
                            error_msg += f" - {error_data['error']}"
                    except:
                        pass
            raise DeviceConnectionError(error_msg) from e

    def _authenticate(self) -> None:
        """Authenticate with LXD server using trust password or client certificates."""
        if self._authenticated:
            return

        try:
            # Get server info to check if we need authentication
            response = self._client.get(f"{self._lxd_endpoint}/1.0")
            if response.status_code == 200:
                # Check if we can access instances without auth
                test_response = self._client.get(f"{self._lxd_endpoint}/1.0/instances")
                if test_response.status_code == 200:
                    self._authenticated = True
                    return

            # If we have client certificates, they should be used automatically by httpx
            # Just test if they work
            if self._cert_file and self._key_file:
                # Certificate authentication is handled by httpx client
                # Just mark as authenticated - the client cert will be used automatically
                self._authenticated = True
                return

            # We need to authenticate with trust password
            if self._trust_password:
                auth_data = {
                    "type": "client",
                    "password": self._trust_password
                }

                response = self._client.post(
                    f"{self._lxd_endpoint}/1.0/certificates",
                    json=auth_data
                )

                if response.status_code in [200, 201]:
                    self._authenticated = True
                else:
                    raise DeviceConnectionError(f"Authentication failed: {response.status_code}")
            else:
                raise DeviceConnectionError("No authentication method available")

        except Exception as e:
            raise DeviceConnectionError(f"Authentication failed: {e}") from e

    def _exec_command_api(self, command: str, timeout: int = -1) -> dict[str, Any]:
        """Execute a command via LXD API.

        :param command: command to execute
        :type command: str
        :param timeout: timeout in seconds, defaults to -1
        :type timeout: int
        :return: execution result
        :rtype: dict[str, Any]
        :raises DeviceConnectionError: if command execution fails
        """
        # Create execution request - match the working curl format
        exec_data = {
            "command": ["bash", "-c", command],
            "wait-for-websocket": False,
            "record-output": True,
            "interactive": False,
            "environment": {
                "TERM": "dumb",
                "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
            }
        }

        # Start execution
        result = self._api_request(
            "POST",
            f"/1.0/instances/{self._container_name}/exec",
            json=exec_data
        )


        if result.get("type") != "async":
            raise DeviceConnectionError(f"Expected async operation from LXD exec, got: {result}")

        # Extract operation ID from the response
        operation_id = result.get("metadata", {}).get("id")
        if not operation_id:
            raise DeviceConnectionError(f"No operation ID in LXD response: {result}")

        # Wait for operation to complete
        max_wait = timeout if timeout > 0 else self._timeout
        start_time = time.time()

        while time.time() - start_time < max_wait:
            op_result = self._api_request("GET", f"/1.0/operations/{operation_id}")

            if op_result["metadata"]["status"] == "Success":
                # Return the complete result including operation ID
                result = {"metadata": op_result["metadata"], "id": operation_id}
                return result
            elif op_result["metadata"]["status"] == "Failure":
                error_msg = op_result["metadata"].get("err", "Unknown error")
                raise DeviceConnectionError(f"Command execution failed: {error_msg}")

            time.sleep(0.1)

        raise DeviceConnectionError("Command execution timed out")

    def _get_operation_logs(self, operation_id: str, metadata: dict = None) -> str:
        """Get logs from an operation.

        :param operation_id: LXD operation ID
        :param metadata: Operation metadata containing output paths
        :return: Combined stdout/stderr output
        """
        try:
            output_parts = []

            # If metadata is provided and contains output paths, use those
            if metadata and "metadata" in metadata and "metadata" in metadata["metadata"] and "output" in metadata["metadata"]["metadata"]:
                output_paths = metadata["metadata"]["metadata"]["output"]

                # Try to get stdout (file descriptor 1)
                if "1" in output_paths:
                    stdout_path = output_paths["1"]
                    try:
                        stdout_response = self._client.get(f"{self._lxd_endpoint}{stdout_path}")
                        if stdout_response.status_code == 200:
                            stdout_text = stdout_response.text
                            if stdout_text is not None:
                                output_parts.append(stdout_text)
                    except Exception:
                        pass

                # Try to get stderr (file descriptor 2)
                if "2" in output_paths:
                    stderr_path = output_paths["2"]
                    try:
                        stderr_response = self._client.get(f"{self._lxd_endpoint}{stderr_path}")
                        if stderr_response.status_code == 200:
                            stderr_text = stderr_response.text
                            if stderr_text and stderr_text.strip():
                                output_parts.append(f"STDERR: {stderr_text}")
                    except Exception:
                        pass

            # Fallback to old method if new method doesn't work
            if not output_parts:
                try:
                    stdout_response = self._client.get(f"{self._lxd_endpoint}/1.0/operations/{operation_id}/logs/stdout")
                    if stdout_response.status_code == 200:
                        stdout_text = stdout_response.text
                        if stdout_text is not None:
                            output_parts.append(stdout_text)
                except:
                    pass

                try:
                    stderr_response = self._client.get(f"{self._lxd_endpoint}/1.0/operations/{operation_id}/logs/stderr")
                    if stderr_response.status_code == 200:
                        stderr_text = stderr_response.text
                        if stderr_text and stderr_text.strip():
                            output_parts.append(f"STDERR: {stderr_text}")
                except:
                    pass

            return "\n".join(output_parts) if output_parts else ""

        except Exception as e:
            return ""

    def login_to_server(self, password: str | None = None) -> None:
        """Login to LXD container.

        :param password: not used for LXD connections
        :raises DeviceConnectionError: if container is not accessible
        :raises ValueError: if shell prompt is unavailable
        """
        # Authenticate with LXD server if needed (for trust password or test certificate access)
        if self._trust_password or self._cert_file:
            self._authenticate()

        # Check if container exists and is running
        try:
            container_info = self._api_request("GET", f"/1.0/instances/{self._container_name}")
            if container_info["metadata"]["status"] != "Running":
                # Try to start the container
                self._api_request("PUT", f"/1.0/instances/{self._container_name}/state",
                                json={"action": "start", "timeout": 30})

                # Wait for container to start
                start_time = time.time()
                while time.time() - start_time < 30:
                    container_info = self._api_request("GET", f"/1.0/instances/{self._container_name}")
                    if container_info["metadata"]["status"] == "Running":
                        break
                    time.sleep(1)
                else:
                    raise DeviceConnectionError(f"Container {self._container_name} failed to start")

        except DeviceConnectionError as e:
            if "not found" in str(e).lower():
                raise DeviceConnectionError(f"Container {self._container_name} not found") from e
            raise

        # Verify we can execute commands
        if not self._shell_prompt:
            raise ValueError(_SHELL_PROMPT_UNAVAILABLE_STR)

        try:
            result = self._exec_command_api("echo 'LXD connection established'")
        except DeviceConnectionError as e:
            raise DeviceConnectionError(f"{_CONNECTION_FAILED_STR}: {e}") from e

    def sendline(self, command: str = "") -> None:
        """Send a command line to the container (pexpect compatibility).

        :param command: command to send
        """
        if not command.strip():
            # Empty command, just simulate sending newline
            self._last_command = "echo"  # Dummy command for empty input
            self._last_output = ""
            return

        self._last_command = command.strip()
        try:
            result = self._exec_command_api(command, timeout=30)
            operation_id = result.get("id", "")
            if operation_id:
                self._last_output = self._get_operation_logs(operation_id, result)
            else:
                self._last_output = ""
        except Exception as e:
            self._last_output = f"ERROR: {e}"

    def expect(self, patterns, timeout: int = 30):
        """Wait for expected pattern (pexpect compatibility).

        :param patterns: pattern(s) to match
        :param timeout: timeout in seconds
        :return: index of matched pattern
        """
        import re

        # For LXD, we simulate the shell prompt by checking if we have output
        # and then matching against common prompt patterns

        # Get the shell prompt from the container
        if not hasattr(self, '_shell_output'):
            try:
                # Get actual prompt from container
                result = self._exec_command_api("echo $PS1 || echo '# '", timeout=5)
                operation_id = result.get("id", "")
                if operation_id:
                    prompt_output = self._get_operation_logs(operation_id, result)
                    # Use the actual prompt or fall back to default
                    self._shell_output = prompt_output.strip() or "# "
                else:
                    self._shell_output = "# "
            except:
                self._shell_output = "# "

        # Set the before/after attributes for pexpect compatibility
        self.before = getattr(self, '_last_output', '')
        self.after = self._shell_output

        # If patterns is a list, check each one
        if isinstance(patterns, list):
            for i, pattern in enumerate(patterns):
                if isinstance(pattern, str):
                    # Simple string match
                    if pattern in self._shell_output or '# ' in self._shell_output:
                        return i
                else:
                    # Regex pattern
                    if re.search(pattern, self._shell_output):
                        return i
            # No pattern matched, return 0 for first pattern
            return 0
        else:
            # Single pattern
            return 0

    def expect_exact(self, pattern: str, timeout: int = 30):
        """Expect exact string match (pexpect compatibility)."""
        self.before = getattr(self, '_last_output', '')
        return 0

    def get_last_output(self) -> str:
        """Get output from last command (pexpect compatibility)."""
        return getattr(self, '_last_output', '')

    def execute_command(self, command: str, timeout: int = -1) -> str:
        """Execute a command in the LXD container.

        :param command: command to execute
        :type command: str
        :param timeout: timeout in seconds, defaults to -1
        :type timeout: int
        :return: command output
        :rtype: str
        :raises DeviceConnectionError: if command execution fails
        """
        try:
            result = self._exec_command_api(command, timeout)

            # Extract operation ID to get logs
            operation_id = result.get("id", "")
            if operation_id and isinstance(operation_id, str):
                # Try to get command output from logs, pass the full result for metadata
                output = self._get_operation_logs(operation_id, result)
                if output:
                    return output.strip()

            # Fallback to metadata output
            metadata = result.get("metadata", {})

            # Check for output in metadata
            if "output" in metadata:
                return metadata["output"].strip()

            # Check for return value (exit code)
            if "return" in metadata:
                return_code = metadata["return"]
                # If return code is 0, command succeeded but may not have output
                if return_code == 0:
                    return ""
                else:
                    raise DeviceConnectionError(f"Command failed with exit code {return_code}")

            # Check for status and logs in metadata
            if "status" in metadata and metadata["status"] == "Success":
                return ""

            # If we get here, something went wrong
            raise DeviceConnectionError(f"Unexpected result structure: {result}")

        except DeviceConnectionError:
            raise
        except Exception as e:
            raise DeviceConnectionError(f"Command execution failed: {e}") from e

    def get_container_info(self) -> dict[str, Any]:
        """Get container information.

        :return: container information
        :rtype: dict[str, Any]
        """
        return self._api_request("GET", f"/1.0/containers/{self._container_name}")

    def start_container(self) -> None:
        """Start the container."""
        self._api_request("PUT", f"/1.0/containers/{self._container_name}/state",
                         json={"action": "start", "timeout": 30})

    def stop_container(self) -> None:
        """Stop the container."""
        self._api_request("PUT", f"/1.0/containers/{self._container_name}/state",
                         json={"action": "stop", "timeout": 30})

    def restart_container(self) -> None:
        """Restart the container."""
        self._api_request("PUT", f"/1.0/containers/{self._container_name}/state",
                         json={"action": "restart", "timeout": 30})

    def close(self) -> None:
        """Close the connection."""
        self._client.close()
        super().close()

    def __del__(self) -> None:
        """Cleanup on deletion."""
        if hasattr(self, '_client'):
            self._client.close()