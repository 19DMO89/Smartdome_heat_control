"""Smart Heating Controller – Integration Entry Point."""
from __future__ import annotations

import logging
import uuid
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.storage import Store

from .const import (
    CONF_ROOMS,
    DOMAIN,
    SERVICE_ADD_ROOM,
    SERVICE_RELOAD,
    SERVICE_REMOVE_ROOM,
    SERVICE_UPDATE_CONFIG,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .controller import SmartHeatingController
from .helpers import async_discover_rooms, deep_merge

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Basis-Setup (ohne config_entries noch nicht nötig)."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup über Config Entry (nach Einrichtung über UI)."""
    cfg = dict(entry.data)

    controller = SmartHeatingController(hass, cfg)
    await controller.async_start()

    hass.data[DOMAIN][entry.entry_id] = {
        "controller": controller,
        "config":     cfg,
        "entry":      entry,
    }

    # State für Lovelace-Karte bereitstellen
    _push_state(hass, cfg)

    # ── Services registrieren ─────────────────────────────────────────────────

    async def handle_update_config(call: ServiceCall) -> None:
        patch = call.data.get("config", {})
        deep_merge(cfg, patch)
        hass.config_entries.async_update_entry(entry, data=dict(cfg))
        controller.update_config(cfg)
        _push_state(hass, cfg)

    async def handle_add_room(call: ServiceCall) -> None:
        room_id    = call.data.get("room_id") or f"room_{uuid.uuid4().hex[:8]}"
        room_label = call.data.get("label", "Neuer Raum")
        if room_id not in cfg.get(CONF_ROOMS, {}):
            cfg.setdefault(CONF_ROOMS, {})[room_id] = {
                "label":        room_label,
                "area_id":      call.data.get("area_id", ""),
                "thermostat":   call.data.get("thermostat", ""),
                "sensor":       call.data.get("sensor", ""),
                "target_day":   call.data.get("target_day", 21.0),
                "target_night": call.data.get("target_night", 18.0),
                "enabled":      True,
            }
        hass.config_entries.async_update_entry(entry, data=dict(cfg))
        controller.update_config(cfg)
        _push_state(hass, cfg)
        _LOGGER.info("Smart Heating: Raum '%s' hinzugefügt", room_label)

    async def handle_remove_room(call: ServiceCall) -> None:
        room_id = call.data.get("room_id")
        if room_id and room_id in cfg.get(CONF_ROOMS, {}):
            del cfg[CONF_ROOMS][room_id]
            hass.config_entries.async_update_entry(entry, data=dict(cfg))
            controller.update_config(cfg)
            _push_state(hass, cfg)

    async def handle_reload(call: ServiceCall) -> None:
        """Räume neu erkennen und fehlende ergänzen."""
        new_rooms = await async_discover_rooms(hass)
        rooms = cfg.setdefault(CONF_ROOMS, {})
        added = 0
        for room_id, room in new_rooms.items():
            if room_id not in rooms:
                rooms[room_id] = room
                added += 1
        hass.config_entries.async_update_entry(entry, data=dict(cfg))
        controller.update_config(cfg)
        _push_state(hass, cfg)
        _LOGGER.info("Smart Heating: %d neue Räume erkannt", added)

    hass.services.async_register(DOMAIN, SERVICE_UPDATE_CONFIG, handle_update_config,
        schema=vol.Schema({vol.Required("config"): dict}))
    hass.services.async_register(DOMAIN, SERVICE_ADD_ROOM, handle_add_room,
        schema=vol.Schema({
            vol.Optional("room_id"):      str,
            vol.Optional("label"):        str,
            vol.Optional("area_id"):      str,
            vol.Optional("thermostat"):   str,
            vol.Optional("sensor"):       str,
            vol.Optional("target_day"):   float,
            vol.Optional("target_night"): float,
        }))
    hass.services.async_register(DOMAIN, SERVICE_REMOVE_ROOM, handle_remove_room,
        schema=vol.Schema({vol.Required("room_id"): str}))
    hass.services.async_register(DOMAIN, SERVICE_RELOAD, handle_reload,
        schema=vol.Schema({}))

    # Config Entry Update Listener (Options Flow)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Wird aufgerufen wenn der Options Flow Änderungen speichert."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Integration deaktivieren."""
    data = hass.data[DOMAIN].pop(entry.entry_id, {})
    controller: SmartHeatingController = data.get("controller")
    if controller:
        await controller.async_stop()

    for service in (SERVICE_UPDATE_CONFIG, SERVICE_ADD_ROOM, SERVICE_REMOVE_ROOM, SERVICE_RELOAD):
        hass.services.async_remove(DOMAIN, service)

    return True


def _push_state(hass: HomeAssistant, cfg: dict) -> None:
    """Schreibt Konfiguration als HA-State → Lovelace-Karte kann ihn lesen."""
    hass.states.async_set(f"{DOMAIN}.config", "active", attributes=cfg)
