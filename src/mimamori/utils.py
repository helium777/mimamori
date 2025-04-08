from contextlib import closing
from pathlib import Path
import socket
import time
import requests


def check_port_availability(port: int) -> int:
    """Check if a port is available. If not, return an available port number.

    Returns:
        An available port number
    """
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("localhost", port))
        except socket.error:
            s.bind(("localhost", 0))
            port = s.getsockname()[1]
        return port


def aliases_already_exist(file_path: Path) -> bool:
    """Check if Mimamori aliases already exist in the given file."""
    if not file_path.exists():
        return False

    with open(file_path, "r") as f:
        content = f.read()

    return "### Mimamori aliases ###" in content


def check_proxy_connectivity() -> int:
    """Return the connection latency to Google.

    Returns:
        The connection latency in milliseconds
    """
    try:
        start_time = time.time()
        response = requests.get("https://www.google.com", timeout=1)
        end_time = time.time()
        response.raise_for_status()
        return int((end_time - start_time) * 1000)
    except requests.exceptions.RequestException:
        return -1
