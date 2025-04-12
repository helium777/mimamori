import os
import sys
import shutil
from pathlib import Path
import traceback
from typing import List, Optional, Dict
import click
from pydantic import ValidationError
import requests
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .globals import MIMAMORI_CONFIG_PATH, SERVICE_FILE_PATH
from . import __version__
from .settings import Settings
from .download import download_mihomo, get_latest_version, get_system_info
from .mihomo_config import create_mihomo_config
from .utils import (
    aliases_already_exist,
    check_port_availability,
    check_proxy_connectivity,
    get_shell_rc_path,
    remove_aliases,
)
from .systemd import (
    create_service_file,
    is_service_running,
    reload_daemon,
    enable_service,
    disable_service,
    start_service,
    stop_service,
    restart_service,
    get_service_status,
)
from .environment import (
    generate_export_commands,
    generate_unset_commands,
)
from .environment import run_with_proxy_env
from .mihomo_api import (
    MihomoAPI,
)


console = Console()
try:
    settings = Settings()
except ValidationError:
    backup_path = MIMAMORI_CONFIG_PATH.with_suffix(MIMAMORI_CONFIG_PATH.suffix + ".bak")
    if MIMAMORI_CONFIG_PATH.exists():
        MIMAMORI_CONFIG_PATH.replace(backup_path)
    console.print(
        "[bold red]Warning: [/bold red]Invalid configuration file. Creating a new one. "
        f"Old config saved at {backup_path}."
    )
    settings = Settings()
    settings.save_to_file()


@click.group()
@click.version_option(version=__version__, prog_name="mimamori")
def cli() -> None:
    """Mimamori: A lightweight CLI for Mihomo proxy management."""
    pass


