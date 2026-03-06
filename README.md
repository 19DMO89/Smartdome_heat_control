# 🔥 Smart Heating Controller

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2023.1%2B-blue)](https://home-assistant.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Intelligente Heizungssteuerung für Home Assistant mit **automatischer Raumerkennung**, Nachtabsenkung und morgendlichem Aufheizen.

---

## ✨ Features

- 🏠 **Automatische Raumerkennung** – liest deine HA-Areas und findet Thermostate & Sensoren selbst
- ➕ **Beliebig viele Räume** – nachrüsten jederzeit über Einstellungen möglich
- 🌙 **Nachtabsenkung** pro Raum individuell einstellbar
- 🌅 **Morgen-Boost** heizt zwischen zwei Uhrzeiten kurz auf
- 🎯 **Smarte Ventilsteuerung** – kalter Raum öffnet, warme Räume drosseln
- 🔧 **Flexibel** – Räume ohne smartes Thermostat werden über Hauptthermostat mitgeheizt
- 📱 **Lovelace-Karte** verfügbar (separates Repository)

---

## 📋 Voraussetzungen

- Home Assistant 2023.1+
- Ein zentrales `climate.*` Thermostat das die Heizanlage steuert
- Optional: Smarte Heizkörperthermostate (`climate.*`) pro Raum
- Optional: Temperatursensoren (`sensor.*` mit `device_class: temperature`) pro Raum

---

## 🚀 Installation via HACS

1. HACS öffnen → **Integrationen**
2. Oben rechts **⋮ → Benutzerdefinierte Repositorys**
3. URL eingeben: `https://github.com/DEIN-USERNAME/smart-heating`
   Kategorie: **Integration**
4. **Hinzufügen** klicken
5. Integration in der Liste suchen und **Installieren**
6. Home Assistant neu starten

---

## ⚙️ Einrichtung

**Einstellungen → Geräte & Dienste → + Integration → „Smart Heating"**

### Schritt 1: Hauptthermostat & globale Einstellungen
- Hauptthermostat auswählen
- Boost-Delta, Toleranz und Zeiten festlegen

### Schritt 2: Räume bestätigen
- Die Integration erkennt automatisch alle HA-Areas mit Thermostaten/Sensoren
- Einfach bestätigen – fertig!

---

## 🏠 Räume verwalten

**Einstellungen → Geräte & Dienste → Smart Heating → Konfigurieren**

| Aktion | Beschreibung |
|--------|-------------|
| ⚙️ Globale Einstellungen | Zeiten, Boost, Toleranz ändern |
| ✏️ Raum bearbeiten | Thermostat/Sensor zuweisen, Temperaturen anpassen, deaktivieren |
| ➕ Raum hinzufügen | Neuen Raum manuell anlegen |
| 🔍 Räume neu erkennen | Nach Nachrüstung neue Geräte automatisch hinzufügen |

---

## 🧠 Funktionsweise

```
Sensor meldet Temperaturänderung
         │
         ▼
Raum X zu kalt? (Ist < Soll − Toleranz)
    │           │
   Ja          Nein
    │           └─► Normalbetrieb
    ▼               Hauptthermostat = max(alle Sollwerte)
Hauptthermostat = max(Sollwerte) + Boost
Raum X Ventil   = Soll + Boost  (voll auf)
Andere Ventile  = gedrosselt
```

### Zeitplan

```
00:00        05:00 05:30                        22:00
  │───────────┤─────┤────────────────────────────┤───▶
      Nacht   │Boost│           Tag              │Nacht
   (Absenkung)│ 🔥  │       (Normalbetrieb)      │
```

---

## 📝 Services

| Service | Parameter | Beschreibung |
|---------|-----------|--------------|
| `smart_heating.update_config` | `config: {}` | Konfiguration aktualisieren |
| `smart_heating.add_room` | `label`, `thermostat`, `sensor`, `target_day`, `target_night` | Raum hinzufügen |
| `smart_heating.remove_room` | `room_id` | Raum entfernen |
| `smart_heating.reload` | – | Räume neu erkennen |

---

## 📱 Lovelace-Karte

Die passende Dashboard-Karte ist als separates Repository verfügbar:
👉 **[smart-heating-card](https://github.com/DEIN-USERNAME/smart-heating-card)**

---

## 📄 Lizenz

MIT License – siehe [LICENSE](LICENSE)
