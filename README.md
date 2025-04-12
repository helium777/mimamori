# Mimamori

> *"Mimamori" (見守り) means "watching over" or "monitoring" in Japanese - your guardian for proxy management in restricted environments.*

A sleek, lightweight CLI frontend for Mihomo, inspired by [mihoro](https://github.com/spencerwooo/mihoro), designed specifically for proxy management on Linux systems **without root privileges**. Perfect for research GPU servers, university clusters, and other environments where admin rights are limited.

> [!WARNING]
> Mimamori is currently in early development. Features may be incomplete, unstable, or subject to significant changes. Use at your own risk.

## Why Mimamori?

Seamless proxy management for restricted environments:

- **No root access required** - runs entirely in user space
- **Reliable service** - managed via systemd user services
- **Simple workflow** - quick setup and intuitive commands

## Quick Start

```bash
# Install mimamori using uv
uv tool install mimamori  # or `pip install mimamori` if you prefer pip

# One-command setup with default settings - installs and configures everything automatically
mim setup --yes

# After restarting your shell, enjoy a seamless workflow:
pon                # Enable proxy in current shell
curl google.com    # All network traffic now routes through your proxy
poff               # Disable proxy when finished

# Or use the proxychains-style command prefix:
pp curl google.com # Run specific commands through proxy without affecting shell
```

> [!CAUTION]
> The `pp` (or `mim proxy run`) command, while similar to gg/proxychains-ng in usage, only configures environment variables. While most common applications respect these variables, some programs may ignore them. Future versions may implement true transparent proxying.

## Usage

Mimamori offers these additional commands for enhanced user experience:

```bash
mim status    # View comprehensive status dashboard (service, connectivity, ports, logs)

mim select    # Choose which proxy node to use
```

## Technical Details

- Mimamori operates in **GLOBAL mode** without traffic rules. This is optimized for GPU servers that primarily access international resources (PyPI, Google Drive, etc.) with minimal need for domestic website allowlisting.

- The default configuration automatically selects functioning nodes from your subscription using the AUTO-FALLBACK strategy group. Use `mim select` when you need to manually choose a specific node.

## Comparison with Similar Projects

- **vs. [gg](https://github.com/mzz2017/gg)**: While gg provides an excellent portable solution with its own implementation, Mimamori leverages Mihomo's extensive protocol support and benefits from its regular maintenance.

- **vs. [mihoro](https://github.com/spencerwooo/mihoro)**: Mimamori builds upon mihoro's approach while enhancing the user experience through automated binary downloads, command wrapping capabilities, and elegant proxy status visualization.

## Similar Tools

- **[mihoro](https://github.com/spencerwooo/mihoro)**: Mihomo CLI client on Linux. Formerly `clashrup`.
- **[gg](https://github.com/mzz2017/gg)**: A command-line tool for one-click proxy in your research and development without installing v2ray or anything else (only for linux).
- **[proxychains-ng](https://github.com/rofl0r/proxychains-ng)**: A preloader which hooks calls to sockets in dynamically linked programs and redirects it through one or more socks/http proxies.
