const DOMAIN = "smartdome_heat_control";
const CONFIG_ENTITY_ID = `${DOMAIN}.config`;

const DEFAULTS = {
  enabled: true,
  main_thermostat: "",
  main_sensor: "",
  boost_delta: 2.0,
  tolerance: 0.5,
  night_start: "22:00",
  morning_boost_start: "05:00",
  morning_boost_end: "05:30",
  rooms: {},
};

const state = {
  config: structuredClone(DEFAULTS),
  climates: [],
  sensors: [],
  allStates: [],
  initialized: false,
};

const els = {
  statusBox: document.getElementById("statusBox"),
  saveBtn: document.getElementById("saveBtn"),
  reloadConfigBtn: document.getElementById("reloadConfigBtn"),
  reloadRoomsBtn: document.getElementById("reloadRoomsBtn"),
  addRoomBtn: document.getElementById("addRoomBtn"),
  enabled: document.getElementById("enabled"),
  mainThermostat: document.getElementById("main_thermostat"),
  mainSensor: document.getElementById("main_sensor"),
  boostDelta: document.getElementById("boost_delta"),
  tolerance: document.getElementById("tolerance"),
  nightStart: document.getElementById("night_start"),
  morningBoostStart: document.getElementById("morning_boost_start"),
  morningBoostEnd: document.getElementById("morning_boost_end"),
  roomsContainer: document.getElementById("roomsContainer"),
};