@cli.command("setup")
@click.option(
    "--url",
    help="Subscription URL for Mihomo",
    default=None,
)
@click.option(
    "--yes",
    is_flag=True,
    help="Skip all prompts and use default behavior",
)
def setup(url: Optional[str], yes: bool) -> None:
    """Set up Mimamori with interactive prompts."""
    if url is None:
        if settings.mihomo.subscription and (
            yes
            or Confirm.ask(
                f"[bold]Use existing subscription {settings.mihomo.subscription}?"
            )
        ):
            url = settings.mihomo.subscription
        else:
            url = Prompt.ask("[bold]Enter your Mihomo subscription URL")
            settings.mihomo.subscription = url

    try:
        version = settings.mihomo.version
        binary_path = Path(settings.mihomo.binary_path)

        console.print()
        # 1. Download Mihomo binary
        need_download = False
        if not binary_path.exists():
            need_download = True
        elif yes or Confirm.ask(
            f"[yellow]Mihomo binary already exists at {binary_path}.[/yellow]\n[bold]Do you want to re-downloading it?[/bold]"
        ):
            need_download = True

        if need_download:
            if version == "latest":
                version = get_latest_version()
            platform_name, arch_name = get_system_info()

            download_mihomo(
                platform_name, arch_name, version, binary_path, show_progress=True
            )

            console.print(f"[green]Downloaded Mihomo {version} to {binary_path}")

        console.print()
        # 2. Create Mihomo config
        with console.status("[bold]Creating mihomo config..."):
            _generate_mihomo_config()

        console.print(
            f"[green]Created mihomo config at {settings.mihomo.config_dir}/config.yaml"
        )

        console.print()
        # 3. Create service file
        if not SERVICE_FILE_PATH.exists():
            if yes or Confirm.ask(
                "[bold]Do you want to create a service file to keep Mihomo running?"
            ):
                with console.status("[bold]Creating service file..."):
                    create_service_file(
                        settings.mihomo.binary_path,
                        settings.mihomo.config_dir,
                        SERVICE_FILE_PATH,
                    )
                    console.print(f"[green]Created service file at {SERVICE_FILE_PATH}")
        else:
            console.print(f"[green]Service file already exists at {SERVICE_FILE_PATH}")

        reload_daemon()
        enable_service()
        restart_service()

        console.print()
        # 4. Set up shell aliases
        console.print("""[bold]Recommended shell aliases:[/bold]
alias [cyan]pon[/cyan]=eval $(mim proxy export)  - Enable proxy in current shell
alias [cyan]poff[/cyan]=eval $(mim proxy unset)  - Disable proxy when done
alias [cyan]pp[/cyan]=mim proxy run              - Run commands with proxy enabled""")

        shell, rc_path = get_shell_rc_path()
        if rc_path is None:
            console.print(
                f"[yellow]Unsupported shell {shell}. Please add the aliases manually."
            )

        aliases_enabled = False
        setup_aliases = False
        if rc_path:
            if aliases_already_exist(rc_path):
                console.print(
                    f"[green]You have already set up the shell aliases in ~/{rc_path.name}"
                )
                aliases_enabled = True
            else:
                need_setup_aliases = yes or Confirm.ask(
                    "[bold]Do you want to set up these shell aliases?"
                )

                if need_setup_aliases:
                    aliases_content = (
                        "\n### Mimamori aliases ###\n"
                        "alias pon='eval $(mim proxy export)'\n"
                        "alias poff='eval $(mim proxy unset)'\n"
                        "alias pp='mim proxy run'\n"
                        "### End of Mimamori aliases ###\n"
                    )

                    with open(rc_path, "a") as f:
                        f.write(aliases_content)
                    console.print(f"[green]Added aliases to ~/{rc_path.name}")
                    aliases_enabled = True
                    setup_aliases = True

        # 5. Save settings
        settings.save_to_file()

        console.print()
        # 6. Print completion message
        console.print("[green]🥳 Setup completed successfully!")
        console.print("\nNext steps:")
        if aliases_enabled:
            if setup_aliases:
                console.print(
                    "[bold yellow]You should restart your shell to apply the aliases."
                )
            console.print("- Run [cyan]pon[/cyan] to enable the proxy in current shell")
            console.print(
                "- Run [cyan]poff[/cyan] to disable the proxy in current shell"
            )
            console.print("- Run [cyan]pp[/cyan] to run commands with proxy enabled")
        else:
            console.print(
                "- Run [cyan]eval $(mim proxy export)[/cyan] to enable the proxy in current shell"
            )
            console.print(
                "- Run [cyan]eval $(mim proxy unset)[/cyan] to disable the proxy in current shell"
            )
            console.print(
                "- Run [cyan]mim proxy run[/cyan] to run commands with proxy enabled"
            )

    except Exception as e:
        console.print(f"[bold red]Error during setup: [/bold red] {e}")
        sys.exit(1)


@cli.command("status")
def status() -> None:
    """Display proxy status."""
    status = get_service_status()
    is_enabled = status["is_enabled"]
    is_running = status["is_running"]
    running_time = status["running_time"]
    last_log_messages = status["last_log_messages"]
    latency = check_proxy_connectivity()

    # Create status indicators
    service_status = (
        Text("●", style="green bold") if is_running else Text("●", style="red bold")
    )
    service_text = Text(
        " Running" if is_running else " Stopped",
        style="green bold" if is_running else "red bold",
    )

    enabled_status = (
        Text("●", style="green bold") if is_enabled else Text("●", style="yellow bold")
    )
    enabled_text = Text(
        " Enabled" if is_enabled else " Disabled",
        style="green bold" if is_enabled else "yellow bold",
    )

    connectivity_status = (
        Text("●", style="red bold")
        if latency == -2
        else Text("●", style="yellow bold")
        if latency == -1
        else Text("●", style="green bold")
    )
    connectivity_text = Text(
        " Failed"
        if latency == -2
        else f" {latency}ms"
        if latency != -1
        else " >1000ms",
        style="red bold"
        if latency == -2
        else "yellow bold"
        if latency == -1
        else "green bold",
    )

    # Create status table
    status_table = Table(show_header=False, box=None, padding=(0, 1))
    status_table.add_column("Status", style="bold")
    status_table.add_column("Value")

    status_table.add_row("Service:", service_status + service_text)
    status_table.add_row("Auto-start:", enabled_status + enabled_text)
    status_table.add_row("Connectivity:", connectivity_status + connectivity_text)

    status_table.add_row("Uptime:", Text(running_time, style="cyan"))

    status_table.add_row("Port:", Text(str(settings.mihomo.port), style="cyan"))
    status_table.add_row("API Port:", Text(str(settings.mihomo.api_port), style="cyan"))

    # Create log table if there are logs
    log_panel = None
    if last_log_messages:
        log_table = Table(show_header=False, box=None, padding=(0, 1))
        log_table.add_column("Logs", style="dim")

        for log in last_log_messages:
            log_table.add_row(log)

        log_panel = Panel(
            log_table,
            title="[bold]Recent Logs",
            border_style="blue",
        )

    # Combine panels
    status_panel = Panel(
        status_table,
        title="[bold]Proxy Status",
        border_style="green"
        if is_running and latency > 0
        else "yellow"
        if is_running
        else "red",
    )

    # Print panels
    console.print(status_panel)
    if log_panel:
        console.print(log_panel)


