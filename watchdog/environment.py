#!/opt/pia-wg-watchdog/venv/bin/python
from pathlib import Path
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # ---------- User config ----------

    pia_user: str = Field(alias="PIA_USER")
    pia_pass: SecretStr = Field(alias="PIA_PASS")

    autoconnect: bool = Field(default=True, alias="AUTOCONNECT")
    preferred_region: str | None = Field(default=None, alias="PREFERRED_REGION", )

    vpn_dns: str = Field(default="10.0.0.244", alias="VPN_DNS")
    fallback_dns: str = Field(default="1.1.1.1", alias="FALLBACK_DNS")

    check_interval: int = Field(default=30, alias="CHECK_INTERVAL",)

    max_failures: int = Field(default=5,alias="MAX_FAILURES",)

    setup_cooldown: int = Field(default=300,alias="SETUP_COOLDOWN",)

    ping_targets: str = Field(default="1.1.1.1,1.0.0.1",alias="PING_TARGETS",)

    # ---------- Derived paths ----------

    @property
    def watchdog_dir(self) -> Path:
        return Path(__file__).resolve().parent

    @property
    def repo_dir(self) -> Path:
        return self.watchdog_dir.parent

    @property
    def config_dir(self) -> Path:
        return self.repo_dir / "configs"

    @property
    def scripts_dir(self) -> Path:
        return self.watchdog_dir / "scripts"

    @property
    def manual_connections_dir(self) -> Path:
        return self.repo_dir / "manual-connections"

    @property
    def pia_conf(self) -> Path:
        return self.config_dir / "pia.conf"

    @property
    def wg_conf(self) -> Path:
        return self.config_dir / "wg0.conf"

    @property
    def generate_pia_conf(self) -> Path:
        return self.watchdog_dir / "generate_pia_conf.py"

    @property
    def wg_gen(self) -> Path:
        return self.scripts_dir / "wg0-gen"

    @property
    def wg_tables(self) -> Path:
        return self.scripts_dir / "wg0-tables"

    # ---------- Properties ----------

    @property
    def ping_target_list(self) -> list[str]:
        return [
            target.strip()
            for target in self.ping_targets.split(",")
            if target.strip()
        ]

ENV = Environment()