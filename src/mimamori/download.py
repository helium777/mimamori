import gzip
import logging
import os
import platform
import shutil
import tempfile
from pathlib import Path
from typing import IO, Callable

import requests
from requests.exceptions import RequestException

from .utils import safe_move

logger = logging.getLogger(__name__)

_PLATFORM_MAP = {
    "linux": "linux",
}
_ARCH_MAP = {
    "x86_64": "amd64",
}


class DownloadError(Exception):
    pass


def apply_proxy(url: str, github_proxy: str) -> str:
    return github_proxy + url


def get_system_info() -> tuple[str, str]:
    """Get the system platform and architecture."""
    platform_name = platform.system().lower()
    arch_name = platform.machine().lower()

    try:
        platform_name = _PLATFORM_MAP[platform_name]
        arch_name = _ARCH_MAP[arch_name]
    except KeyError as e:
        msg = f"Unsupported platform: {platform_name} {arch_name}"
        logger.error(msg)
        raise DownloadError(msg) from e

    return platform_name, arch_name


def get_latest_version(github_proxy: str | None = None) -> str:
    url = "https://github.com/MetaCubeX/mihomo/releases/latest"

    if github_proxy:
        proxied_url = apply_proxy(url, github_proxy)
        try:
            response = requests.get(proxied_url)
            response.raise_for_status()
            return response.url.split("/")[-1]
        except RequestException:
            msg = f"Failed to get the latest version from {proxied_url}, trying to use the original URL..."
            logger.warning(msg)

    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.url.split("/")[-1]
    except RequestException as e:
        msg = f"Failed to get the latest version from {url}"
        logger.error(msg)
        raise DownloadError(msg) from e


def _download_url(
    url: str,
    f: IO[bytes],
    progress_callback: Callable[[int, int], None] | None = None,
) -> None:
    logger.info(f"Downloading from {url}")
    response = requests.get(url, stream=True)
    response.raise_for_status()

    total_size = int(response.headers.get("content-length", 0))
    downloaded = 0

    f.seek(0)
    f.truncate()

    for chunk in response.iter_content():
        f.write(chunk)
        downloaded += len(chunk)
        progress_callback(downloaded, total_size)

    f.seek(0)


def download_mihomo(
    platform_name: str,
    arch_name: str,
    version: str,
    target_path: Path,
    github_proxy: str | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> Path:
    url = f"https://github.com/MetaCubeX/mihomo/releases/download/{version}/mihomo-{platform_name}-{arch_name}-{version}.gz"

    # Ensure the target directory exists
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Download the compressed binary
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        downloaded = False

        if github_proxy:
            proxied_url = apply_proxy(url, github_proxy)
            try:
                _download_url(proxied_url, temp_file, progress_callback)
            except RequestException:
                logger.warning(
                    f"Failed to download from {proxied_url}, trying to use the original URL..."
                )
            downloaded = True

        if not downloaded:
            try:
                _download_url(url, temp_file, progress_callback)
            except RequestException as e:
                msg = f"Failed to download from {url}"
                logger.error(msg)
                raise DownloadError(msg) from e

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

    # Remove the temporary file
    os.remove(temp_file.name)

    return target_path
