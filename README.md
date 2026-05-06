# Remote Boot Manager for Home Assistant

![GitHub](https://img.shields.io/github/license/jjack/hass-remote-boot-manager)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/jjack/hass-remote-boot-manager)
[![Python and Coverage](https://github.com/jjack/hass-remote-boot-manager/actions/workflows/test.yml/badge.svg)](https://github.com/jjack/hass-remote-boot-manager/actions/workflows/test.yml)
[![CodeQL](https://github.com/jjack/hass-remote-boot-manager/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/jjack/hass-remote-boot-manager/actions/workflows/github-code-scanning/codeql)
![Codecov branch](https://img.shields.io/codecov/c/github/jjack/hass-remote-boot-manager)

Manage and automate the booting of your remote bare-metal hosts in Home Assistant.

## Features
* **Dynamic OS Discovery**: Hosts automatically report their available OS list (e.g., Ubuntu, Windows) to Home Assistant.
* **Next Boot Selection**: Change the next boot OS via a dropdown `select` entity.
* **Wake-on-LAN & Power Status**: Sends magic packets to wake hosts and tracks power state via ping.
* **Bootloader Endpoint**: Exposes a smart endpoint for GRUB (or other bootloaders) to fetch the selected OS and automatically reset state to prevent boot loops.
* **Secure Webhooks**: Uses auto-generated, secure webhooks for agent-to-HA communication.


This integration creates a new Home Assistant Device for each host discovered by the agent. Each device will have the following entities:

*   **Switch**: A `switch` entity named `[Host Name] Wake` that sends the Wake-on-LAN magic packet and tracks the host's power state via ping.
*   **Select**: A `select` entity named `[Host Name] Next Boot Option` that allows you to choose which OS the host should boot into on its next restart.

## Installation

### Via HACS (Recommended)
1. Open HACS in Home Assistant.
2. Go to **Integrations**.
3. Click the 3 dots in the top right -> **Custom repositories**.
4. Add `jjack/hass-remote-boot-manager` as an Integration.
5. Download it and restart Home Assistant.

### Manual Installation
1. Copy the `custom_components/remote_boot_manager` directory to your Home Assistant `custom_components` directory.
2. Restart Home Assistant.

## Configuration & Setup

1. Go to **Settings** -> **Devices & Services** in Home Assistant.
2. Click **+ Add Integration** and search for "Remote Boot Manager".
3. **IMPORTANT:** During setup, Home Assistant will generate a unique, secure `webhook_id`. **You must copy and save this ID and the example configuration!** It is only shown to you once for security reasons. You will need it to configure your remote hosts.

## Remote Boot Agent (Client Setup)

For this integration to work, you must install a bare-metal GO agent on **every** target host you want to manage.

**Agent Repository:** jjack/remote-boot-agent

### Basic Agent Setup:
1. Download the [remote-boot-agent](https://github.com/jjack/hass-remote-boot-manager/releases/latest) package, binary, or source code.
2. Install the agent on your target host.
3. Configure the agent using your Home Assistant URL and the `webhook_id` you saved during the integration setup.
4. Run the agent. It will automatically ping Home Assistant, and your host will instantly appear as a new Device!

*(For detailed installation instructions, see the remote-boot-agent repository).*

## Tips & Hints

* **Testing Bootloaders**: The bootloader endpoint is read-only by default so you can safely test it. To actually consume the next boot option, append `?token=YOUR_WEBHOOK_ID` to the request URL.
* **IP address or hostname changes**: If a host's IP address or hostname changes, the integration will attempt to update the Device Registry automatically. If you need to remove an old host, you can do so directly from the Home Assistant UI via the device page.
* **Custom Broadcast Networks**: If your Home Assistant instance spans multiple VLANs or complex subnets, you can define custom broadcast IP addresses and ports to ensure magic packets reliably reach your hosts.
* **Security Regeneration**: If you suspect your webhook ID is compromised, you can safely regenerate it via the  button (gear icon) on the integration card. This menu also allows you to temporarily override the Wake-on-LAN broadcast address and port for troubleshooting, though these settings will be overwritten by the agent on its next check-in.
