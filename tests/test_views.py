"""Test views for remote_boot_manager."""

from unittest.mock import MagicMock, patch

from aiohttp import web
from homeassistant.core import HomeAssistant

from custom_components.remote_boot_manager.manager import RemoteServer
from custom_components.remote_boot_manager.views import BootloaderView


async def test_bootloader_view_invalid_mac(hass: HomeAssistant) -> None:
    """Test Invalid MAC."""
    mock_manager = MagicMock()
    view = BootloaderView(mock_manager)
    mock_request = MagicMock(spec=web.Request)
    mock_request.app = {"hass": hass}
    with patch(
        "custom_components.remote_boot_manager.views.format_mac", return_value=None
    ):
        resp = await view.get(mock_request, "invalid")
        assert resp.status == 400


async def test_bootloader_view_server_not_found(hass: HomeAssistant) -> None:
    """Test server not found."""
    mock_request = MagicMock(spec=web.Request)
    mock_request.app = {"hass": hass}

    mock_manager = MagicMock()
    mock_manager.servers = {}
    view = BootloaderView(mock_manager)

    resp = await view.get(mock_request, "aa:bb:cc:dd:ee:ff")
    assert resp.status == 404


async def test_bootloader_view_no_bootloader(hass: HomeAssistant) -> None:
    """Test server with no bootloader configured."""
    mock_request = MagicMock(spec=web.Request)
    mock_request.app = {"hass": hass}

    mock_manager = MagicMock()
    mock_manager.servers = {
        "aa:bb:cc:dd:ee:ff": RemoteServer(
            mac="aa:bb:cc:dd:ee:ff",
            name="test",
            bootloader=None,
        )
    }
    view = BootloaderView(mock_manager)

    resp = await view.get(mock_request, "aa:bb:cc:dd:ee:ff")
    assert resp.status == 400


async def test_bootloader_view_unsupported_bootloader(hass: HomeAssistant) -> None:
    """Test unsupported bootloader."""
    mock_request = MagicMock(spec=web.Request)
    mock_request.app = {"hass": hass}

    mock_manager = MagicMock()
    mock_manager.servers = {
        "aa:bb:cc:dd:ee:ff": RemoteServer(
            mac="aa:bb:cc:dd:ee:ff",
            name="test",
            bootloader="unsupported",
        )
    }
    view = BootloaderView(mock_manager)

    with patch(
        "custom_components.remote_boot_manager.views.async_get_bootloader",
        return_value=None,
    ):
        resp = await view.get(mock_request, "aa:bb:cc:dd:ee:ff")
        assert resp.status == 400


async def test_bootloader_view_exception(hass: HomeAssistant) -> None:
    """Test exception generating config."""
    mock_request = MagicMock(spec=web.Request)
    mock_request.app = {"hass": hass}

    mock_manager = MagicMock()
    mock_manager.servers = {
        "aa:bb:cc:dd:ee:ff": RemoteServer(
            mac="aa:bb:cc:dd:ee:ff",
            name="test",
            bootloader="grub",
        )
    }
    mock_request.query = {}
    view = BootloaderView(mock_manager)

    mock_bootloader = MagicMock()
    mock_bootloader.generate_boot_config.side_effect = Exception("Boom")
    with patch(
        "custom_components.remote_boot_manager.views.async_get_bootloader",
        return_value=mock_bootloader,
    ):
        resp = await view.get(mock_request, "aa:bb:cc:dd:ee:ff")
        assert resp.status == 500


async def test_bootloader_view_success_read_only(hass: HomeAssistant) -> None:
    """Test successful request without a valid token (read-only)."""
    mock_request = MagicMock(spec=web.Request)
    mock_request.app = {"hass": hass}
    mock_request.query = {}

    mock_manager = MagicMock()
    mock_manager.servers = {
        "aa:bb:cc:dd:ee:ff": RemoteServer(
            mac="aa:bb:cc:dd:ee:ff",
            name="test",
            bootloader="grub",
            next_boot_option="windows",
        )
    }
    view = BootloaderView(mock_manager)

    mock_bootloader = MagicMock()
    mock_bootloader.generate_boot_config.return_value = web.Response(text="ok")

    with patch(
        "custom_components.remote_boot_manager.views.async_get_bootloader",
        return_value=mock_bootloader,
    ):
        resp = await view.get(mock_request, "aa:bb:cc:dd:ee:ff")
        assert resp.status == 200
        mock_manager.async_consume_next_boot_option.assert_not_called()

        # Verify the unconsumed next_boot_option is passed to the generator
        called_server = mock_bootloader.generate_boot_config.call_args[0][0]
        assert called_server["next_boot_option"] == "windows"


async def test_bootloader_view_success_consume(hass: HomeAssistant) -> None:
    """Test successful request with a valid token (consumes state)."""
    mock_request = MagicMock(spec=web.Request)
    mock_request.app = {"hass": hass}
    mock_request.query = {"token": "valid_webhook_id"}

    mock_entry = MagicMock()
    mock_entry.data = {"webhook_id": "valid_webhook_id"}
    hass.config_entries.async_entries = MagicMock(return_value=[mock_entry])

    mock_manager = MagicMock()
    mock_manager.servers = {
        "aa:bb:cc:dd:ee:ff": RemoteServer(
            mac="aa:bb:cc:dd:ee:ff",
            name="test",
            bootloader="grub",
            next_boot_option="windows",
        )
    }
    mock_manager.async_consume_next_boot_option.return_value = "windows"
    view = BootloaderView(mock_manager)

    mock_bootloader = MagicMock()
    mock_bootloader.generate_boot_config.return_value = web.Response(text="ok")

    with patch(
        "custom_components.remote_boot_manager.views.async_get_bootloader",
        return_value=mock_bootloader,
    ):
        resp = await view.get(mock_request, "aa:bb:cc:dd:ee:ff")
        assert resp.status == 200
        mock_manager.async_consume_next_boot_option.assert_called_once_with(
            "aa:bb:cc:dd:ee:ff"
        )

        called_server = mock_bootloader.generate_boot_config.call_args[0][0]
        assert called_server["next_boot_option"] == "windows"
