"""Smartdome Heat Control."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    DATA_CONTROLLER,
    DATA_ENABLED,
    DEFAULT_ENABLED,
    DOMAIN,
    PLATFORMS,
)
from .controller import SmartHeatingController


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """YAML-Setup nicht verwendet."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Integration aus Config Entry laden."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    controller = SmartHeatingController(hass, dict(entry.data))
    controller.set_enabled(DEFAULT_ENABLED)

    hass.data[DOMAIN][entry.entry_id][DATA_CONTROLLER] = controller
    hass.data[DOMAIN][entry.entry_id][DATA_ENABLED] = DEFAULT_ENABLED

    await controller.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Integration entladen."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        controller = hass.data[DOMAIN][entry.entry_id].get(DATA_CONTROLLER)
        if controller is not None:
            await controller.async_stop()

        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Integration neu laden."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