function setStatus(message, type = "warn") {
  els.statusBox.textContent = message;
  els.statusBox.className = `status ${type}`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function prettyEntityLabel(item) {
  const friendlyName = item.attributes?.friendly_name || item.entity_id;
  return `${friendlyName} (${item.entity_id})`;
}

function sortByEntityId(items) {
  return [...items].sort((a, b) => a.entity_id.localeCompare(b.entity_id));
}

function isTemperatureSensor(entity) {
  if (!entity?.entity_id?.startsWith("sensor.")) {
    return false;
  }

  const deviceClass = entity.attributes?.device_class;
  if (deviceClass === "temperature") {
    return true;
  }

  const entityId = entity.entity_id.toLowerCase();
  const looksLikeTemperature = entityId.includes("temp") || entityId.includes("temperature");
  const numericState = !Number.isNaN(Number(entity.state));

  return looksLikeTemperature && numericState;
}

function normalizeTime(value, fallback) {
  if (typeof value !== "string" || !value.includes(":")) {
    return fallback;
  }
  return value.slice(0, 5);
}

function normalizeNumber(value, fallback) {
  const num = Number(value);
  return Number.isFinite(num) ? num : fallback;
}

function normalizeConfig(input) {
  const cfg = {
    ...structuredClone(DEFAULTS),
    ...(input || {}),
  };

  cfg.enabled = cfg.enabled !== false;
  cfg.main_thermostat = typeof cfg.main_thermostat === "string" ? cfg.main_thermostat : "";
  cfg.main_sensor = typeof cfg.main_sensor === "string" ? cfg.main_sensor : "";
  cfg.boost_delta = normalizeNumber(cfg.boost_delta, DEFAULTS.boost_delta);
  cfg.tolerance = normalizeNumber(cfg.tolerance, DEFAULTS.tolerance);
  cfg.night_start = normalizeTime(cfg.night_start, DEFAULTS.night_start);
  cfg.morning_boost_start = normalizeTime(cfg.morning_boost_start, DEFAULTS.morning_boost_start);
  cfg.morning_boost_end = normalizeTime(cfg.morning_boost_end, DEFAULTS.morning_boost_end);

  if (!cfg.rooms || typeof cfg.rooms !== "object") {
    cfg.rooms = {};
  }

  const normalizedRooms = {};
  for (const [roomId, room] of Object.entries(cfg.rooms)) {
    normalizedRooms[roomId] = {
      label: typeof room?.label === "string" && room.label.trim() ? room.label.trim() : roomId,
      area_id: typeof room?.area_id === "string" ? room.area_id : "",
      thermostat: typeof room?.thermostat === "string" ? room.thermostat : "",
      sensor: typeof room?.sensor === "string" ? room.sensor : "",
      target_day: normalizeNumber(room?.target_day, 21.0),
      target_night: normalizeNumber(room?.target_night, 18.0),
      enabled: room?.enabled !== false,
    };
  }

  cfg.rooms = normalizedRooms;
  return cfg;
}

async function getHassConnection() {
  if (window.hassConnection) {
    return window.hassConnection;
  }

  if (window.parent?.hassConnection) {
    return window.parent.hassConnection;
  }

  throw new Error("Keine Home-Assistant-Verbindung verfügbar");
}

async function getAccessToken() {
  const connWrapper = await getHassConnection();
  const token = connWrapper?.auth?.data?.access_token;

  if (!token) {
    throw new Error("Kein Zugriffstoken verfügbar");
  }

  return token;
}

async function haFetch(path, options = {}) {
  const token = await getAccessToken();

  const response = await fetch(path, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  const text = await response.text();

  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}${text ? ` – ${text}` : ""}`);
  }

  return text ? JSON.parse(text) : null;
}

async function callService(domain, service, data = {}) {
  return haFetch(`/api/services/${domain}/${service}`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

function buildSelectOptions(selectEl, items, selectedValue, options = {}) {
  const {
    includeEmpty = true,
    emptyLabel = "— Nicht gesetzt —",
  } = options;

  selectEl.innerHTML = "";

  if (includeEmpty) {
    const emptyOption = document.createElement("option");
    emptyOption.value = "";
    emptyOption.textContent = emptyLabel;
    selectEl.appendChild(emptyOption);
  }

  for (const item of items) {
    const option = document.createElement("option");
    option.value = item.entity_id;
    option.textContent = prettyEntityLabel(item);
    if (item.entity_id === selectedValue) {
      option.selected = true;
    }
    selectEl.appendChild(option);
  }
}

async function loadAllStates() {
  const states = await haFetch("/api/states");
  state.allStates = Array.isArray(states) ? states : [];

  state.climates = sortByEntityId(
    state.allStates.filter((item) => item.entity_id?.startsWith("climate."))
  );

  state.sensors = sortByEntityId(
    state.allStates.filter((item) => isTemperatureSensor(item))
  );
}

async function loadConfig() {
  try {
    const entity = await haFetch(`/api/states/${CONFIG_ENTITY_ID}`);
    state.config = normalizeConfig(entity?.attributes || {});
  } catch (error) {
    if (String(error.message).includes("404")) {
      state.config = normalizeConfig({});
      return;
    }
    throw error;
  }
}

function renderGlobalSettings() {
  const cfg = state.config;

  els.enabled.checked = cfg.enabled;
  els.boostDelta.value = String(cfg.boost_delta);
  els.tolerance.value = String(cfg.tolerance);
  els.nightStart.value = cfg.night_start;
  els.morningBoostStart.value = cfg.morning_boost_start;
  els.morningBoostEnd.value = cfg.morning_boost_end;

  buildSelectOptions(
    els.mainThermostat,
    state.climates,
    cfg.main_thermostat,
    {
      includeEmpty: true,
      emptyLabel: "— Bitte wählen —",
    }
  );

  buildSelectOptions(
    els.mainSensor,
    state.sensors,
    cfg.main_sensor,
    {
      includeEmpty: true,
      emptyLabel: "— Automatisch / keiner —",
    }
  );
}

function createRoomCard(roomId, room) {
  const wrapper = document.createElement("div");
  wrapper.className = "room";
  wrapper.dataset.roomId = roomId;

  const areaText = room.area_id ? `Area: ${room.area_id}` : "Manuell angelegt";

  wrapper.innerHTML = `
    <div class="room-top">
      <div>
        <div class="room-title">${escapeHtml(room.label || roomId)}</div>
        <div class="room-subtitle">${escapeHtml(areaText)}</div>
      </div>
      <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
        <span class="pill">
          <input class="room-enabled" type="checkbox" ${room.enabled ? "checked" : ""} />
          <span>Aktiv</span>
        </span>
        <button class="danger room-delete-btn" type="button">Löschen</button>
      </div>
    </div>

    <div class="room-grid">
      <div class="field">
        <label>Bezeichnung</label>
        <input class="room-label" type="text" value="${escapeHtml(room.label || "")}" />
      </div>

      <div class="field">
        <label>Area-ID</label>
        <input class="room-area-id" type="text" value="${escapeHtml(room.area_id || "")}" />
      </div>

      <div class="field">
        <label>Thermostat</label>
        <select class="room-thermostat"></select>
      </div>

      <div class="field">
        <label>Temperatursensor</label>
        <select class="room-sensor"></select>
      </div>

      <div class="field">
        <label>Zieltemperatur Tag (°C)</label>
        <input class="room-target-day" type="number" min="5" max="30" step="0.1" value="${escapeHtml(room.target_day)}" />
      </div>

      <div class="field">
        <label>Zieltemperatur Nacht (°C)</label>
        <input class="room-target-night" type="number" min="5" max="30" step="0.1" value="${escapeHtml(room.target_night)}" />
      </div>
    </div>
  `;

  const thermostatSelect = wrapper.querySelector(".room-thermostat");
  const sensorSelect = wrapper.querySelector(".room-sensor");
  const deleteBtn = wrapper.querySelector(".room-delete-btn");

  buildSelectOptions(
    thermostatSelect,
    state.climates,
    room.thermostat || "",
    { includeEmpty: true, emptyLabel: "— Nicht gesetzt —" }
  );

  buildSelectOptions(
    sensorSelect,
    state.sensors,
    room.sensor || "",
    { includeEmpty: true, emptyLabel: "— Nicht gesetzt —" }
  );

  deleteBtn.addEventListener("click", () => {
    delete state.config.rooms[roomId];
    renderRooms();
  });

  return wrapper;
}

function renderRooms() {
  els.roomsContainer.innerHTML = "";

  const entries = Object.entries(state.config.rooms || {});
  if (!entries.length) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "Noch keine Räume vorhanden.";
    els.roomsContainer.appendChild(empty);
    return;
  }

  for (const [roomId, room] of entries) {
    els.roomsContainer.appendChild(createRoomCard(roomId, room));
  }
}

function collectFormState() {
  const cfg = structuredClone(state.config);

  cfg.enabled = els.enabled.checked;
  cfg.main_thermostat = els.mainThermostat.value || "";
  cfg.main_sensor = els.mainSensor.value || "";
  cfg.boost_delta = normalizeNumber(els.boostDelta.value, DEFAULTS.boost_delta);
  cfg.tolerance = normalizeNumber(els.tolerance.value, DEFAULTS.tolerance);
  cfg.night_start = normalizeTime(els.nightStart.value, DEFAULTS.night_start);
  cfg.morning_boost_start = normalizeTime(
    els.morningBoostStart.value,
    DEFAULTS.morning_boost_start
  );
  cfg.morning_boost_end = normalizeTime(
    els.morningBoostEnd.value,
    DEFAULTS.morning_boost_end
  );

  const rooms = {};
  const roomNodes = els.roomsContainer.querySelectorAll(".room");

  for (const node of roomNodes) {
    const roomId = node.dataset.roomId;
    rooms[roomId] = {
      label: node.querySelector(".room-label").value.trim() || roomId,
      area_id: node.querySelector(".room-area-id").value.trim(),
      thermostat: node.querySelector(".room-thermostat").value || "",
      sensor: node.querySelector(".room-sensor").value || "",
      target_day: normalizeNumber(node.querySelector(".room-target-day").value, 21.0),
      target_night: normalizeNumber(node.querySelector(".room-target-night").value, 18.0),
      enabled: node.querySelector(".room-enabled").checked,
    };
  }

  cfg.rooms = rooms;
  return normalizeConfig(cfg);
}

function generateRoomId() {
  return `room_${Math.random().toString(16).slice(2, 10)}`;
}

function addRoom() {
  const roomId = generateRoomId();
  state.config.rooms[roomId] = {
    label: "Neuer Raum",
    area_id: "",
    thermostat: "",
    sensor: "",
    target_day: 21.0,
    target_night: 18.0,
    enabled: true,
  };
  renderRooms();
}

async function saveConfig() {
  try {
    setButtonsDisabled(true);
    setStatus("Speichere Konfiguration …", "warn");

    const cfg = collectFormState();

    await callService(DOMAIN, "update_config", {
      config: cfg,
    });

    state.config = cfg;
    renderGlobalSettings();
    renderRooms();
    setStatus("Konfiguration erfolgreich gespeichert.", "ok");
  } catch (error) {
    console.error(error);
    setStatus(`Speichern fehlgeschlagen: ${error.message}`, "err");
  } finally {
    setButtonsDisabled(false);
  }
}

async function reloadRooms() {
  try {
    setButtonsDisabled(true);
    setStatus("Erkenne Räume neu …", "warn");

    await callService(DOMAIN, "reload", {});
    await refreshAll();

    setStatus("Räume wurden neu erkannt.", "ok");
  } catch (error) {
    console.error(error);
    setStatus(`Neu-Erkennung fehlgeschlagen: ${error.message}`, "err");
  } finally {
    setButtonsDisabled(false);
  }
}

async function reloadConfig() {
  try {
    setButtonsDisabled(true);
    setStatus("Lade Konfiguration neu …", "warn");

    await refreshAll();

    setStatus("Konfiguration neu geladen.", "ok");
  } catch (error) {
    console.error(error);
    setStatus(`Neu laden fehlgeschlagen: ${error.message}`, "err");
  } finally {
    setButtonsDisabled(false);
  }
}

async function refreshAll() {
  await loadAllStates();
  await loadConfig();
  renderGlobalSettings();
  renderRooms();
}

function setButtonsDisabled(disabled) {
  els.saveBtn.disabled = disabled;
  els.reloadConfigBtn.disabled = disabled;
  els.reloadRoomsBtn.disabled = disabled;
  els.addRoomBtn.disabled = disabled;
}

function bindEvents() {
  els.saveBtn.addEventListener("click", saveConfig);
  els.reloadRoomsBtn.addEventListener("click", reloadRooms);
  els.reloadConfigBtn.addEventListener("click", reloadConfig);
  els.addRoomBtn.addEventListener("click", addRoom);
}

async function init() {
  bindEvents();
  setButtonsDisabled(true);
  setStatus("Initialisiere Panel …", "warn");

  try {
    await refreshAll();
    state.initialized = true;
    setStatus("Konfiguration geladen.", "ok");
  } catch (error) {
    console.error(error);
    setStatus(
      `Initialisierung fehlgeschlagen: ${error.message}`,
      "err"
    );
  } finally {
    setButtonsDisabled(false);
  }
}

init();
