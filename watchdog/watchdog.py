#!/opt/pia-wg-watchdog/venv/bin/python
import subprocess
import time
from pathlib import Path

from environment import ENV
from generate_pia_conf import conf_generate


last_repair = 0


def run(cmd: list[str]) -> bool:
    print(f"Running: {' '.join(cmd)}", flush=True)

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    if result.stdout:
        print(result.stdout, flush=True)

    return result.returncode == 0


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

    for line in resolv.read_text().splitlines():
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        return line == f"nameserver {ENV.vpn_dns}"

    return False


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
        resolv.write_text(expected)


def repair_wg0() -> bool:
    global last_repair

    now = time.time()
    if now - last_repair < ENV.setup_cooldown:
        print("Repair skipped: cooldown active", flush=True)
        return False

    last_repair = now

    print("Repairing wg0...", flush=True)

    subprocess.run(
        ["wg-quick", "down", str(ENV.wg_conf)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        conf_generate()
    except Exception as exc:
        print(f"generate_pia_conf.py failed: {exc}", flush=True)
        return False

    if not run([str(ENV.wg_gen)]):
        print("wg0-gen failed", flush=True)
        return False

    if not run([str(ENV.wg_tables)]):
        print("wg0-tables failed", flush=True)
        return False

    if not run(["wg-quick", "up", str(ENV.wg_conf)]):
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
        if not interface_exists("wg0"):
            print("wg0 interface missing", flush=True)
            repair_wg0()
            failures = 0
            time.sleep(ENV.check_interval)
            continue

        if not dns_ok():
            print("DNS configuration drift detected", flush=True)
            ensure_dns()

        if ping_ok():
            failures = 0
            print("VPN check OK", flush=True)
        else:
            failures += 1
            print(f"VPN check failed {failures}/{ENV.max_failures}", flush=True)

            if failures >= ENV.max_failures:
                repair_wg0()
                failures = 0

        time.sleep(ENV.check_interval)


if __name__ == "__main__":
    main()