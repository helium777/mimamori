import subprocess
from pathlib import Path

from .globals import SERVICE_TEMPLATE


def create_service_file(binary_path: str, config_dir: str, file_path: Path) -> None:
    """Create the systemd service file."""
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Create the service file
    service_content = SERVICE_TEMPLATE.format(
        binary_path=binary_path,
        config_dir=config_dir,
    )

    with open(file_path, "w") as f:
        f.write(service_content)


def reload_daemon() -> None:
    """Reload the systemd daemon."""
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)


def enable_service() -> None:
    """Enable the mimamori service."""
    subprocess.run(
        ["systemctl", "--user", "enable", "mimamori.service"],
        capture_output=True,
        text=True,
        check=True,
    )


def disable_service() -> None:
    """Disable the mimamori service."""
    subprocess.run(
        ["systemctl", "--user", "disable", "mimamori.service"],
        capture_output=True,
        text=True,
        check=True,
    )


def start_service() -> None:
    """Start the mimamori service."""
    subprocess.run(["systemctl", "--user", "start", "mimamori.service"], check=True)


def stop_service() -> None:
    """Stop the mimamori service."""
    subprocess.run(["systemctl", "--user", "stop", "mimamori.service"], check=True)


def restart_service() -> None:
    """Restart the mimamori service."""
    subprocess.run(["systemctl", "--user", "restart", "mimamori.service"], check=True)


def get_service_status() -> dict:
    """Get the status of the mimamori service."""
    result = {}

    # Check if service is enabled
    enabled_output = subprocess.run(
        ["systemctl", "--user", "is-enabled", "mimamori.service"],
        capture_output=True,
        text=True,
        check=False,
    )
    result["is_enabled"] = enabled_output.returncode == 0

    # Check if service is running and get running time
    status_output = subprocess.run(
        ["systemctl", "--user", "status", "mimamori.service"],
        capture_output=True,
        text=True,
        check=False,
    )
    status_text = status_output.stdout

    result["is_running"] = "Active: active (running)" in status_text

    # Extract running time
    running_time = None
    for line in status_text.splitlines():
        if "Active:" in line:
            parts = line.split(";")
            if len(parts) > 1:
                running_time = parts[1].strip().rstrip(" ago")
            break
    result["running_time"] = running_time

    # Get last log message
    log_output = subprocess.run(
        ["journalctl", "--user", "-u", "mimamori.service", "-n", "5", "--no-pager"],
        capture_output=True,
        text=True,
        check=False,
    )
    # Remove the first line (timestamp)
    messages = log_output.stdout.strip().split("\n")[1:]
    result["last_log_messages"] = messages

    return result


def is_service_running() -> bool:
    """Check if the service is running."""
    status_text = subprocess.run(
        ["systemctl", "--user", "status", "mimamori.service"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return "Active: active (running)" in status_text
