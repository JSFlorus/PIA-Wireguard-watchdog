#!/usr/bin/env python3
import subprocess
from pathlib import Path
from shlex import quote

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path("/opt/pia-wg-watchdog")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    pia_helper_url: str = Field(alias="PIA_HELPER_URL")
    pia_helper_token: SecretStr = Field(alias="PIA_HELPER_TOKEN")
    pia_creds_conf_path: str = Field(
        default="/opt/pia-wg-watchdog/configs/wg0-creds.conf",
        alias="PIA_CREDS_CONF_PATH",
    )


def main() -> None:
    settings = Settings()
    output = Path(settings.pia_creds_conf_path)
    tmp = output.with_suffix(output.suffix + ".tmp")
    output.parent.mkdir(parents=True, exist_ok=True)

    cmd = (
        "curl -fsS "
        "-X POST "
        f"-H {quote('Authorization: Bearer ' + settings.pia_helper_token.get_secret_value())} "
        f"{quote(settings.pia_helper_url)} "
        f"-o {quote(str(tmp))}"
    )

    print(f"Fetching WireGuard creds from {settings.pia_helper_url}", flush=True)

    result = subprocess.run(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=180,
    )

    if result.returncode != 0:
        print(result.stdout, flush=True)
        raise SystemExit("Failed to fetch WireGuard creds")

    text = tmp.read_text()
    if "[Interface]" not in text or "[Peer]" not in text:
        tmp.unlink(missing_ok=True)
        raise SystemExit("Downloaded file does not look like a WireGuard config")

    tmp.chmod(0o600)
    tmp.replace(output)
    output.chmod(0o600)

    print(f"Wrote creds to {output}", flush=True)


if __name__ == "__main__":
    main()
