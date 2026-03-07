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

let appState = {
  config: structuredClone(DEFAULTS),
  climates: [],
  sensors: [],
  allStates: [],
};

const els = {
  statusBox: document.getElementById("statusBox"),
  saveBtn: document.getElementById("saveBtn"),
  reloadConfigBtn: document.getElementById("reloadConfigBtn"),
  reloadRoomsBtn: document.getElementById("reloadRoomsBtn"),
  addRoomBtn: document.getElementById("addRoomBtn"),
  enabled: document.getElementById("enabled"),
  main_thermostat: document.getElementById("main_thermostat"),
  main_sensor: document.getElementById("main_sensor"),
  boost_delta: document.getElementById("boost_delta"),
  tolerance: document.getElementById("tolerance"),
  night_start: document.getElementById("night_start"),
  morning_boost_start: document.getElementById("morning_boost_start"),
  morning_boost_end: document.getElementById("morning_boost_end"),
  roomsContainer: document.getElementById("roomsContainer"),
};

function setStatus(message, type = "warn") {
  els.statusBox.textContent = message;
  els.statusBox.className = `status ${type}`;
}

async function haFetch(path, options = {}) {

  const auth = await window.hassConnection;
  const token = auth.auth.data.access_token;

  const response = await fetch(path, {
    ...options,
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(options.headers || {})
    }
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status} ${text}`);
  }

  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

async function callService(domain, service, data = {}) {
  await haFetch(`/api/services/${domain}/${service}`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

function sortByEntityId(items) {
  return [...items].sort((a, b) => a.entity_id.localeCompare(b.entity_id));
}

function prettyEntityLabel(stateObj) {
  const name = stateObj.attributes?.friendly_name || stateObj.entity_id;
  return `${name} (${stateObj.entity_id})`;
}

function buildSelectOptions(selectEl, options, selectedValue, includeEmpty = true, emptyLabel = "— Nicht gesetzt —") {
  selectEl.innerHTML = "";

  if (includeEmpty) {
    const emptyOption = document.createElement("option");
    emptyOption.value = "";
    emptyOption.textContent = emptyLabel;
    selectEl.appendChild(emptyOption);
  }

  for (const item of options) {
    const option = document.createElement("option");
    option.value = item.entity_id;
    option.textContent = prettyEntityLabel(item);
    if (item.entity_id === selectedValue) {
      option.selected = true;
    }
    selectEl.appendChild(option);
  }
}

function normalizeConfig(input) {
  const cfg = {
    ...structuredClone(DEFAULTS),
    ...(input || {}),
  };

  cfg.enabled = cfg.enabled !== false;
  cfg.main_thermostat = cfg.main_thermostat || "";
  cfg.main_sensor = cfg.main_sensor || "";
  cfg.boost_delta = Number(cfg.boost_delta ?? DEFAULTS.boost_delta);
  cfg.tolerance = Number(cfg.tolerance ?? DEFAULTS.tolerance);
  cfg.night_start = cfg.night_start || DEFAULTS.night_start;
  cfg.morning_boost_start = cfg.morning_boost_start || DEFAULTS.morning_boost_start;
  cfg.morning_boost_end = cfg.morning_boost_end || DEFAULTS.morning_boost_end;
  cfg.rooms = cfg.rooms && typeof cfg.rooms === "object" ? cfg.rooms : {};

  for (const [roomId, room] of Object.entries(cfg.rooms)) {
    cfg.rooms[roomId] = {
      label: room.label || roomId,
      area_id: room.area_id || "",
      thermostat: room.thermostat || "",
      sensor: room.sensor || "",
      target_day: Number(room.target_day ?? 21.0),
      target_night: Number(room.target_night ?? 18.0),
      enabled: room.enabled !== false,
    };
  }

  return cfg;
}

async function loadAllStates() {
  const states = await haFetch("/api/states");
  appState.allStates = Array.isArray(states) ? states : [];

  appState.climates = sortByEntityId(
    appState.allStates.filter((s) => s.entity_id.startsWith("climate."))
  );

  appState.sensors = sortByEntityId(
    appState.allStates.filter((s) => {
      if (!s.entity_id.startsWith("sensor.")) {
        return false;
      }

      const deviceClass = s.attributes?.device_class;
      if (deviceClass === "temperature") {
        return true;
      }

      const id = s.entity_id.toLowerCase();
      const looksLikeTemp = id.includes("temp") || id.includes("temperature");
      const numericState = !Number.isNaN(Number(s.state));
      return looksLikeTemp && numericState;
    })
  );
}

async function loadConfig() {
  let stateObj = null;

  try {
    stateObj = await haFetch(`/api/states/${CONFIG_ENTITY_ID}`);
  } catch {
    stateObj = null;
  }

  const attrs = stateObj?.attributes || {};
  appState.config = normalizeConfig(attrs);
}

function renderGlobalForm() {
  const cfg = appState.config;

  els.enabled.checked = cfg.enabled;
  els.boost_delta.value = Number.isFinite(cfg.boost_delta) ? cfg.boost_delta : DEFAULTS.boost_delta;
  els.tolerance.value = Number.isFinite(cfg.tolerance) ? cfg.tolerance : DEFAULTS.tolerance;
  els.night_start.value = cfg.night_start || DEFAULTS.night_start;
  els.morning_boost_start.value = cfg.morning_boost_start || DEFAULTS.morning_boost_start;
  els.morning_boost_end.value = cfg.morning_boost_end || DEFAULTS.morning_boost_end;

  buildSelectOptions(
    els.main_thermostat,
    appState.climates,
    cfg.main_thermostat,
    true,
    "— Bitte wählen —"
  );

  buildSelectOptions(
    els.main_sensor,
    appState.sensors,
    cfg.main_sensor,
    true,
    "— Automatisch / keiner —"
  );
}

function roomCardTemplate(roomId, room) {
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
        <input class="room-label" type="text" value="${escapeAttr(room.label || "")}" />
      </div>

      <div class="field">
        <label>Area-ID</label>
        <input class="room-area-id" type="text" value="${escapeAttr(room.area_id || "")}" />
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
        <input class="room-target-day" type="number" min="5" max="30" step="0.1" value="${escapeAttr(room.target_day)}" />
      </div>

      <div class="field">
        <label>Zieltemperatur Nacht (°C)</label>
        <input class="room-target-night" type="number" min="5" max="30" step="0.1" value="${escapeAttr(room.target_night)}" />
      </div>
    </div>
  `;

  const thermostatSelect = wrapper.querySelector(".room-thermostat");
  const sensorSelect = wrapper.querySelector(".room-sensor");

  buildSelectOptions(
    thermostatSelect,
    appState.climates,
    room.thermostat || "",
    true,
    "— Nicht gesetzt —"
  );

  buildSelectOptions(
    sensorSelect,
    appState.sensors,
    room.sensor || "",
    true,
    "— Nicht gesetzt —"
  );

  wrapper.querySelector(".room-delete-btn").addEventListener("click", () => {
    delete appState.config.rooms[roomId];
    renderRooms();
  });

  return wrapper;
}

