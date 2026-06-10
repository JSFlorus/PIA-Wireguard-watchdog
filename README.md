# PIA WireGuard Watchdog

Self-healing WireGuard watchdog for Private Internet Access (PIA).

The watchdog continuously monitors VPN connectivity and automatically regenerates WireGuard credentials, rebuilds configuration files, and reconnects the tunnel when connectivity is lost.

## Features

- Uses PIA's official manual-connections scripts
- Supports automatic lowest-latency server selection
- Supports fixed preferred regions
- Automatically regenerates WireGuard credentials
- Rebuilds WireGuard configuration files
- Monitors VPN health using configurable ping targets
- Repairs broken tunnels automatically
- Sets DNS configuration
- Runs as an OpenRC service on Alpine Linux
- Configuration through a single `.env` file


## Requirements

- Alpine Linux
- OpenRC
- WireGuard
- Python 3.12+
- PIA subscription


## Installation

Clone the repository:

```bash
git clone https://github.com/JSFlorus/PIA-Wireguard-watchdog.git
cd PIA-Wireguard-watchdog
```

Create a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r watchdog/requirements.txt
```

Clone the PIA manual-connections repository:

```bash
git clone https://github.com/pia-foss/manual-connections.git
```

## Configuration

Create `.env`:

```env
PIA_USER=p1234567
PIA_PASS=your_password

AUTOCONNECT=true

# Used when AUTOCONNECT=false
PREFERRED_REGION=ca_ontario

VPN_DNS=10.0.0.244
FALLBACK_DNS=10.10.10.1

CHECK_INTERVAL=30
MAX_FAILURES=5
SETUP_COOLDOWN=300

PING_TARGETS=1.1.1.1,1.0.0.1
```

## Running Manually

Generate credentials:

```bash
./venv/bin/python watchdog/generate_pia_conf.py
```

Start watchdog:

```bash
./venv/bin/python watchdog/watchdog.py
```

## OpenRC Service

The provided OpenRC service assumes the repository is installed at:

/opt/pia-wg-watchdog

Install the bundled OpenRC service:

```bash
cp service/pia-wg-watchdog.openrc /etc/init.d/pia-wg-watchdog
chmod +x /etc/init.d/pia-wg-watchdog
```

Enable at boot:

```bash
rc-update add pia-wg-watchdog default
```

Start the service:

```bash
rc-service pia-wg-watchdog start
```

Check status:

```bash
rc-service pia-wg-watchdog status
```

View logs:

```bash
tail -f /var/log/pia-wg-watchdog.log
```
## How It Works

1. Generate WireGuard credentials using PIA's official scripts.
2. Build a WireGuard configuration.
3. Bring up the WireGuard interface.
4. Verify DNS configuration.
5. Verify connectivity using ping targets.
6. Automatically repair the tunnel if connectivity fails repeatedly.

### DNS

The watchdog ensures that the VPN DNS server is configured as the primary resolver and automatically restores the configured DNS settings if they are modified.

Example:

```text
nameserver 10.0.0.244
nameserver 10.10.10.1
```

## License

This project uses the PIA manual-connections project, which is licensed under the MIT License.

See the `manual-connections` directory for the original project and license information.
