# <img src="https://raw.githubusercontent.com" width="48" align="center"> Smartdome Heat Control

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![HA Version](https://img.shields.io)](https://home-assistant.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Die professionelle Heizungssteuerung für Home Assistant. **Smartdome Heat Control** kombiniert automatische Raumerkennung mit einem dedizierten Management-Dashboard direkt in deiner Seitenleiste.

---

## ✨ Features

- 🖥️ **Eigenes Dashboard** – Verwalte alle Räume und Einstellungen direkt über den neuen Eintrag in der HA-Seitenleiste.
- 🏠 **Automatische Raumerkennung** – Liest deine HA-Areas aus und findet Thermostate & Sensoren von selbst.
- ➕ **Dynamische Verwaltung** – Räume hinzufügen, bearbeiten oder löschen direkt über die grafische Oberfläche.
- 🌙 **Intelligente Absenkung** – Nachtabsenkung und Morgen-Boost (schnelles Aufheizen) individuell pro Raum.
- 🎯 **Präzise Ventilsteuerung** – Kalte Räume öffnen voll, warme Räume drosseln intelligent, um Energie zu sparen.
- 🔧 **Hauptthermostat-Koppelung** – Steuert deine zentrale Heizanlage basierend auf dem Wärmebedarf aller Räume.
- 📱 **Lovelace-Integration** – Perfekt abgestimmt auf die [Smartdome Heat Card](https://github.com/19DMO89/smartdome_heat_card).

---

## 📋 Voraussetzungen

- Home Assistant 2024.1 oder neuer
- Ein zentrales `climate.*` Thermostat (Heizanlage)
- Optionale Heizkörperthermostate (`climate.*`) und Temperatursensoren (`sensor.*`) pro Raum

---

## 🚀 Installation via HACS

1. Öffne **HACS** → **Integrationen**.
2. Klicke oben rechts auf das Drei-Punkte-Menü **⋮** → **Benutzerdefinierte Repositorys**.
3. Füge die URL hinzu: `https://github.com/19DMO89/smartdome_heat_control`
4. Wähle als Kategorie **Integration** und klicke auf **Hinzufügen**.
5. Suche in der Liste nach **Smartdome Heat Control** und klicke auf **Herunterladen**.
6. **Starte Home Assistant neu.**

---

## ⚙️ Einrichtung & Dashboard

### 1. Integration hinzufügen
Gehe zu **Einstellungen** → **Geräte & Dienste** → **Integration hinzufügen** und suche nach **"Smartdome Heat Control"**.

### 2. Das neue Smartdome Panel
Nach der Installation erscheint in deiner **Seitenleiste** ein neues Icon (Radiator) namens **"Smartdome Heat"**. 
Dort kannst du:
- Alle erkannten Räume auf einen Blick sehen.
- Thermostate und Sensoren per Dropdown zuweisen.
- Zieltemperaturen für Tag und Nacht bequem anpassen.
- Mit einem Klick die gesamte Konfiguration speichern.

---

## 🧠 Funktionsweise

Das System arbeitet nach einem Bedarfs-Prinzip:



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

### Zeitsteuerung

| Modus | Zeitraum | Verhalten |
|-------|----------|-----------|
| 🌙 **Nacht** | Nacht-Start bis Boost-Start | Alle Räume auf `target_night` |
| 🔥 **Boost** | Boost-Start bis Boost-Ende | Schnelles Aufheizen mit `Boost-Delta` |
| ☀️ **Tag** | Boost-Ende bis Nacht-Start | Normalbetrieb auf `target_day` |

---

## 📝 WebSocket & Services

Für Entwickler bietet die Integration eine WebSocket-Schnittstelle:
- `smartdome_heat_control/save_config`: Speichert das gesamte Konfigurations-JSON.

Verfügbare Services:
- `smartdome_heat_control.update_config`
- `smartdome_heat_control.add_room`
- `smartdome_heat_control.reload`

---

## 📄 Lizenz

Dieses Projekt lizenziert unter der MIT-Lizenz – siehe die [LICENSE](LICENSE) Datei für Details.

---
*Entwickelt von [19DMO89](https://github.com) – Teil der Smartdome-Serie.*
