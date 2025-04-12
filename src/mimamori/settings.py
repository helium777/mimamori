from pathlib import Path
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)
from pydantic import Field
import tomlkit

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

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (TomlConfigSettingsSource(settings_cls),)

    def save_to_file(self) -> None:
        """Save the current settings to the config file, preserving format and comments."""
        MIMAMORI_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Try to load existing file to preserve comments and format
        if MIMAMORI_CONFIG_PATH.exists():
            with open(MIMAMORI_CONFIG_PATH, "r") as f:
                doc = tomlkit.parse(f.read())
        else:
            doc = tomlkit.document()

        # Update with current settings
        config_dict = self.model_dump()

        def update_toml_doc(doc, new_dict):
            for key, value in new_dict.items():
                if isinstance(value, dict):
                    if key not in doc:
                        doc[key] = tomlkit.table()
                    update_toml_doc(doc[key], value)
                else:
                    doc[key] = value

        # Update all settings recursively
        update_toml_doc(doc, config_dict)

        # Write back to file
        with open(MIMAMORI_CONFIG_PATH, "w") as f:
            f.write(tomlkit.dumps(doc))
