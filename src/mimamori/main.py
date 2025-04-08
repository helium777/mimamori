import os
import sys
import shutil
from pathlib import Path
from typing import List, Optional
import click
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from mimamori.globals import MIMAMORI_CONFIG_PATH, SERVICE_FILE_PATH

from . import __version__
from .settings import settings
from .download import download_mihomo, get_latest_version, get_system_info
from .mihomo_config import create_mihomo_config
from .utils import (
    aliases_already_exist,
    check_port_availability,
    check_proxy_connectivity,
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


console = Console()


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
        elif Confirm.ask(
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
        if Confirm.ask(
            "[bold]Do you want to create a service file to keep Mihomo running?"
        ):
            with console.status("[bold]Creating service file..."):
                create_service_file(SERVICE_FILE_PATH)
                console.print(f"[green]Created service file at {SERVICE_FILE_PATH}")

                reload_daemon()
                enable_service()
                start_service()

        console.print()
        # 4. Set up shell aliases
        console.print("""[bold]Recommended shell aliases:[/bold]
[cyan]pon[/cyan]  - Enable proxy in current shell  (eval $(mim proxy export))
[cyan]poff[/cyan] - Disable proxy when done        (eval $(mim proxy unset))
[cyan]pp[/cyan]   - Run commands with proxy enabled (mim proxy run)""")
        need_setup_aliases = Confirm.ask(
            "[bold]Do you want to set up these shell aliases?"
        )

        if need_setup_aliases:
            shell = os.environ.get("SHELL", "")
            aliases_enabled = False

            aliases_content = (
                "\n### Mimamori aliases ###\n"
                "alias pon='eval $(mim proxy export)'\n"
                "alias poff='eval $(mim proxy unset)'\n"
                "alias pp='mim proxy run'\n"
            )

            def setup_aliases_for_shell(rc_path):
                if aliases_already_exist(rc_path):
                    console.print(f"[yellow]Aliases already exist in ~/{rc_path.name}")
                    return True
                else:
                    with open(rc_path, "a") as f:
                        f.write(aliases_content)
                    console.print(f"[green]Added aliases to ~/{rc_path.name}")
                    return True

            if "bash" in shell:
                aliases_enabled = setup_aliases_for_shell(Path.home() / ".bashrc")
            elif "zsh" in shell:
                aliases_enabled = setup_aliases_for_shell(Path.home() / ".zshrc")
            else:
                console.print(
                    "[yellow]Unsupported shell. Please add the aliases manually."
                )

        # 5. Save settings
        settings.save_to_file()

        console.print()
        # 6. Print completion message
        console.print("[green]🥳 Setup completed successfully!")
        console.print("\nNext steps:")
        if aliases_enabled:
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
                "- Run [cyan]mim proxy export[/cyan] to enable the proxy in current shell"
            )
            console.print(
                "- Run [cyan]mim proxy unset[/cyan] to disable the proxy in current shell"
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
    # TODO: refactor this
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
        Text("●", style="green bold") if latency != -1 else Text("●", style="red bold")
    )
    connectivity_text = Text(
        f" {latency}ms" if latency != -1 else " >1000ms",
        style="green bold" if latency != -1 else "red bold",
    )

    # Create status table
    status_table = Table(show_header=False, box=None, padding=(0, 1))
    status_table.add_column("Status", style="bold")
    status_table.add_column("Value")

    status_table.add_row("Service:", service_status + service_text)
    status_table.add_row("Auto-start:", enabled_status + enabled_text)
    status_table.add_row("Connectivity:", connectivity_status + connectivity_text)

    if running_time:
        status_table.add_row("Uptime:", Text(running_time, style="cyan"))

    status_table.add_row("Port:", Text(str(settings.mihomo.port), style="cyan"))
    status_table.add_row("API Port:", Text(str(settings.mihomo.api_port), style="cyan"))

    # Create log table if there are logs
    log_panel = None
    if last_log_messages and is_running:
        log_table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        log_table.add_column("Logs", style="dim")

        for log in last_log_messages[-5:]:  # Show last 5 log messages
            log_table.add_row(log)

        log_panel = Panel(
            log_table,
            title="[bold]Recent Logs",
            border_style="blue",
            expand=False,
        )

    # Combine panels
    status_panel = Panel(
        status_table,
        title="[bold]Proxy Status",
        border_style="green"
        if is_running and latency != -1
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
    """Remove all configuration files and binaries, stop service."""
    try:
        status = get_service_status()
        is_running = status["is_running"]
        is_enabled = status["is_enabled"]

        if is_running:
            stop_service()
            console.print("[green]Stopped service successfully.")

        if is_enabled:
            disable_service()
            console.print("[green]Disabled service successfully.")

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


def main() -> None:
    """Main entry point."""
    try:
        cli()
    except Exception as e:
        console.print(f"[bold red]Unexpected error: [/bold red]{e}")
        sys.exit(1)


def _generate_mihomo_config():
    mihomo_config_path = Path(settings.mihomo.config_dir) / "config.yaml"
    config_preset = settings.mihomo.config_preset
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
        config_preset=config_preset,
        subscription=subscription,
        port=port,
        api_port=api_port,
    )


if __name__ == "__main__":
    main()
