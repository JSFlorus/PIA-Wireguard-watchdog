#!/opt/PIA-Wireguard-watchdog/venv/bin/python

import subprocess
import time
from pathlib import Path
import os
from environment import ENV
from generate_pia_conf import conf_generate
import sys

last_repair = 0

# PIA authentication/config-generation protection.
CONF_GENERATE_TIMEOUT = 90
CONF_GENERATE_RETRIES = 3
CONF_GENERATE_RETRY_DELAY = 10

def run(
    cmd: list[str],
    env: dict[str, str] | None = None,
    timeout: int | None = None,
) -> bool:
    print(f"Running: {' '.join(cmd)}", flush=True)

    try:
        result = subprocess.run(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        print(
            f"Command timed out after {timeout} seconds: {' '.join(cmd)}",
            flush=True,
        )
        return False
    except Exception as exc:
        print(
            f"Command failed to execute: {' '.join(cmd)}: {exc}",
            flush=True,
        )
        return False

    if result.stdout:
        print(result.stdout, flush=True)

    if result.returncode != 0:
        print(
            f"Command exited with code {result.returncode}: {' '.join(cmd)}",
            flush=True,
        )
        return False

    return True


def interface_exists(name: str) -> bool:
    return Path(f"/sys/class/net/{name}").exists()


def ping_ok() -> bool:
    for target in ENV.ping_target_list:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "3", target],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        if result.returncode == 0:
            return True

    return False


def dns_ok() -> bool:
    resolv = Path("/etc/resolv.conf")

    if not resolv.exists():
        return False

    try:
        lines = resolv.read_text().splitlines()
    except Exception as exc:
        print(f"Unable to read /etc/resolv.conf: {exc}", flush=True)
        return False

    nameservers = []

    for line in lines:
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        if line.startswith("nameserver "):
            nameservers.append(line.split(maxsplit=1)[1])

    return bool(nameservers) and nameservers[0] == ENV.vpn_dns


def ensure_dns() -> None:
    expected = (
        f"nameserver {ENV.vpn_dns}\n"
        f"nameserver {ENV.fallback_dns}\n"
    )

    resolv = Path("/etc/resolv.conf")

    try:
        current = resolv.read_text()
    except Exception:
        current = ""

    if current != expected:
        print("Repairing DNS configuration", flush=True)

        try:
            resolv.write_text(expected)
        except Exception as exc:
            print(f"Failed to repair DNS configuration: {exc}", flush=True)


def prepare_auth_dns() -> None:
    """
    Put the fallback DNS server first while PIA authentication is running.

    If wg0 is down, the VPN-provided DNS server may itself be unreachable.
    That can cause PIA authentication to appear to hang while DNS requests
    wait for timeouts.
    """
    resolv = Path("/etc/resolv.conf")

    expected = (
        f"nameserver {ENV.fallback_dns}\n"
        f"nameserver {ENV.vpn_dns}\n"
    )

    try:
        current = resolv.read_text()
    except Exception:
        current = ""

    if current != expected:
        print("Using fallback DNS for PIA authentication", flush=True)

        try:
            resolv.write_text(expected)
        except Exception as exc:
            print(f"Failed to prepare authentication DNS: {exc}", flush=True)


def generate_pia_config() -> bool:
    """
    Run generate_pia_conf.py in a separate process.

    This is deliberately NOT imported and called directly. If PIA's
    authentication process hangs, subprocess.run() can kill the child
    after CONF_GENERATE_TIMEOUT rather than freezing this watchdog.
    """
    script = Path(__file__).resolve().with_name("generate_pia_conf.py")

    if not script.exists():
        print(f"PIA config generator not found: {script}", flush=True)
        return False

    prepare_auth_dns()

    for attempt in range(1, CONF_GENERATE_RETRIES + 1):
        print(
            f"Generating PIA configuration "
            f"(attempt {attempt}/{CONF_GENERATE_RETRIES})",
            flush=True,
        )

        if run(
            [sys.executable, str(script)],
            timeout=CONF_GENERATE_TIMEOUT,
        ):
            print("PIA configuration generated successfully", flush=True)
            return True

        if attempt < CONF_GENERATE_RETRIES:
            print(
                f"PIA configuration attempt failed; "
                f"retrying in {CONF_GENERATE_RETRY_DELAY} seconds",
                flush=True,
            )
            time.sleep(CONF_GENERATE_RETRY_DELAY)

    print(
        "PIA configuration generation failed after all retries",
        flush=True,
    )
    return False


def repair_wg0() -> bool:
    global last_repair

    now = time.time()

    if now - last_repair < ENV.setup_cooldown:
        remaining = int(ENV.setup_cooldown - (now - last_repair))

        print(
            f"Repair skipped: cooldown active "
            f"({remaining}s remaining)",
            flush=True,
        )
        return False

    last_repair = now

    print("Repairing wg0...", flush=True)

    # Make sure any existing interface is removed first.
    run(
        ["wg-quick", "down", str(ENV.wg_conf)],
        timeout=30,
    )

    #
    # CRITICAL CHANGE:
    #
    # generate_pia_conf.py is now a child process with a timeout.
    # A stuck PIA authentication can no longer freeze the watchdog.
    #
    if not generate_pia_config():
        print("PIA configuration generation failed", flush=True)
        return False

    env = os.environ.copy()
    env.update(
        {
            "LAN_IF": ENV.lan_if,
            "VPN_IF": ENV.vpn_if,
            "LAN_GW": ENV.lan_gw,
            "VPN_NET": ENV.vpn_net,
            "VPN_HOST": ENV.vpn_host,
            "VPN_DNS": ENV.vpn_dns,
            "LOCAL_NETS": ENV.local_nets,
            "OUTBOUND_NETS": ENV.outbound_nets,
            "FALLBACK_DNS": ENV.fallback_dns,
        }
    )

    if not run(
        [str(ENV.wg_tables)],
        env=env,
        timeout=30,
    ):
        print("wg0-tables failed", flush=True)
        return False

    if not run(
        [str(ENV.wg_gen)],
        env=env,
        timeout=30,
    ):
        print("wg0-gen failed", flush=True)
        return False

    if not run(
        ["wg-quick", "up", str(ENV.wg_conf)],
        timeout=30,
    ):
        print("wg-quick up failed", flush=True)
        return False

    ensure_dns()

    if not dns_ok():
        print("DNS validation failed", flush=True)
        return False

    if not ping_ok():
        print("wg0 came up, but ping still failed", flush=True)
        return False

    print("wg0 repaired successfully", flush=True)
    return True


def main() -> None:
    failures = 0

    print("wg0 watchdog started", flush=True)

    while True:
        try:
            if not interface_exists("wg0"):
                print("wg0 interface missing", flush=True)

                if repair_wg0():
                    failures = 0
                else:
                    print(
                        "wg0 repair unsuccessful; watchdog will retry",
                        flush=True,
                    )

                time.sleep(ENV.check_interval)
                continue

            if not dns_ok():
                print(
                    "DNS configuration drift detected",
                    flush=True,
                )
                ensure_dns()

            if ping_ok():
                failures = 0
                print("VPN check OK", flush=True)

            else:
                failures += 1

                print(
                    f"VPN check failed "
                    f"{failures}/{ENV.max_failures}",
                    flush=True,
                )

                if failures >= ENV.max_failures:
                    repair_wg0()
                    failures = 0

        except Exception as exc:
            #
            # Never allow an unexpected Python exception to permanently
            # kill the watchdog service.
            #
            print(
                f"Unexpected watchdog error: {exc}",
                flush=True,
            )

        time.sleep(ENV.check_interval)


if __name__ == "__main__":
    main()