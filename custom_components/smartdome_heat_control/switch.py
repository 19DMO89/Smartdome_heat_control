"""Switch-Entities für Smartdome Heat Control."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_AWAY_ENABLED,
    CONF_VACATION_ENABLED,
    DATA_CONTROLLER,
    DATA_ENABLED,
    DEFAULT_AWAY_ENABLED,
    DEFAULT_ENABLED,
    DEFAULT_VACATION_ENABLED,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Switch-Entities für einen Config Entry anlegen."""
    async_add_entities(
        [
            SmartHeatingEnableSwitch(hass, entry),
            SmartHeatingModeSwitch(
                hass,
                entry,
                config_key=CONF_VACATION_ENABLED,
                default_value=DEFAULT_VACATION_ENABLED,
                name="Vacation Mode",
                unique_suffix="vacation_mode",
                icon="mdi:beach",
            ),
            SmartHeatingModeSwitch(
                hass,
                entry,
                config_key=CONF_AWAY_ENABLED,
                default_value=DEFAULT_AWAY_ENABLED,
                name="Away Mode",
                unique_suffix="away_mode",
                icon="mdi:home-export-outline",
            ),
        ],
        True,
    )


class SmartHeatingBaseSwitch(SwitchEntity):
    """Gemeinsame Basis für config-basierte Switches."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry

    @property
    def available(self) -> bool:
        """Entity ist verfügbar, solange der Config Entry geladen ist."""
        return self._entry.entry_id in self.hass.data.get(DOMAIN, {})

    def _get_entry_data(self) -> dict[str, Any] | None:
        """Entry-Daten aus hass.data holen."""
        return self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)

    def _get_config(self) -> dict[str, Any]:
        """Aktuelle Config des Entries holen."""
        entry_data = self._get_entry_data()
        if entry_data is None:
            return {}
        return dict(entry_data.get("config", {}))

    def _push_state(self, cfg: dict[str, Any]) -> None:
        """Globalen UI-State aktualisieren."""
        state_cfg = dict(cfg)
        state_cfg.setdefault(DATA_ENABLED, DEFAULT_ENABLED)

        self.hass.states.async_set(
            f"{DOMAIN}.config",
            "active" if state_cfg.get(DATA_ENABLED, DEFAULT_ENABLED) else "disabled",
            attributes=state_cfg,
        )

    def _apply_config_update(self, cfg: dict[str, Any]) -> None:
        """Config speichern, Controller aktualisieren und UI-State pushen."""
        entry_data = self._get_entry_data()
        if entry_data is None:
            _LOGGER.warning(
                "Kein Entry-Status für %s gefunden, Schalter kann nicht gesetzt werden",
                self._entry.entry_id,
            )
            return

        entry_data["config"] = cfg
        self.hass.config_entries.async_update_entry(self._entry, data=cfg)

        controller = entry_data.get(DATA_CONTROLLER)
        if controller is not None:
            controller.update_config(cfg)
            controller.set_enabled(bool(cfg.get(DATA_ENABLED, DEFAULT_ENABLED)))

        self._push_state(cfg)
        self.async_write_ha_state()


class SmartHeatingEnableSwitch(SmartHeatingBaseSwitch):
    """Globaler Ein/Aus-Schalter für Smartdome Heat Control."""

    _attr_name = "Enabled"
    _attr_icon = "mdi:radiator"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry)
        self._attr_unique_id = f"{entry.entry_id}_enabled"

    @property
    def is_on(self) -> bool:
        """Aktuellen Schalterzustand zurückgeben."""
        config = self._get_config()
        return bool(config.get(DATA_ENABLED, DEFAULT_ENABLED))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Integration aktivieren."""
        await self._async_set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Integration deaktivieren."""
        await self._async_set_enabled(False)

    async def _async_set_enabled(self, enabled: bool) -> None:
        """Enabled-Status setzen, speichern und Controller informieren."""
        config = self._get_config()
        config[DATA_ENABLED] = enabled

        self._apply_config_update(config)

        _LOGGER.info(
            "Smartdome Heat Control wurde %s",
            "aktiviert" if enabled else "deaktiviert",
        )


class SmartHeatingModeSwitch(SmartHeatingBaseSwitch):
    """Config-basierter Modus-Switch, z. B. Vacation oder Away."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        *,
        config_key: str,
        default_value: bool,
        name: str,
        unique_suffix: str,
        icon: str,
    ) -> None:
        super().__init__(hass, entry)
        self._config_key = config_key
        self._default_value = default_value
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{unique_suffix}"
        self._attr_icon = icon

    @property
    def is_on(self) -> bool:
        """Aktuellen Modus-Zustand zurückgeben."""
        config = self._get_config()
        return bool(config.get(self._config_key, self._default_value))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Modus aktivieren."""
        await self._async_set_mode(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Modus deaktivieren."""
        await self._async_set_mode(False)

    async def _async_set_mode(self, enabled: bool) -> None:
        """Modus-Status setzen und speichern."""
        config = self._get_config()
        config[self._config_key] = enabled

        self._apply_config_update(config)

        _LOGGER.info(
            "Smartdome Heat Control Modus %s wurde %s",
            self._config_key,
            "aktiviert" if enabled else "deaktiviert",
        )
