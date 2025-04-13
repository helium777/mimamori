import gzip
import os
import platform
from urllib.parse import urljoin
import requests
import shutil
import tempfile
from pathlib import Path
from typing import Tuple
from rich.progress import Progress

from .utils import safe_move
from .globals import MIHOMO_RELEASES_API_URL


_PLATFORM_MAP = {
    "linux": "linux",
}

_ARCH_MAP = {
    "x86_64": "amd64",
}


def _get_download_url(platform_name: str, arch_name: str, version: str) -> str:
    """Get the download URL for the Mihomo binary.

    Args:
        version: The actual version string (e.g. "v1.0.0")
    """
    # Get the release info
    response = requests.get(urljoin(MIHOMO_RELEASES_API_URL, f"tags/{version}"))
    response.raise_for_status()
    release = response.json()

    # Find the appropriate asset
    asset_name = f"mihomo-{platform_name}-{arch_name}-{version}.gz"
    for asset in release["assets"]:
        if asset["name"] == asset_name:
            return asset["browser_download_url"]

    # Get all available asset names for error reporting
    available_assets = [asset["name"] for asset in release["assets"]]
    raise ValueError(
        f"No compatible Mihomo binary found for {platform_name}-{arch_name}. "
        f"Available assets: {', '.join(available_assets)}"
    )


def get_system_info() -> Tuple[str, str]:
    """Get the system platform and architecture."""
    platform_name = platform.system().lower()
    arch_name = platform.machine().lower()

    try:
        platform_name = _PLATFORM_MAP[platform_name]
        arch_name = _ARCH_MAP[arch_name]
    except KeyError:
        raise ValueError(f"Unsupported platform: {platform_name} {arch_name}")

    return platform_name, arch_name


def get_latest_version() -> str:
    """Get the latest version of Mihomo."""
    response = requests.get(urljoin(MIHOMO_RELEASES_API_URL, "latest"))
    response.raise_for_status()
    releases = response.json()

    return releases["tag_name"]


def download_mihomo(
    platform_name: str,
    arch_name: str,
    version: str,
    target_path: Path,
    show_progress: bool = True,
) -> Path:
    """Download Mihomo binary."""
    url = _get_download_url(platform_name, arch_name, version)

    # Ensure the target directory exists
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Download the compressed binary
    with tempfile.NamedTemporaryFile() as temp_file:
        with Progress() as progress:
            if show_progress:
                task = progress.add_task(f"Mihomo {version}", total=100)

            response = requests.get(url, stream=True)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0

            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)
                downloaded += len(chunk)
                if show_progress:
                    progress.update(
                        task,
                        completed=int(100 * downloaded / total_size)
                        if total_size
                        else 0,
                    )

        # Extract file
        with (
            gzip.open(temp_file.name, "rb") as f_in,
            tempfile.NamedTemporaryFile(delete=False) as f_out,
        ):
            shutil.copyfileobj(f_in, f_out)

    # Move the extracted file to the target path
    safe_move(f_out.name, target_path)

    # Make the binary executable
    os.chmod(target_path, 0o755)

    return target_path
