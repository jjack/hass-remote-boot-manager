"""Custom types for remote_boot_manager."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .manager import RemoteBootManager


type RemoteBootManagerConfigEntry = ConfigEntry[RemoteBootManager]
