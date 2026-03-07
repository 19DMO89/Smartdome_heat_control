"""Switch-Entity für Smartdome Heat Control."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_CONTROLLER, DATA_ENABLED, DEFAULT_ENABLED, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Switch-Entity für einen Config Entry anlegen."""
    async_add_entities([SmartHeatingEnableSwitch(hass, entry)], True)


class SmartHeatingEnableSwitch(SwitchEntity):
    """Globaler Ein/Aus-Schalter für die Integration."""

    _attr_has_entity_name = True
    _attr_name = "Enabled"
    _attr_icon = "mdi:radiator"
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_enabled"
        self._attr_is_on = hass.data[DOMAIN][entry.entry_id].get(
            DATA_ENABLED,
            DEFAULT_ENABLED,
        )

    async def async_turn_on(self, **kwargs) -> None:
        """Integration aktivieren."""
        await self._async_set_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Integration deaktivieren."""
        await self._async_set_enabled(False)

    async def _async_set_enabled(self, enabled: bool) -> None:
        """Status setzen und Controller informieren."""
        self.hass.data[DOMAIN][self._entry.entry_id][DATA_ENABLED] = enabled
        self._attr_is_on = enabled

        controller = self.hass.data[DOMAIN][self._entry.entry_id].get(DATA_CONTROLLER)
        if controller is not None:
            controller.set_enabled(enabled)

        _LOGGER.info(
            "Smartdome Heat Control wurde %s",
            "aktiviert" if enabled else "deaktiviert",
        )

        self.async_write_ha_state()
