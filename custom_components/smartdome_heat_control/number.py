"""Number-Entities für Smartdome Heat Control."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_VACATION_TEMPERATURE,
    DATA_CONTROLLER,
    DATA_ENABLED,
    DEFAULT_ENABLED,
    DEFAULT_VACATION_TEMPERATURE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Number-Entities für einen Config Entry anlegen."""
    async_add_entities(
        [SmartHeatingVacationTemperatureNumber(hass, entry)],
        True,
    )


class SmartHeatingVacationTemperatureNumber(NumberEntity):
    """Globale Urlaubstemperatur als Home-Assistant-Number-Entity."""

    _attr_has_entity_name = True
    _attr_name = "Vacation Temperature"
    _attr_icon = "mdi:thermometer"
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG

    _attr_native_min_value = 5.0
    _attr_native_max_value = 20.0
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_vacation_temperature"

    @property
    def available(self) -> bool:
        """Entity ist verfügbar, solange der Config Entry geladen ist."""
        return self._entry.entry_id in self.hass.data.get(DOMAIN, {})

    def _get_entry_data(self) -> dict | None:
        """Entry-Daten aus hass.data holen."""
        return self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)

    def _get_config(self) -> dict:
        """Aktuelle Config des Entries holen."""
        entry_data = self._get_entry_data()
        if entry_data is None:
            return {}
        return dict(entry_data.get("config", {}))

    def _push_state(self, cfg: dict) -> None:
        """Globalen UI-State aktualisieren."""
        state_cfg = dict(cfg)
        state_cfg.setdefault(DATA_ENABLED, DEFAULT_ENABLED)

        self.hass.states.async_set(
            f"{DOMAIN}.config",
            "active" if state_cfg.get(DATA_ENABLED, DEFAULT_ENABLED) else "disabled",
            attributes=state_cfg,
        )

    @property
    def native_value(self) -> float:
        """Aktuellen Wert der Urlaubstemperatur zurückgeben."""
        config = self._get_config()
        return float(
            config.get(
                CONF_VACATION_TEMPERATURE,
                DEFAULT_VACATION_TEMPERATURE,
            )
        )

    async def async_set_native_value(self, value: float) -> None:
        """Urlaubstemperatur setzen, speichern und Controller informieren."""
        entry_data = self._get_entry_data()
        if entry_data is None:
            _LOGGER.warning(
                "Kein Entry-Status für %s gefunden, Zahl kann nicht gesetzt werden",
                self._entry.entry_id,
            )
            return

        config = self._get_config()
        config[CONF_VACATION_TEMPERATURE] = float(value)

        entry_data["config"] = config
        self.hass.config_entries.async_update_entry(self._entry, data=config)

        controller = entry_data.get(DATA_CONTROLLER)
        if controller is not None:
            controller.update_config(config)
            controller.set_enabled(bool(config.get(DATA_ENABLED, DEFAULT_ENABLED)))

        self._push_state(config)

        _LOGGER.info(
            "Smartdome Heat Control Urlaubstemperatur auf %.1f °C gesetzt",
            float(value),
        )

        self.async_write_ha_state()
