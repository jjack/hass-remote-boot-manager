"""Test the config flow."""

from unittest.mock import MagicMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.remote_boot_manager.config_flow import (
    RemoteBootManagerOptionsFlow,
)
from custom_components.remote_boot_manager.const import DOMAIN
from custom_components.remote_boot_manager.manager import RemoteServer


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {}

    with patch(
        "custom_components.remote_boot_manager.config_flow.webhook.async_generate_url",
        return_value="http://example.com/webhook",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "webhook_info"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {},
    )

    assert result3.get("type") == FlowResultType.CREATE_ENTRY
    assert result3.get("title") == "Remote Boot Manager"
    assert "webhook_id" in result3.get("data", {})


async def test_form_missing_documentation(hass: HomeAssistant) -> None:
    """Test we abort if documentation is missing."""
    with patch(
        "custom_components.remote_boot_manager.config_flow.async_get_loaded_integration"
    ) as mock_get_integration:
        mock_integration = MagicMock()
        mock_integration.documentation = None
        mock_get_integration.return_value = mock_integration

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result.get("type") == FlowResultType.ABORT
        assert result.get("reason") == "missing_documentation"


async def test_single_instance_allowed(hass: HomeAssistant) -> None:
    """Test that only a single instance is allowed."""
    entry = MockConfigEntry(domain=DOMAIN, data={"webhook_id": "test_id"})
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "single_instance_allowed"


async def test_reconfigure_flow(hass: HomeAssistant) -> None:
    """Test reconfigure flow to regenerate webhook ID."""
    entry = MockConfigEntry(domain=DOMAIN, data={"webhook_id": "old_id"})
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "reconfigure"

    with (
        patch(
            "custom_components.remote_boot_manager.config_flow.webhook.async_generate_id",
            return_value="new_id",
        ),
        patch(
            "custom_components.remote_boot_manager.config_flow.webhook.async_generate_url",
            return_value="http://example.com/new_webhook",
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "reconfigure_webhook_info"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={},
    )

    assert result3.get("type") == FlowResultType.ABORT
    assert result3.get("reason") == "reconfigure_successful"
    assert entry.data["webhook_id"] == "new_id"


async def test_options_flow_no_servers(hass: HomeAssistant) -> None:
    """Test options flow aborts when there are no servers available."""
    entry = MockConfigEntry(domain=DOMAIN, data={"webhook_id": "test_id"})
    entry.add_to_hass(hass)

    mock_manager = MagicMock()
    mock_manager.servers = {}
    entry.runtime_data = mock_manager

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "no_servers"


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options flow to successfully configure a server script and addresses."""
    entry = MockConfigEntry(domain=DOMAIN, data={"webhook_id": "test_id"})
    entry.add_to_hass(hass)

    mock_manager = MagicMock()
    mock_server = RemoteServer(
        mac="00:11:22:33:44:55",
        name="Test Server",
        address="test.local",
    )
    mock_manager.servers = {"00:11:22:33:44:55": mock_server}
    entry.runtime_data = mock_manager

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"server": "00:11:22:33:44:55"},
    )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "server_config"

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={
            "turn_off_script": "script.turn_off",
            "address": "new.local",
            "broadcast_address": "192.168.1.255",
            "broadcast_port": 9,
        },
    )

    assert result3.get("type") == FlowResultType.CREATE_ENTRY
    assert mock_server.off_action == [{"action": "script.turn_off"}]
    assert mock_server.address == "new.local"
    assert mock_server.broadcast_address == "192.168.1.255"
    assert mock_server.broadcast_port == 9
    mock_manager.save.assert_called_once()


async def test_options_flow_clear_script_and_service_fallback(
    hass: HomeAssistant,
) -> None:
    """Test options flow clearing a script and handling legacy 'service' action syntax."""
    entry = MockConfigEntry(domain=DOMAIN, data={"webhook_id": "test_id"})
    entry.add_to_hass(hass)

    mock_manager = MagicMock()
    mock_server = RemoteServer(
        mac="00:11:22:33:44:55",
        name="Test Server",
        address="test.local",
        off_action=[{"service": "script.turn_off"}],
    )
    mock_manager.servers = {"00:11:22:33:44:55": mock_server}
    entry.runtime_data = mock_manager

    result = await hass.config_entries.options.async_init(entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"server": "00:11:22:33:44:55"},
    )
    assert result2.get("type") == FlowResultType.FORM

    # Submit the form without specifying a turn_off_script to clear it
    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={
            "address": "cleared.local",
        },
    )

    assert result3.get("type") == FlowResultType.CREATE_ENTRY
    assert mock_server.off_action is None
    assert mock_server.address == "cleared.local"
    mock_manager.save.assert_called()


async def test_options_flow_server_config_no_mac(hass: HomeAssistant) -> None:
    """Test options flow aborts if selected mac is missing."""
    entry = MockConfigEntry(domain=DOMAIN, data={"webhook_id": "test_id"})
    entry.runtime_data = MagicMock()
    entry.add_to_hass(hass)

    flow = RemoteBootManagerOptionsFlow(entry)
    flow.hass = hass

    result = await flow.async_step_server_config()
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "no_servers"
