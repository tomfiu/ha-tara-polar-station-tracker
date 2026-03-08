# Tara Polar Station Tracker

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A Home Assistant custom integration that provides real-time tracking and polar analytics for the **Tara Polar Station**, a drifting Arctic research observatory operated by the [Tara Ocean Foundation](https://fondationtaraocean.org/).

## Features

- **Real-time AIS tracking** via [AISStream.io](https://aisstream.io/) (free)
- **Derived expedition metrics**: distance from home, distance to North Pole, bearing, days since departure
- **Polar context**: Arctic Circle detection, polar day/night detection, solar elevation
- **Mission phase tracking**: Pre-departure, Transit, Drifting
- **Webcam integration**: Live Panomax panoramic camera feed
- **Home Assistant events**: Milestone transitions for automations

## Entities

### Sensors

| Entity | Description | Unit |
|--------|-------------|------|
| `sensor.tara_polar_station_tracker_latitude` | Current latitude | ° |
| `sensor.tara_polar_station_tracker_longitude` | Current longitude | ° |
| `sensor.tara_polar_station_tracker_speed` | Vessel speed | kn |
| `sensor.tara_polar_station_tracker_course` | Course heading | ° |
| `sensor.tara_polar_station_tracker_last_report` | Last AIS report time | timestamp |
| `sensor.tara_polar_station_tracker_distance_from_home` | Distance from your HA installation | km |
| `sensor.tara_polar_station_tracker_distance_to_north_pole` | Distance to the North Pole | km |
| `sensor.tara_polar_station_tracker_bearing_from_home` | Compass bearing from home | ° |
| `sensor.tara_polar_station_tracker_days_since_departure` | Expedition duration | days |
| `sensor.tara_polar_station_tracker_solar_elevation` | Sun altitude at station | ° |
| `sensor.tara_polar_station_tracker_mission_phase` | Current expedition phase | — |

### Binary Sensors

| Entity | Description |
|--------|-------------|
| `binary_sensor.tara_polar_station_tracker_in_arctic_circle` | Station is above 66.5°N |
| `binary_sensor.tara_polar_station_tracker_in_polar_day` | Sun never sets at station |
| `binary_sensor.tara_polar_station_tracker_in_polar_night` | Sun never rises at station |
| `binary_sensor.tara_polar_station_tracker_stationary` | Speed below 0.5 kn |

### Camera (optional)

| Entity | Description |
|--------|-------------|
| `camera.tara_polar_station_tracker_webcam` | Panomax panoramic webcam |

## Events

| Event | Trigger |
|-------|---------|
| `tara_polar_station_tracker_position_updated` | Every data refresh |
| `tara_polar_station_tracker_entered_arctic_circle` | Crossed 66.5°N northbound |
| `tara_polar_station_tracker_entered_polar_night` | Polar night begins |
| `tara_polar_station_tracker_stationary` | Vessel stops moving |
| `tara_polar_station_tracker_resumed_transit` | Vessel starts moving |

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant.
2. Go to **Integrations** > **Custom repositories**.
3. Add this repository URL and select **Integration**.
4. Install **Tara Polar Station Tracker**.
5. Restart Home Assistant.

### Manual

1. Copy the `custom_components/tara_polar_station_tracker` folder into your Home Assistant `custom_components/` directory.
2. Restart Home Assistant.

## Configuration

1. Get a free API key from [AISStream.io](https://aisstream.io/) (sign in with GitHub).
2. In Home Assistant, go to **Settings** > **Devices & Services** > **Add Integration**.
3. Search for **Tara Polar Station Tracker**.
4. Enter your AISStream API key.

### Options

After setup, configure optional settings via the integration's **Configure** button:

| Option | Default | Description |
|--------|---------|-------------|
| Update interval | 15 min | Polling frequency (5–60 min) |
| Home latitude | HA home | Override latitude for distance calculations |
| Home longitude | HA home | Override longitude for distance calculations |
| Departure date | 2026-07-01 | Expedition start date for day counter |
| Enable webcam | On | Toggle Panomax camera entity |

## Example Automations

### Notify when station enters polar night

```yaml
automation:
  - alias: "Tara enters polar night"
    trigger:
      - platform: state
        entity_id: binary_sensor.tara_polar_station_tracker_in_polar_night
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          message: "Tara Polar Station has entered polar night!"
```

### Daily distance update

```yaml
automation:
  - alias: "Tara daily distance"
    trigger:
      - platform: time
        at: "09:00:00"
    action:
      - service: notify.mobile_app
        data:
          message: >
            Tara is {{ states('sensor.tara_polar_station_tracker_distance_to_north_pole') }} km
            from the North Pole ({{ states('sensor.tara_polar_station_tracker_mission_phase') }}).
```

## Dashboard Examples

### Map card

```yaml
type: map
entities:
  - entity: sensor.tara_polar_station_tracker_latitude
```

### Gauge card

```yaml
type: gauge
entity: sensor.tara_polar_station_tracker_distance_to_north_pole
name: Distance to North Pole
unit: km
min: 0
max: 5000
```

## Data Source

Position data is sourced from [AISStream.io](https://aisstream.io/), a free real-time AIS data streaming service. The vessel is identified by MMSI `228471700`.

Webcam imagery is sourced from [Panomax](https://tara-polar-station.panomax.com/).

## Links

- [GitHub Repository](https://github.com/tomfiu/ha-tara-polar-station-tracker)
- [Issue Tracker](https://github.com/tomfiu/ha-tara-polar-station-tracker/issues)

## License

[MIT](LICENSE)
