from pathlib import Path


MIHOMO_CONFIG_TEMPLATE = """
mixed-port: # auto-generated
external-controller: # auto-generated
mode: global
allow-lan: false
proxies: # auto-generated
proxy-groups:
  - name: AUTO-FALLBACK
    type: fallback
    proxies: # auto-generated
  - name: GLOBAL
    type: select
    proxies:
      - AUTO-FALLBACK
      # auto-generated
"""
SERVICE_TEMPLATE = """[Unit]
Description=Mihomo proxy service managed by Mimamori
After=network.target NetworkManager.service systemd-networkd.service iwd.service

[Service]
Type=simple
ExecStart={binary_path} -d {config_dir}
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=default.target
"""

MIHOMO_RELEASES_API_URL = "https://api.github.com/repos/MetaCubeX/mihomo/releases/"
MIMAMORI_CONFIG_PATH = Path.home() / ".config" / "mimamori" / "config.toml"
SERVICE_FILE_PATH = Path.home() / ".config" / "systemd" / "user" / "mimamori.service"
