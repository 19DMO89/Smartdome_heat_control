"""Smartdome Heat Control – Integration Entry Point."""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any

import voluptuous as vol
from homeassistant.components import frontend, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall

from .const import (
    CONF_ROOMS,
    DATA_CONTROLLER,
    DATA_ENABLED,
    DEFAULT_ENABLED,
    DOMAIN,
    PLATFORMS,
    SERVICE_ADD_ROOM,
    SERVICE_RELOAD,
    SERVICE_REMOVE_ROOM,
    SERVICE_UPDATE_CONFIG,
)
from .helpers import async_discover_rooms, deep_merge

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """YAML-Setup wird nicht verwendet."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup der Integration über Config Entry."""
    from .controller import SmartHeatingController

    hass.data.setdefault(DOMAIN, {})

    cfg = dict(entry.data)
    cfg.setdefault(DATA_ENABLED, DEFAULT_ENABLED)

    controller = SmartHeatingController(hass, dict(cfg))
    controller._enabled = bool(cfg.get(DATA_ENABLED, DEFAULT_ENABLED))

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CONTROLLER: controller,
        "config": cfg,
        "entry": entry,
    }

    await controller.async_start()
    await _async_register_frontend(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _async_register_ws_save_config(hass)
    _async_register_services(hass)

    _push_state(hass, cfg)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Integration entladen."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, {})
    controller = data.get(DATA_CONTROLLER)
    if controller is not None:
        await controller.async_stop()

    remaining_entries = [
        key for key in hass.data.get(DOMAIN, {}) if not key.startswith("_")
    ]

    if not remaining_entries:
        try:
            hass.states.async_remove(f"{DOMAIN}.config")
        except Exception:
            _LOGGER.debug("State %s.config konnte nicht entfernt werden", DOMAIN)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Integration neu laden."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload bei Änderungen im Options Flow."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Statisches Frontend und Sidebar-Panel registrieren."""
    frontend_path = os.path.join(os.path.dirname(__file__), "www")

    if not hass.data[DOMAIN].get("_frontend_registered"):
        if os.path.exists(frontend_path):
            await hass.http.async_register_static_paths(
                [StaticPathConfig("/smartdome_ui", frontend_path, False)]
            )
        else:
            _LOGGER.error("Frontend-Ordner 'www' nicht gefunden in %s", frontend_path)
            return

        frontend.async_register_built_in_panel(
            hass,
            component_name="iframe",
            sidebar_title="Smartdome Heat",
            sidebar_icon="mdi:radiator",
            frontend_url_path="smartdome_control",
            config={"url": "/smartdome_ui/index.html"},
            require_admin=False,
        )

        hass.data[DOMAIN]["_frontend_registered"] = True


def _async_register_ws_save_config(hass: HomeAssistant) -> None:
    """WebSocket-Command für direktes Speichern aus dem Web-Panel registrieren."""
    command_type = f"{DOMAIN}/save_config"

    if hass.data[DOMAIN].get("_ws_registered"):
        return

    @websocket_api.websocket_command(
        {
            vol.Required("type"): command_type,
            vol.Required("config"): dict,
        }
    )
    @websocket_api.async_response
    async def ws_save_config(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict[str, Any],
    ) -> None:
        target_entry = _get_single_entry(hass)
        if target_entry is None:
            connection.send_error(msg["id"], "not_found", "Keine Config Entry gefunden")
            return

        data = hass.data[DOMAIN][target_entry.entry_id]
        controller = data[DATA_CONTROLLER]
        new_cfg = dict(msg["config"])
        new_cfg.setdefault(DATA_ENABLED, DEFAULT_ENABLED)

        hass.config_entries.async_update_entry(target_entry, data=new_cfg)
        data["config"] = new_cfg

        controller.update_config(new_cfg)
        controller.set_enabled(bool(new_cfg.get(DATA_ENABLED, DEFAULT_ENABLED)))

        _push_state(hass, new_cfg)
        connection.send_result(msg["id"], {"success": True})

    websocket_api.async_register_command(hass, ws_save_config)
    hass.data[DOMAIN]["_ws_registered"] = True


def _async_register_services(hass: HomeAssistant) -> None:
    """Services für UI, Automationen und Abwärtskompatibilität registrieren."""
    if hass.data[DOMAIN].get("_services_registered"):
        return

    async def handle_update_config(call: ServiceCall) -> None:
        target_entry = _get_single_entry(hass)
        if target_entry is None:
            _LOGGER.warning("Kein Config Entry für update_config gefunden")
            return

        data = hass.data[DOMAIN][target_entry.entry_id]
        cfg = dict(data["config"])
        patch = call.data.get("config", {})

        deep_merge(cfg, patch)
        cfg.setdefault(DATA_ENABLED, DEFAULT_ENABLED)

        hass.config_entries.async_update_entry(target_entry, data=dict(cfg))
        data["config"] = cfg

        controller = data[DATA_CONTROLLER]
        controller.update_config(cfg)
        controller.set_enabled(bool(cfg.get(DATA_ENABLED, DEFAULT_ENABLED)))

        _push_state(hass, cfg)

    async def handle_add_room(call: ServiceCall) -> None:
        target_entry = _get_single_entry(hass)
        if target_entry is None:
            _LOGGER.warning("Kein Config Entry für add_room gefunden")
            return

        data = hass.data[DOMAIN][target_entry.entry_id]
        cfg = dict(data["config"])

        room_id = call.data.get("room_id") or f"room_{uuid.uuid4().hex[:8]}"
        room_label = call.data.get("label", "Neuer Raum")

        rooms = cfg.setdefault(CONF_ROOMS, {})
        if room_id not in rooms:
            rooms[room_id] = {
                "label": room_label,
                "area_id": call.data.get("area_id", ""),
                "thermostat": call.data.get("thermostat", ""),
                "sensor": call.data.get("sensor", ""),
                "target_day": call.data.get("target_day", 21.0),
                "target_night": call.data.get("target_night", 18.0),
                "day_start": call.data.get("day_start", ""),
                "night_start": call.data.get("night_start", ""),
                "enabled": call.data.get("enabled", True),
            }

        hass.config_entries.async_update_entry(target_entry, data=dict(cfg))
        data["config"] = cfg

        controller = data[DATA_CONTROLLER]
        controller.update_config(cfg)

        _push_state(hass, cfg)

    async def handle_remove_room(call: ServiceCall) -> None:
        target_entry = _get_single_entry(hass)
        if target_entry is None:
            _LOGGER.warning("Kein Config Entry für remove_room gefunden")
            return

        data = hass.data[DOMAIN][target_entry.entry_id]
        cfg = dict(data["config"])

        room_id = call.data.get("room_id")
        if room_id and room_id in cfg.get(CONF_ROOMS, {}):
            del cfg[CONF_ROOMS][room_id]

            hass.config_entries.async_update_entry(target_entry, data=dict(cfg))
            data["config"] = cfg

            controller = data[DATA_CONTROLLER]
            controller.update_config(cfg)

            _push_state(hass, cfg)

    async def handle_reload(call: ServiceCall) -> None:
        target_entry = _get_single_entry(hass)
        if target_entry is None:
            _LOGGER.warning("Kein Config Entry für reload gefunden")
            return

        data = hass.data[DOMAIN][target_entry.entry_id]
        cfg = dict(data["config"])

        new_rooms = await async_discover_rooms(hass)
        rooms = cfg.setdefault(CONF_ROOMS, {})

        for room_id, room_data in new_rooms.items():
            if room_id not in rooms:
                rooms[room_id] = room_data

        hass.config_entries.async_update_entry(target_entry, data=dict(cfg))
        data["config"] = cfg

        controller = data[DATA_CONTROLLER]
        controller.update_config(cfg)

        _push_state(hass, cfg)

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_CONFIG,
        handle_update_config,
        schema=vol.Schema({vol.Required("config"): dict}),
    )
    hass.services.async_register(DOMAIN, SERVICE_ADD_ROOM, handle_add_room)
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_ROOM,
        handle_remove_room,
        schema=vol.Schema({vol.Required("room_id"): str}),
    )
    hass.services.async_register(DOMAIN, SERVICE_RELOAD, handle_reload)

    hass.data[DOMAIN]["_services_registered"] = True


def _get_single_entry(hass: HomeAssistant) -> ConfigEntry | None:
    """Die erste verfügbare Config Entry der Integration holen."""
    domain_data = hass.data.get(DOMAIN, {})
    for key, value in domain_data.items():
        if key.startswith("_"):
            continue
        entry = value.get("entry")
        if entry is not None:
            return entry
    return None


def _push_state(hass: HomeAssistant, cfg: dict[str, Any]) -> None:
    """Globalen UI-State aktualisieren."""
    state_cfg = dict(cfg)
    state_cfg.setdefault(DATA_ENABLED, DEFAULT_ENABLED)

    hass.states.async_set(
        f"{DOMAIN}.config",
        "active" if state_cfg.get(DATA_ENABLED, DEFAULT_ENABLED) else "disabled",
        attributes=state_cfg,
    )
