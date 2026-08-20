# ShevLogger for Home Assistant

[![HACS validation](https://github.com/AlexMarvel/ShevLogger-HA/actions/workflows/validate.yml/badge.svg)](https://github.com/AlexMarvel/ShevLogger-HA/actions/workflows/validate.yml)
[![GitHub release](https://img.shields.io/github/v/release/AlexMarvel/ShevLogger-HA)](https://github.com/AlexMarvel/ShevLogger-HA/releases)

Local Home Assistant integration for the **SmartShev ShevLogger** inverter
gateway. It discovers loggers automatically through mDNS and exposes all
values declared by the active inverter profile as Home Assistant sensors.

The integration talks directly to the logger over the local network. It does
not require the SmartShev cloud, MQTT or a fixed IP address.

## Features

- automatic `_shevlogger._tcp.local.` discovery;
- manual setup by local IP address or hostname;
- activation-key authentication;
- all inverter profile values fetched in one request every 5 seconds;
- stable entity IDs based on the logger device ID;
- automatic entity catalogue reload when the inverter profile changes;
- Ukrainian and English setup screens.

## Install with HACS

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=AlexMarvel&repository=ShevLogger-HA&category=integration)

1. Open the button above, or open **HACS → Integrations → Custom
   repositories**.
2. Add `https://github.com/AlexMarvel/ShevLogger-HA` with category
   **Integration**.
3. Download **ShevLogger** and restart Home Assistant.
4. Open **Settings → Devices & services**. Select the discovered ShevLogger and
   enter its activation key.

If automatic discovery is unavailable between VLANs, select **Add
integration → ShevLogger** and enter the logger IP/hostname and activation key
manually.

## Manual installation

Copy `custom_components/shevlogger` to
`/config/custom_components/shevlogger`, then restart Home Assistant.

## How polling works

Entity metadata is downloaded only during setup or after changing the inverter
profile. Current values are then fetched with a single local HTTP request every
5 seconds, regardless of the number of sensors. The logger does not run an MQTT
client or a separate Home Assistant background task.

## Requirements

- Home Assistant 2024.8 or newer;
- ShevLogger firmware with local Home Assistant API v1;
- Home Assistant and ShevLogger reachable on the same local network;
- the ShevLogger activation key.

Project website: [logger.smartshev.pp.ua](https://logger.smartshev.pp.ua)

## Українською

Інтеграція автоматично знаходить ShevLogger у локальній мережі та додає всі
сенсори активного профілю інвертора. Якщо mDNS між мережами недоступний,
ShevLogger можна додати вручну за IP-адресою. Для входу використовується ключ
активації логера.
