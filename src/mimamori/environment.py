import os
import subprocess
from typing import Dict, List


def _get_proxy_env(port: int) -> Dict[str, str]:
    """Get the proxy environment variables."""
    http_proxy = f"http://127.0.0.1:{port}"
    https_proxy = http_proxy
    all_proxy = http_proxy
    no_proxy = "localhost,127.0.0.1"

    return {
        "http_proxy": http_proxy,
        "https_proxy": https_proxy,
        "all_proxy": all_proxy,
        "HTTP_PROXY": http_proxy,
        "HTTPS_PROXY": https_proxy,
        "ALL_PROXY": all_proxy,
        "no_proxy": no_proxy,
        "NO_PROXY": no_proxy,
    }


def generate_export_commands(port: int) -> List[str]:
    """Generate shell commands to export proxy environment variables."""
    env_vars = _get_proxy_env(port)
    commands = [f"export {key}={value}" for key, value in env_vars.items()]

    return commands


def generate_unset_commands() -> List[str]:
    """Generate shell commands to unset proxy environment variables."""
    env_vars = list(_get_proxy_env(0).keys())
    commands = [f"unset {key}" for key in env_vars]

    return commands


def run_with_proxy_env(port: int, command: List[str]) -> int:
    """Run a command with proxy environment variables."""
    env = os.environ.copy()
    env.update(_get_proxy_env(port))

    process = subprocess.run(command, env=env)
    return process.returncode
