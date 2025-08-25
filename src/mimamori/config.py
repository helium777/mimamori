from pathlib import Path
from typing import Any

import tomlkit
from pydantic import Field, ValidationError
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from .console import console
from .globals import MIMAMORI_CONFIG_PATH


class MihomoSettings(BaseSettings):
    """Settings for the Mihomo binary and configuration."""

    binary_path: str = Field(default=str(Path.home() / ".local" / "bin" / "mihomo"))
    config_dir: str = Field(default=str(Path.home() / ".config" / "mihomo"))
    version: str = Field(default="latest")
    subscription: str = Field(default="")
    port: int = Field(default=7890)
    api_port: int = Field(default=9090)


class Settings(BaseSettings):
    """Main settings for Mimamori."""

    model_config = SettingsConfigDict(toml_file=MIMAMORI_CONFIG_PATH)

    mihomo: MihomoSettings = Field(default_factory=MihomoSettings)
    github_proxy: str = Field(default="https://ghfast.top/")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings, TomlConfigSettingsSource(settings_cls))


class Config:
    """Config for Mimamori."""

    def __init__(self):
        self.settings = Settings()

    def get_all(self) -> dict:
        """Get all config values."""
        return self.settings.model_dump()

    def get(self, key: str) -> Any:
        """Get a specific config value.

        key is the path to the setting, e.g. 'mihomo.binary_path'
        """
        keys = key.split(".")
        current = self.settings

        for k in keys:
            if hasattr(current, k):
                current = getattr(current, k)
            else:
                raise KeyError(f"Config value '{key}' not found")

        return current

    def set(self, key: str, value: Any):
        """Set a specific config value and persist it to the config file.

        key is the path to the setting, e.g. 'mihomo.binary_path'
        """
        keys = key.split(".")
        new_settings = self.settings.model_dump()

        # Navigate to the parent of the target attribute
        current = new_settings
        for k in keys[:-1]:
            if k in current:
                current = current.get(k)
            else:
                raise KeyError(f"Config path '{key}' not found")
        current[keys[-1]] = value
        new_settings = Settings(**new_settings)

        # Persist the key-value pair to the config file
        self._persist_to_file(keys, value)

        self.settings = new_settings

    # --- internal methods ---

    def _get_update_dict(self, keys: list[str], value: Any) -> dict:
        return (
            value
            if len(keys) == 0
            else {keys[0]: self._get_update_dict(keys[1:], value)}
        )

    def _persist_to_file(self, keys: list[str], value: Any) -> None:
        self._ensure_config_file()
        text = MIMAMORI_CONFIG_PATH.read_text()
        doc = tomlkit.parse(text)

        # Update the value in the document
        current = doc
        for k in keys[:-1]:
            if k not in current:
                current[k] = tomlkit.table()
            current = current[k]
        current[keys[-1]] = value

        MIMAMORI_CONFIG_PATH.write_text(tomlkit.dumps(doc))

    def _ensure_config_file(self) -> None:
        MIMAMORI_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not MIMAMORI_CONFIG_PATH.exists():
            MIMAMORI_CONFIG_PATH.touch()


try:
    mim_config = Config()
except ValidationError:
    console.print("[bold red]Error:[/bold red] Broken config file.")
    raise
