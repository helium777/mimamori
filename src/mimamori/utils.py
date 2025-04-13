from contextlib import closing
import errno
import os
from pathlib import Path
import shutil
import socket
import tempfile
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


def remove_aliases(file_path: Path) -> bool:
    """Remove Mimamori aliases from the given file."""
    if not file_path.exists():
        return False

    with open(file_path, "r") as f:
        content = f.read()

    # Remove content between "### Mimamori aliases ###" and "### End of Mimamori aliases ###" (inclusive)
    start_marker = "### Mimamori aliases ###"
    end_marker = "### End of Mimamori aliases ###"
    start = content.find(start_marker)
    end = content.find(end_marker) + len(end_marker)
    if start == -1 or end == -1:
        return False

    # Remove leading and trailing newlines
    try:
        if content[start - 2 : start] == "\n\n":
            start -= 1
    except IndexError:
        pass
    try:
        if content[end] == "\n":
            end += 1
    except IndexError:
        pass

    with open(file_path, "w") as f:
        f.write(content[:start])
        f.write(content[end:])

    return True


def check_proxy_connectivity() -> int:
    """Return the connection latency to Google.

    Returns:
        The connection latency in milliseconds, or -1 if the connection is timed out, or -2 if the connection is failed.
    """
    try:
        start_time = time.time()
        response = requests.get("https://www.google.com", timeout=1)
        end_time = time.time()
        response.raise_for_status()
        return int((end_time - start_time) * 1000)
    except requests.exceptions.Timeout:
        return -1
    except requests.exceptions.RequestException:
        return -2


def get_shell_rc_path() -> Path:
    """Get the path to the shell's rc file."""
    shell = os.environ.get("SHELL", "")
    rc_path = None
    if "bash" in shell:
        rc_path = Path.home() / ".bashrc"
    elif "zsh" in shell:
        rc_path = Path.home() / ".zshrc"
    return shell, rc_path


def safe_move(src, dst) -> None:
    """Move a file from source to destination. If the destination file already exists, it will be overwritten.

    - Move is guaranteed to be atomic while `shutil.move()` is not.

    - Move works across different filesystems while `os.rename()` throws an error in that case.
    """
    if not isinstance(src, Path):
        src = Path(src)
    if not isinstance(dst, Path):
        dst = Path(dst)

    try:
        os.rename(src, dst)
    except OSError as err:
        if err.errno == errno.EXDEV:
            with tempfile.NamedTemporaryFile(delete=False, dir=dst.parent) as tmp:
                # Copy the source file to the destination filesystem
                shutil.copy(src, tmp.name)
                # Atomic move
                os.rename(tmp.name, dst)

            # Remove the source file
            os.unlink(src)
        else:
            raise
