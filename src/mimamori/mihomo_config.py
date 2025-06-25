import logging
from pathlib import Path

import requests
import yaml
from requests.exceptions import RequestException

from .globals import MIHOMO_CONFIG_TEMPLATE

logger = logging.getLogger(__name__)


class MihomoSubscriptionError(Exception):
    pass


def create_mihomo_config(
    config_path: Path,
    subscription: str,
    port: int,
    api_port: int,
) -> None:
    """
    Create Mihomo configuration file.

    Args:
        config_path: Path where to save the config file
        subscription: Subscription URL
        port: Port number or "auto" for auto-selection
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)

    template = MIHOMO_CONFIG_TEMPLATE

    # Get proxy nodes from the subscription
    try:
        response = requests.get(
            subscription, headers={"User-Agent": "Clash"}
        )  # some subscription may require a user agent to return clash format
        response.raise_for_status()
        content = response.text
    except RequestException as e:
        logger.error(f"Failed to get subscription from {subscription}: {e}")
        raise MihomoSubscriptionError(
            f"Failed to get subscription from {subscription}: {e}"
        ) from e

    sub_yaml = yaml.safe_load(content)
    if not isinstance(sub_yaml, dict):
        raise MihomoSubscriptionError(
            "Could not parse subscription content as YAML."
            f"First 100 characters: {content[:100]}"
        )

    proxies = sub_yaml.get("proxies")
    if proxies is None:
        raise MihomoSubscriptionError("No proxies found in the subscription.")

    # Mix the proxies into the template
    config_yaml = yaml.safe_load(template)
    config_yaml["mixed-port"] = port
    config_yaml["external-controller"] = f"127.0.0.1:{api_port}"
    config_yaml["proxies"] = proxies
    proxy_names = [p["name"] for p in proxies]
    config_yaml["proxy-groups"][0]["proxies"] = proxy_names
    config_yaml["proxy-groups"][1]["proxies"].extend(proxy_names)

    # Write to the config file
    with open(config_path, "w") as f:
        yaml.dump(config_yaml, f)
