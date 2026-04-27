#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path
from shlex import quote

from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path("/home/automation/pia/helper")
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    pia_user: SecretStr = Field(alias="PIA_USER")
    pia_pass: SecretStr = Field(alias="PIA_PASS")
    helper_token: SecretStr = Field(alias="HELPER_TOKEN")

    pia_manual_connections_dir: str = Field(
        default="/home/automation/pia/manual-connections",
        alias="PIA_MANUAL_CONNECTIONS_DIR",
    )
    pia_output_conf: str = Field(
        default="/home/automation/pia/helper/wg0-creds.conf",
        alias="PIA_OUTPUT_CONF",
    )

    vpn_protocol: str = Field(default="wireguard", alias="VPN_PROTOCOL")
    disable_ipv6: str = Field(default="yes", alias="DISABLE_IPV6")
    dip_token: str = Field(default="no", alias="DIP_TOKEN")
    autoconnect: str = Field(default="true", alias="AUTOCONNECT")
    pia_pf: str = Field(default="false", alias="PIA_PF")
    pia_dns: str = Field(default="false", alias="PIA_DNS")
    pia_connect: str = Field(default="false", alias="PIA_CONNECT")

    server_host: str = Field(default="0.0.0.0", alias="SERVER_HOST")
    server_port: int = Field(default=9090, alias="SERVER_PORT")
settings = Settings()
app = FastAPI()


def check_token(authorization: str | None) -> None:
    expected = f"Bearer {settings.helper_token.get_secret_value()}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def run_pia_setup() -> Path:
    pia_dir = Path(settings.pia_manual_connections_dir)
    output_conf = Path(settings.pia_output_conf)

    if not pia_dir.exists():
        raise RuntimeError(f"Missing PIA directory: {pia_dir}")

    run_setup = pia_dir / "run_setup.sh"
    if not run_setup.exists():
        raise RuntimeError(f"Missing run_setup.sh: {run_setup}")

    output_conf.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(["chmod", "+x", str(run_setup)], check=False)

    cmd = (
        f"VPN_PROTOCOL={quote(settings.vpn_protocol)} "
        f"DISABLE_IPV6={quote(settings.disable_ipv6)} "
        f"DIP_TOKEN={quote(settings.dip_token)} "
        f"AUTOCONNECT={quote(settings.autoconnect)} "
        f"PIA_PF={quote(settings.pia_pf)} "
        f"PIA_DNS={quote(settings.pia_dns)} "
        f"PIA_CONNECT={quote(settings.pia_connect)} "
        f"PIA_USER={quote(settings.pia_user.get_secret_value())} "
        f"PIA_PASS={quote(settings.pia_pass.get_secret_value())} "
        f"PIA_CONF_PATH={quote(str(output_conf))} "
        "./run_setup.sh"
    )

    result = subprocess.run(
        cmd,
        cwd=pia_dir,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=180,
    )

    if result.returncode != 0:
        raise RuntimeError(f"PIA setup failed:\n{result.stdout}")

    if not output_conf.exists():
        raise RuntimeError(f"PIA setup did not create {output_conf}")

    output_conf.chmod(0o600)
    return output_conf


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/refresh")
def refresh(authorization: str | None = Header(default=None)):
    check_token(authorization)

    try:
        conf_path = run_pia_setup()
        conf_text = conf_path.read_text()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return Response(content=conf_text, media_type="text/plain")
