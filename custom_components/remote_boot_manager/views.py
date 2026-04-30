"""Views for the remote_boot_manager custom component."""

from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING

from aiohttp import web
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.http import HomeAssistantView

from .bootloaders import async_get_bootloader
from .const import BOOTLOADER_VIEW_URL, DOMAIN

if TYPE_CHECKING:
    from .manager import RemoteBootManager

LOGGER = logging.getLogger(__name__)


class BootloaderView(HomeAssistantView):
    """View to handle unauthenticated bootloader requests."""

    # {mac_address} matches the `mac_address` argument to the get method
    url = BOOTLOADER_VIEW_URL
    name = f"api:{DOMAIN}:bootloader"
    requires_auth = False

    def __init__(self, manager: RemoteBootManager) -> None:
        """Initialize."""
        self.manager = manager

    async def get(self, request: web.Request, mac_address: str) -> web.Response:
        """
        Handle GET requests for a specific server's boot configuration.

        By default, this endpoint is read-only.
        If a valid `token` (the integration's webhook ID) is provided in the query
        string, this endpoint deviates from RESTful principles by containing a
        side-effect: it "consumes" the next_boot_option and resets it to none.

        This is a necessary compromise because many basic bootloaders (e.g., GRUB)
        only support downloading configurations via HTTP GET and lack the capability
        to execute POST requests to acknowledge receipt.
        """
        hass = request.app["hass"]
        mac_address = format_mac(mac_address)
        if not mac_address:
            return web.json_response(
                {"error": "Invalid MAC address format"}, status=400
            )

        server = self.manager.servers.get(mac_address)
        if not server:
            # this is a wake on lan entry, so this is probably a misconfiguration
            LOGGER.warning(
                "Bootloader request for unknown MAC address: %s", mac_address
            )
            return web.json_response({"error": "Server not found"}, status=404)

        bootloader_name = server.bootloader
        if not bootloader_name:
            LOGGER.error("No bootloader configured for %s", mac_address)
            return web.json_response(
                {"error": "No bootloader configured for this server"}, status=400
            )

        bootloader = await async_get_bootloader(hass, bootloader_name)
        if not bootloader:
            LOGGER.error(
                "Bootloader module %s not found for %s", bootloader_name, mac_address
            )
            return web.json_response({"error": "Bootloader not supported"}, status=400)

        # Call the appropriate bootloader instance to generate the response and (maybe)
        # consume the next boot option.
        try:
            token = request.query.get("token")
            valid_tokens = {
                entry.data["webhook_id"]
                for entry in hass.config_entries.async_entries(DOMAIN)
                if "webhook_id" in entry.data
            }

            server_copy = dataclasses.asdict(server)
            if token and token in valid_tokens:
                server_copy["next_boot_option"] = (
                    self.manager.async_consume_next_boot_option(mac_address)
                )
            else:
                server_copy["next_boot_option"] = server.next_boot_option

            return bootloader.generate_boot_config(server_copy)
        except Exception:
            LOGGER.exception("Error generating boot config for %s", mac_address)
            return web.json_response({"error": "Internal Server Error"}, status=500)