function renderRooms() {
  els.roomsContainer.innerHTML = "";

  const roomEntries = Object.entries(appState.config.rooms || {});
  if (!roomEntries.length) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "Noch keine Räume vorhanden.";
    els.roomsContainer.appendChild(empty);
    return;
  }

  for (const [roomId, room] of roomEntries) {
    els.roomsContainer.appendChild(roomCardTemplate(roomId, room));
  }
}

function collectFormState() {
  const cfg = structuredClone(appState.config);

  cfg.enabled = els.enabled.checked;
  cfg.main_thermostat = els.main_thermostat.value || "";
  cfg.main_sensor = els.main_sensor.value || "";
  cfg.boost_delta = Number(els.boost_delta.value || DEFAULTS.boost_delta);
  cfg.tolerance = Number(els.tolerance.value || DEFAULTS.tolerance);
  cfg.night_start = els.night_start.value || DEFAULTS.night_start;
  cfg.morning_boost_start = els.morning_boost_start.value || DEFAULTS.morning_boost_start;
  cfg.morning_boost_end = els.morning_boost_end.value || DEFAULTS.morning_boost_end;

  const roomNodes = els.roomsContainer.querySelectorAll(".room");
  const nextRooms = {};

  for (const node of roomNodes) {
    const roomId = node.dataset.roomId;
    nextRooms[roomId] = {
      label: node.querySelector(".room-label").value.trim() || roomId,
      area_id: node.querySelector(".room-area-id").value.trim(),
      thermostat: node.querySelector(".room-thermostat").value || "",
      sensor: node.querySelector(".room-sensor").value || "",
      target_day: Number(node.querySelector(".room-target-day").value || 21),
      target_night: Number(node.querySelector(".room-target-night").value || 18),
      enabled: node.querySelector(".room-enabled").checked,
    };
  }

  cfg.rooms = nextRooms;
  return normalizeConfig(cfg);
}

function createRoomId() {
  return `room_${Math.random().toString(16).slice(2, 10)}`;
}

function addRoom() {
  const roomId = createRoomId();
  appState.config.rooms[roomId] = {
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
    setStatus("Speichere Konfiguration …", "warn");
    const cfg = collectFormState();

    await callService(DOMAIN, "update_config", {
      config: cfg,
    });

    appState.config = cfg;
    setStatus("Konfiguration erfolgreich gespeichert.", "ok");
  } catch (error) {
    console.error(error);
    setStatus(`Speichern fehlgeschlagen: ${error.message}`, "err");
  }
}

async function reloadRooms() {
  try {
    setStatus("Erkenne Räume neu …", "warn");
    await callService(DOMAIN, "reload", {});
    await refreshAll();
    setStatus("Räume wurden neu erkannt.", "ok");
  } catch (error) {
    console.error(error);
    setStatus(`Neu-Erkennung fehlgeschlagen: ${error.message}`, "err");
  }
}

async function refreshAll() {
  await loadAllStates();
  await loadConfig();
  renderGlobalForm();
  renderRooms();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value);
}

function bindEvents() {
  els.saveBtn.addEventListener("click", saveConfig);
  els.reloadRoomsBtn.addEventListener("click", reloadRooms);
  els.reloadConfigBtn.addEventListener("click", async () => {
    try {
      setStatus("Lade Konfiguration neu …", "warn");
      await refreshAll();
      setStatus("Konfiguration neu geladen.", "ok");
    } catch (error) {
      console.error(error);
      setStatus(`Neu laden fehlgeschlagen: ${error.message}`, "err");
    }
  });
  els.addRoomBtn.addEventListener("click", addRoom);
}

async function init() {
  bindEvents();

  try {
    await refreshAll();
    setStatus("Konfiguration geladen.", "ok");
  } catch (error) {
    console.error(error);
    setStatus(
      `Initialisierung fehlgeschlagen: ${error.message}. Prüfe, ob die Integration geladen ist.`,
      "err"
    );
  }
}

init();