@cli.command("enable")
def enable() -> None:
    """Enable the Mimamori service."""
    try:
        enable_service()
        console.print("[green]Service enabled successfully.")
    except Exception as e:
        console.print(f"[bold red]Error enabling service: [/bold red]{e}")
        sys.exit(1)


@cli.command("disable")
def disable() -> None:
    """Disable the Mimamori service."""
    try:
        disable_service()
        console.print("[green]Service disabled successfully.")
    except Exception as e:
        console.print(f"[bold red]Error disabling service: [/bold red]{e}")
        sys.exit(1)


@cli.command("start")
def start() -> None:
    """Start the Mimamori service."""
    try:
        start_service()
        console.print("[green]Service started successfully.")
    except Exception as e:
        console.print(f"[bold red]Error starting service: [/bold red]{e}")
        sys.exit(1)


@cli.command("stop")
def stop() -> None:
    """Stop the Mimamori service."""
    try:
        stop_service()
        console.print("[green]Service stopped successfully.")
    except Exception as e:
        console.print(f"[bold red]Error stopping service: [/bold red]{e}")
        sys.exit(1)


@cli.command("restart")
def restart() -> None:
    """Restart the Mimamori service."""
    try:
        restart_service()
        console.print("[green]Service restarted successfully.")
    except Exception as e:
        console.print(f"[bold red]Error restarting service: [/bold red]{e}")
        sys.exit(1)


@cli.command("reload")
def reload() -> None:
    """Apply the latest configuration."""
    stop_service()
    with console.status("[bold]Generating mihomo config..."):
        _generate_mihomo_config()
        settings.save_to_file()
    start_service()


@cli.command("update")
def update() -> None:
    """Update Mihomo binary."""
    try:
        version = settings.mihomo.version
        binary_path = Path(settings.mihomo.binary_path)

        if version == "latest":
            version = get_latest_version()
        platform_name, arch_name = get_system_info()

        download_mihomo(
            platform_name, arch_name, version, binary_path, show_progress=True
        )

        console.print(f"[green]Downloaded Mihomo {version} to {binary_path}")
        console.print("[green]Update completed successfully!")
    except Exception as e:
        console.print(f"[bold red]Error updating Mihomo: [/bold red]{e}")
        sys.exit(1)


@cli.group("config")
def config() -> None:
    """Configuration management."""
    pass


@config.command("show")
def config_show() -> None:
    """Show current configuration."""
    try:
        config_dict = settings.model_dump()

        console.print("[bold]Current Configuration:")
        console.print(config_dict)
    except Exception as e:
        console.print(f"[bold red]Error showing configuration: [/bold red]{e}")
        sys.exit(1)


