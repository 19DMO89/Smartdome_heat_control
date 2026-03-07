<h1>
<img src="https://raw.githubusercontent.com/19DMO89/smartdome_heat_control/main/images/icon.png" width="32" align="center">
Smartdome Heat Control
</h1>

[![HACS
Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)\
[![HA
Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://home-assistant.io)\
[![License:
MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Die professionelle Heizungssteuerung für Home Assistant.\
**Smartdome Heat Control** kombiniert automatische Raumerkennung mit
einem dedizierten Management‑Dashboard direkt in deiner Seitenleiste.

Die Integration synchronisiert **Hauptthermostat und Raumthermostate**,
um effizient zu heizen und gleichzeitig Energie zu sparen.

------------------------------------------------------------------------

# ✨ Features

## 🖥️ Eigenes Dashboard

Verwalte alle Räume und Einstellungen direkt über einen neuen Eintrag in
der Home‑Assistant‑Seitenleiste.

------------------------------------------------------------------------

## 🏠 Automatische Raumerkennung

Die Integration liest deine **Home Assistant Areas** aus und erkennt
automatisch:

-   Thermostate (`climate.*`)
-   Temperatursensoren (`sensor.*`)

Räume können jederzeit neu erkannt werden.

------------------------------------------------------------------------

## ➕ Dynamische Raumverwaltung

Direkt im Dashboard möglich:

-   Räume hinzufügen
-   Räume löschen
-   Thermostat auswählen
-   Sensor auswählen
-   Raum aktiv / deaktivieren

------------------------------------------------------------------------

## 🌡️ Live‑Temperaturanzeige

Im Dashboard wird neben jedem Raum die aktuelle Temperatur angezeigt.

Beispiel:

    Esszimmer   21.4°C

Die Temperatur stammt direkt vom ausgewählten Sensor.

------------------------------------------------------------------------

## 🔥 Heizstatus Anzeige

Wenn ein Raum gerade heizt, erscheint ein **Flammensymbol**.

Beispiel:

    Esszimmer   21.4°C 🔥

Die Anzeige basiert auf:

    climate.* → hvac_action = heating

------------------------------------------------------------------------

## 🕒 Individuelle Zeitsteuerung pro Raum

Jeder Raum kann eigene Zeiten besitzen:

  Einstellung   Beschreibung
  ------------- ---------------------------
  Tag Start     Beginn der Tagtemperatur
  Nacht Start   Beginn der Nachtabsenkung

Damit können Räume unterschiedliche Heizzeiten haben.

------------------------------------------------------------------------

## 📋 Globale Zeiten übernehmen

Im Dashboard gibt es einen Button:

    Globale Zeiten in alle Räume übernehmen

Damit werden automatisch gesetzt:

    Tag Start = globale Tagzeit
    Nacht Start = globale Nachtzeit

Ideal wenn nur einzelne Räume abweichen sollen.

------------------------------------------------------------------------

## 🌙 Intelligente Absenkung

Räume ohne Wärmebedarf werden automatisch reduziert, damit sie **nicht
unnötig mitheizen**.

Das spart Energie und verhindert Überheizen.

------------------------------------------------------------------------

## 🎯 Präzise Ventilsteuerung

Wenn ein Raum zu kalt ist:

    Raumthermostat = Soll + Boost

Andere Räume werden automatisch reduziert.

------------------------------------------------------------------------

## 🔧 Hauptthermostat‑Steuerung

Wenn **ein Raum Wärme benötigt**:

    Hauptthermostat = max(Sollwerte) + Boost

Dadurch wird die Heizung nur aktiviert wenn tatsächlich Bedarf besteht.

------------------------------------------------------------------------

## ⚡ Optimierter Home Assistant Start

Der Heizcontroller startet erst nach:

    EVENT_HOMEASSISTANT_STARTED

Dadurch wird der **Start von Home Assistant nicht verzögert**.

------------------------------------------------------------------------

## 📱 Lovelace Integration

Die Integration ist perfekt abgestimmt auf:

**Smartdome Heat Card**\
https://github.com/19DMO89/smartdome_heat_card

------------------------------------------------------------------------

# 📋 Voraussetzungen

-   Home Assistant **2024.1 oder neuer**
-   Ein zentrales `climate.*` Thermostat (Heizanlage)
-   Optionale Heizkörperthermostate (`climate.*`)
-   Optionale Temperatursensoren (`sensor.*`) pro Raum

------------------------------------------------------------------------

# 🚀 Installation via HACS

1.  Öffne **HACS → Integrationen**
2.  Drei Punkte **⋮ → Benutzerdefinierte Repositorys**
3.  Repository hinzufügen:

```{=html}
<!-- -->
```
    https://github.com/19DMO89/smartdome_heat_control

Kategorie:

    Integration

4.  **Smartdome Heat Control installieren**
5.  **Home Assistant neu starten**

------------------------------------------------------------------------

# ⚙️ Einrichtung & Dashboard

## 1️⃣ Integration hinzufügen

    Einstellungen
    → Geräte & Dienste
    → Integration hinzufügen
    → Smartdome Heat Control

------------------------------------------------------------------------

## 2️⃣ Smartdome Panel

Nach der Installation erscheint in der **Sidebar**:

    Smartdome Heat

Dort kannst du:

-   Räume verwalten
-   Sensoren auswählen
-   Thermostate auswählen
-   Zieltemperaturen einstellen
-   Tag/Nacht Zeiten definieren
-   Konfiguration speichern

------------------------------------------------------------------------

# 🧠 Funktionsweise

Das System arbeitet nach einem Bedarfs‑Prinzip.

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
    Andere Ventile  = reduziert

------------------------------------------------------------------------

# 🕒 Zeitsteuerung

  Modus             Zeitraum                   Verhalten
  ----------------- -------------------------- ---------------------
  🌙 Nacht          Nacht‑Start → Tag‑Start    target_night
  🔥 Morgen Boost   Boost‑Start → Boost‑Ende   schnelles Aufheizen
  ☀️ Tag            Boost‑Ende → Nacht‑Start   target_day

------------------------------------------------------------------------

# 📝 WebSocket & Services

### WebSocket

    smartdome_heat_control/save_config

Speichert das komplette Konfigurations‑JSON.

### Services

    smartdome_heat_control.update_config
    smartdome_heat_control.add_room
    smartdome_heat_control.reload
    smartdome_heat_control.remove_room

------------------------------------------------------------------------

# 🌍 English

## Description

Smartdome Heat Control is a Home Assistant integration for **coordinated
heating control** using:

-   a **central thermostat**
-   multiple **room thermostats**
-   optional **temperature sensors per room**

The system boosts the main thermostat whenever a room requires heat and
prevents other rooms from overheating.

### Features

-   Dedicated **sidebar dashboard**
-   Automatic **room discovery**
-   Dynamic **room management**
-   **Live temperature display**
-   **Heating indicator 🔥**
-   Individual **room schedules**
-   Global schedule copy
-   Optimized startup (no HA startup delay)

### Installation

Install via **HACS Custom Repository**:

    https://github.com/19DMO89/smartdome_heat_control

Restart Home Assistant afterwards.

------------------------------------------------------------------------

# 📄 Lizenz

Dieses Projekt steht unter der **MIT Lizenz**.\
Siehe Datei:

    LICENSE

------------------------------------------------------------------------

*Entwickelt von [19DMO89](https://github.com) -- Teil der
Smartdome-Serie.*
