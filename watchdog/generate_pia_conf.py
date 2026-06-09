#!/opt/pia-wg-watchdog/venv/bin/python

import os
import subprocess

from environment import ENV


def conf_generate() -> None:
    ENV.config_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.update(
        {
            "VPN_PROTOCOL": "wireguard",
            "DISABLE_IPV6": "yes",
            "DIP_TOKEN": "no",
            "PIA_CONNECT": "false",
            "PIA_CONF_PATH": str(ENV.pia_conf),
            "PIA_PF": "false",
            "PIA_DNS": "true",
            "PIA_USER": ENV.pia_user,
            "PIA_PASS": ENV.pia_pass.get_secret_value(),
        }
    )

    if ENV.autoconnect:
        env["AUTOCONNECT"] = "true"
        env.pop("PREFERRED_REGION", None)
        print("Using AUTOCONNECT=true", flush=True)
    else:
        if not ENV.preferred_region:
            raise SystemExit("PREFERRED_REGION must be set when AUTOCONNECT=false")

        env["AUTOCONNECT"] = "false"
        env["PREFERRED_REGION"] = ENV.preferred_region
        print(f"Using PREFERRED_REGION={ENV.preferred_region}", flush=True)

    print(f"Generating PIA WireGuard config at {ENV.pia_conf}...", flush=True)

    result = subprocess.run(
        ["./run_setup.sh"],
        cwd=ENV.manual_connections_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=600,
    )

    print(result.stdout, flush=True)

    if result.returncode != 0:
        raise SystemExit(f"run_setup.sh failed with exit code {result.returncode}")

    if not ENV.pia_conf.exists():
        raise SystemExit(f"Expected config not found: {ENV.pia_conf}")

    text = ENV.pia_conf.read_text()
    if "[Interface]" not in text or "[Peer]" not in text:
        raise SystemExit(f"{ENV.pia_conf} does not look like a WireGuard config")

    ENV.pia_conf.chmod(0o600)

    print(f"PIA WireGuard config ready: {ENV.pia_conf}", flush=True)