@cli.command("cleanup")
def cleanup() -> None:
    """Remove all configuration files and binaries, stop service, and delete the service file."""
    try:
        status = get_service_status()
        is_running = status["is_running"]
        is_enabled = status["is_enabled"]

        # Stop service if it is running
        if is_running:
            stop_service()
            console.print("[green]Stopped service successfully.")

        # Disable service if it is enabled
        if is_enabled:
            disable_service()
            console.print("[green]Disabled service successfully.")

        # Remove service file
        if SERVICE_FILE_PATH.exists():
            SERVICE_FILE_PATH.unlink()
            console.print(f"[green]Deleted service file at {SERVICE_FILE_PATH}")

        # Remove configuration files
        config_path = MIMAMORI_CONFIG_PATH
        config_dir = config_path.parent
        if config_dir.exists():
            shutil.rmtree(config_dir)
            console.print(f"[green]Deleted Mimamori config directory at {config_dir}")

        # Remove Mihomo config directory
        mihomo_config_dir = Path(settings.mihomo.config_dir)
        if mihomo_config_dir.exists():
            shutil.rmtree(mihomo_config_dir)
            console.print(
                f"[green]Deleted Mihomo config directory at {mihomo_config_dir}"
            )

        # Remove Mihomo binary
        binary_path = Path(settings.mihomo.binary_path)
        if binary_path.exists():
            binary_path.unlink()
            console.print(f"[green]Deleted Mihomo binary at {binary_path}")

        # Remove Mimamori aliases
        shell, rc_path = get_shell_rc_path()
        if not rc_path:
            console.print(
                "[yellow]Unsupported shell {shell}. Please remove the aliases manually."
            )
        elif remove_aliases(rc_path):
            console.print(f"[green]Deleted Mimamori aliases in {rc_path}")
        else:
            console.print(
                f"[yellow]No Mimamori aliases found in {rc_path}. Maybe you should remove them manually."
            )

        console.print("[bold green]Cleanup completed successfully!")
    except Exception as e:
        console.print(f"[bold red]Error during cleanup: [/bold red]{e}")
        sys.exit(1)


@cli.group("proxy")
def proxy() -> None:
    """Proxy environment management."""
    pass


@proxy.command("export")
def proxy_export() -> None:
    """Output commands to set proxy environment variables."""
    commands = generate_export_commands(settings.mihomo.port)
    for cmd in commands:
        print(cmd)


@proxy.command("unset")
def proxy_unset() -> None:
    """Output commands to unset proxy environment variables."""
    commands = generate_unset_commands()
    for cmd in commands:
        print(cmd)


@proxy.command("run", context_settings={"ignore_unknown_options": True})
@click.argument("command", nargs=-1, required=True)
def proxy_run(command: List[str]) -> None:
    """Run a command with proxy environment variables."""
    if not command:
        console.print("[bold red]Error: No command specified.")
        sys.exit(1)

    if not is_service_running():
        console.print(
            "[yellow]Warning: Mimamori service is not running. "
            "The proxy may not work correctly.[/yellow]"
        )

    exit_code = run_with_proxy_env(settings.mihomo.port, command)
    sys.exit(exit_code)


