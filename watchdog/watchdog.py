#!/opt/pia-wg-watchdog/venv/bin/python
import subprocess
import time
from pathlib import Path

BASE_DIR = Path("/opt/pia-wg-watchdog")

PYTHON = BASE_DIR / "venv" / "bin" / "python"
FETCH_CREDS = BASE_DIR / "scripts" / "fetch_wg0_creds.py"
WG_GEN = BASE_DIR / "scripts" / "wg0-gen"
WG_TABLES = BASE_DIR / "scripts" / "wg0-tables"
WG_CONF = BASE_DIR / "configs" / "wg0.conf"

CHECK_INTERVAL = 30
MAX_FAILURES = 5
SETUP_COOLDOWN = 300

PING_TARGETS = ["1.1.1.1", "1.0.0.1"]

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
    for target in PING_TARGETS:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "3", target],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        if result.returncode == 0:
            return True

    return False


def repair_wg0() -> bool:
    global last_repair

    now = time.time()
    if now - last_repair < SETUP_COOLDOWN:
        print("Repair skipped: cooldown active", flush=True)
        return False

    last_repair = now

    print("Repairing wg0...", flush=True)

    subprocess.run(
        ["wg-quick", "down", str(WG_CONF)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if not run([str(PYTHON), str(FETCH_CREDS)]):
        print("fetch_wg0_creds.py failed", flush=True)
        return False

    if not run([str(WG_GEN)]):
        print("wg0-gen failed", flush=True)
        return False

    if not run([str(WG_TABLES)]):
        print("wg0-tables failed", flush=True)
        return False

    if not run(["wg-quick", "up", str(WG_CONF)]):
        print("wg-quick up failed", flush=True)
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
            time.sleep(CHECK_INTERVAL)
            continue

        if ping_ok():
            failures = 0
            print("VPN check OK", flush=True)
        else:
            failures += 1
            print(f"VPN check failed {failures}/{MAX_FAILURES}", flush=True)

            if failures >= MAX_FAILURES:
                repair_wg0()
                failures = 0

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
