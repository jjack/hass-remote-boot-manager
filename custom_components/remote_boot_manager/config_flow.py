"""Adds config flow for RemoteBootManager."""

from __future__ import annotations

import time

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import webhook
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_BROADCAST_ADDRESS,
    CONF_BROADCAST_PORT,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.loader import async_get_loaded_integration

from .const import BOOT_AGENT_URL, DOMAIN


class RemoteBootManagerFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for RemoteBootManager."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._webhook_id: str = ""

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return RemoteBootManagerOptionsFlow(config_entry)

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        integration = async_get_loaded_integration(self.hass, DOMAIN)
        if integration.documentation is None:
            return self.async_abort(reason="missing_documentation")

        if user_input is not None:
            # Form has no fields; clicking submit confirms intent and triggers webhook
            # generation.
            self._webhook_id = webhook.async_generate_id()
            return await self.async_step_webhook_info()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            errors={},
            description_placeholders={
                "documentation_url": integration.documentation,
            },
        )

    async def async_step_webhook_info(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Show the generated webhook ID to the user."""
        if user_input is not None:
            return self.async_create_entry(
                title="Remote Boot Manager", data={"webhook_id": self._webhook_id}
            )

        webhook_url = webhook.async_generate_url(self.hass, self._webhook_id)

        return self.async_show_form(
            step_id="webhook_info",
            description_placeholders={
                "webhook_id": self._webhook_id,
                "webhook_url": webhook_url,
                "agent_url": BOOT_AGENT_URL,
            },
        )

    async def async_step_reconfigure(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        if user_input is not None:
            # Form has no fields; clicking submit confirms intent and triggers webhook
            # sgeneration.
            self._webhook_id = webhook.async_generate_id()
            return await self.async_step_reconfigure_webhook_info()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({}),
        )

    async def async_step_reconfigure_webhook_info(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Show the new webhook ID to the user."""
        if user_input is not None:
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                data={"webhook_id": self._webhook_id},
            )

        webhook_url = webhook.async_generate_url(self.hass, self._webhook_id)

        return self.async_show_form(
            step_id="reconfigure_webhook_info",
            description_placeholders={
                "webhook_id": self._webhook_id,
                "webhook_url": webhook_url,
                "agent_url": BOOT_AGENT_URL,
            },
        )


class RemoteBootManagerOptionsFlow(config_entries.OptionsFlow):
    """Options flow for Remote Boot Manager."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self.selected_mac: str | None = None

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        manager = self._config_entry.runtime_data
        if not manager or not manager.servers:
            return self.async_abort(reason="no_servers")

        if user_input is not None:
            self.selected_mac = user_input["server"]
            return await self.async_step_server_config()

        servers = {
            mac: f"{server.name} ({mac})" for mac, server in manager.servers.items()
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("server"): vol.In(servers),
                }
            ),
        )

    async def async_step_server_config(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Configure specific server."""
        manager = self._config_entry.runtime_data

        if not self.selected_mac:
            return self.async_abort(reason="no_servers")

        server = manager.servers[self.selected_mac]

        if user_input is not None:
            if turn_off_script := user_input.get("turn_off_script"):
                # Save as a script sequence action
                server.off_action = [{"action": turn_off_script}]
            else:
                server.off_action = None

            server.address = user_input.get(CONF_ADDRESS)
            server.broadcast_address = user_input.get(CONF_BROADCAST_ADDRESS)
            server.broadcast_port = user_input.get(CONF_BROADCAST_PORT)

            # Persist the changes to storage
            manager.save()

            # Saving the entry data with a timestamp forces Home Assistant to trigger
            # the reload listener
            return self.async_create_entry(title="", data={"updated_at": time.time()})

        default_script = vol.UNDEFINED
        if (
            server.off_action
            and isinstance(server.off_action, list)
            and len(server.off_action) > 0
        ):
            action = server.off_action[0].get("action") or server.off_action[0].get(
                "service"
            )
            if action:
                default_script = action

        data_schema = {}

        if default_script != vol.UNDEFINED:
            data_schema[
                vol.Optional(
                    "turn_off_script", description={"suggested_value": default_script}
                )
            ] = selector.EntitySelector(selector.EntitySelectorConfig(domain="script"))
        else:
            data_schema[vol.Optional("turn_off_script")] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script")
            )

        # Address values can be edited here for debugging but will be overwritten by
        # the next agent webhook.
        data_schema[
            vol.Optional(CONF_ADDRESS, description={"suggested_value": server.address})
            if server.address is not None
            else vol.Optional(CONF_ADDRESS)
        ] = str
        data_schema[
            vol.Optional(
                CONF_BROADCAST_ADDRESS,
                description={"suggested_value": server.broadcast_address},
            )
            if server.broadcast_address is not None
            else vol.Optional(CONF_BROADCAST_ADDRESS)
        ] = str
        data_schema[
            vol.Optional(
                CONF_BROADCAST_PORT,
                description={"suggested_value": server.broadcast_port},
            )
            if server.broadcast_port is not None
            else vol.Optional(CONF_BROADCAST_PORT)
        ] = int

        return self.async_show_form(
            step_id="server_config",
            data_schema=vol.Schema(data_schema),
            description_placeholders={
                "server_name": server.name,
            },
        )
