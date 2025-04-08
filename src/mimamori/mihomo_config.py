from pathlib import Path
import requests
import yaml
from typing import Literal

from .globals import GLOBAL_CONFIG_TEMPLATE


def create_mihomo_config(
    config_path: Path,
    config_preset: Literal["global", "rule"],
    subscription: str,
    port: int,
    api_port: int,
) -> None:
    """
    Create Mihomo configuration file.

    Args:
        config_path: Path where to save the config file
        config_preset: Configuration preset ("global" or "rule")
        subscription: Subscription URL
        port: Port number or "auto" for auto-selection
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if config_preset == "global":
        template = GLOBAL_CONFIG_TEMPLATE
    else:
        raise NotImplementedError("Rule mode is not implemented yet")

    # Get proxy nodes from the subscription
    response = requests.get(subscription)
    response.raise_for_status()
    sub_yaml = yaml.safe_load(response.text)
    proxies = sub_yaml.get("proxies")
    if proxies is None:
        raise ValueError("No proxies found in the subscription")

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