@cli.command("select")
def select() -> None:
    """Select a proxy from the GLOBAL proxy group."""
    if not is_service_running():
        console.print(
            "[bold red]Error: Mimamori service is not running. "
            "Please start the service first with 'mim start'."
        )
        sys.exit(1)

    api_port = settings.mihomo.api_port
    api_base_url = f"http://127.0.0.1:{api_port}"
    mihomo_api = MihomoAPI(api_base_url)

    # Fetch proxy list
    try:
        proxies = mihomo_api.get_proxies("GLOBAL")

        if not proxies:
            console.print("[bold red]Error:[/bold red] No proxies found.")
            sys.exit(1)
    except requests.RequestException as e:
        console.print(f"[bold red]Error fetching proxy list:[/bold red] {e}")
        sys.exit(1)

    # Test latency for each proxy
    with console.status("[bold]Testing proxy latencies...") as status:

        def update_progress(current: int, total: int):
            status.update(f"[bold]Testing proxy latencies... ({current}/{total})")

        proxy_latencies = mihomo_api.test_proxy_latencies(proxies, update_progress)

    _display_proxy_table(proxy_latencies)
    console.print()

    # Get current selection
    current_proxy = mihomo_api.get_current_proxy("GLOBAL")
    console.print(f"Current selection: [bold cyan]{current_proxy}[/bold cyan]")

    # Let user select a proxy
    while True:
        selection = Prompt.ask("[bold]Enter proxy number to select")

        try:
            idx = int(selection) - 1
            if idx < 0 or idx >= len(proxy_latencies):
                console.print("[bold red]Selection out of range. Please try again.")
                continue

            selected_proxy = list(proxy_latencies.keys())[idx]

            # Update the selection
            mihomo_api.select_proxy("GLOBAL", selected_proxy)

            console.print(
                f"[bold green]Successfully switched to proxy: {selected_proxy}"
            )
            break
        except ValueError:
            console.print("[bold red]Invalid input. Please enter a number.")
            continue
        except requests.RequestException as e:
            console.print(f"[bold red]Error updating proxy selection: [/bold red]{e}")
            sys.exit(1)


def main() -> None:
    """Main entry point."""
    try:
        cli()
    except Exception as e:
        console.print(f"[bold red]Unexpected error: [/bold red]{e}")
        console.print(traceback.format_exc())
        sys.exit(1)


def _display_proxy_table(proxy_latencies: Dict[str, int]):
    """
    Display a grid of proxies with their latencies.

    Args:
        proxy_latencies: Dictionary mapping proxy names to latencies
    """
    # Get terminal width
    console_width = max(console.width, 80)

    # Determine optimal grid dimensions based on terminal width
    card_width = 20
    padding = 2
    max_columns = max(1, (console_width + padding) // (card_width + padding))

    # Create grid for proxies
    proxy_grid = Table.grid(expand=True)
    for _ in range(max_columns):
        proxy_grid.add_column(ratio=1)

    # Add each proxy to the grid
    current_row = []
    for idx, (proxy, latency) in enumerate(proxy_latencies.items()):
        # Format the card content
        latency_str = f"{latency}ms" if latency > 0 else "Timeout"
        latency_style = (
            "green"
            if 0 < latency < 200
            else "yellow"
            if 200 <= latency < 500
            else "red"
        )

        # Create a compact panel
        proxy_text = Text(proxy, overflow="fold")
        latency_text = Text(latency_str, style=latency_style)

        table = Table.grid(expand=True, padding=(0, 1))
        table.add_column()
        table.add_column(justify="right")
        table.add_row(proxy_text, latency_text)

        card = Panel(table, title=f"#{idx + 1}", title_align="left", border_style="dim")

        current_row.append(card)

        # When we've filled a row or reached the end, add it to the grid
        if len(current_row) == max_columns or idx == len(proxy_latencies) - 1:
            # Pad the row with empty strings if needed
            while len(current_row) < max_columns:
                current_row.append("")
            proxy_grid.add_row(*current_row)
            current_row = []

    console.print(proxy_grid)


def _generate_mihomo_config():
    mihomo_config_path = Path(settings.mihomo.config_dir) / "config.yaml"
    port = settings.mihomo.port
    api_port = settings.mihomo.api_port
    subscription = settings.mihomo.subscription

    # Check if the port is available and use a different port if it is not
    if not is_service_running():
        new_port = check_port_availability(port)
        if new_port != port:
            console.print(
                f"[yellow]Port {port} is already in use. Using port {new_port} instead."
            )
            port = new_port
            settings.mihomo.port = port

        new_api_port = check_port_availability(api_port)
        if new_api_port != api_port:
            console.print(
                f"[yellow]API port {api_port} is already in use. Using port {new_api_port} instead."
            )
            api_port = new_api_port
            settings.mihomo.api_port = api_port

    # Create the config
    create_mihomo_config(
        mihomo_config_path,
        subscription=subscription,
        port=port,
        api_port=api_port,
    )


if __name__ == "__main__":
    main()
