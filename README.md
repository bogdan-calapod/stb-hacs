<p align="center">
  <img src="custom_components/stb_bucuresti/brand/icon@2x.png" alt="STB Bucuresti Logo" width="150">
</p>

<h1 align="center">STB Bucuresti - Home Assistant Unofficial Integration</h1>

<p align="center">
  <em>This integration is in no way officially affiliated or linked with STB</em>
</p>

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Home Assistant integration for **real-time tracking** of public transport vehicles in Bucharest, Romania (STB - Societatea de Transport Bucuresti).

> [!WARNING]
> 
> This is a *heavily AI-built* integration. I built this for my own personal use - while YMMV, feedback is always welcome. 

## Features

- **Real-time vehicle tracking** - Track trams, buses, and trolleybuses in real-time
- **Device trackers** - Each vehicle becomes a device tracker with GPS coordinates
- **Line sensors** - See how many vehicles are active on each monitored line
- **Proximity automations** - Create automations based on vehicle proximity to a location

## Use Cases

### "If phone X is on Tram 41, do something"

You can create automations that trigger when a phone (person) is near a specific tram/bus. This works by:

1. The integration tracks all vehicles on the lines you select
2. Each vehicle has GPS coordinates (latitude/longitude)
3. You can use Home Assistant's proximity features or template sensors to calculate distance between your phone and vehicles

**Example automation:**
```yaml
description: "Notify when I'm near Tram 41"
mode: single
triggers:
  - trigger: time_pattern
    seconds: "/10"
conditions: []
actions:
  - choose:
      - conditions:
          - condition: template
            value_template: >
              {% set phone = 'device_tracker.my_phone' %}
              {% set phone_lat = state_attr(phone, 'latitude') %}
              {% set phone_lon = state_attr(phone, 'longitude') %}
              {% if phone_lat and phone_lon %}
                {% for state in states.device_tracker if 'stb_line41_' in state.entity_id %}
                  {% set vlat = state.attributes.latitude %}
                  {% set vlon = state.attributes.longitude %}
                  {% if vlat and vlon and distance(phone_lat, phone_lon, vlat, vlon) < 0.1 %}
                    true
                  {% endif %}
                {% endfor %}
              {% endif %}
        sequence:
          - action: notify.mobile_app_my_phone
            data:
              message: "You're near Tram 41!"
```

## Installation

### HACS (Recommended)

1. Add this repository to HACS as a custom repository
2. Search for "STB Bucuresti" in HACS
3. Install the integration
4. Restart Home Assistant
5. Add the integration from Settings -> Devices & Services

### Manual Installation

1. Download the `custom_components/stb_bucuresti` folder
2. Copy it to your Home Assistant `custom_components` directory
3. Restart Home Assistant
4. Add the integration from Settings -> Devices & Services

## Configuration

1. Go to **Settings** -> **Devices & Services**
2. Click **Add Integration**
3. Search for "STB Bucuresti"
4. Select the transport lines you want to monitor
5. Set the update interval (default: 30 seconds, minimum: 10 seconds)

## Entities

### Device Trackers

For each vehicle on your monitored lines, a device tracker is created:
- Entity ID: `device_tracker.stb_{line_id}_{vehicle_number}`
- Attributes:
  - `latitude` / `longitude` - GPS coordinates
  - `vehicle_number` - Vehicle identification number
  - `vehicle_type` - Type (Tramvai, Autobuz, Troleibuz)
  - `line_id` / `line_name` - Line information
  - `direction` - Direction of travel (0 or 1)

### Sensors

- **Line Vehicle Count** - Shows how many vehicles are active on each monitored line
  - Entity ID: `sensor.stb_line_{line_id}_count`
  
- **Total Vehicles** - Shows total number of tracked vehicles
  - Entity ID: `sensor.stb_total_vehicles`

## Supported Transport Types

- **Tramvai** (Tram) - Lines 1, 2, 4, 5, 7, 10, 11, 14, 17, 21, 23, 25, 27, 32, 36, 41, 44, 47, 53, 55
- **Autobuz** (Bus) - All STB bus lines
- **Troleibuz** (Trolleybus) - Lines 61, 62, 63, 66, 69, 70, 72, 73, 76, 79, 85, 86, 90, 93, 95, 96, 97

## API

This integration uses the public API from [info.stb.ro](https://info.stb.ro), which provides real-time vehicle positions for STB vehicles.

## Notes

- The API updates vehicle positions approximately every 10-30 seconds
- Vehicles may temporarily disappear from the API when they are at terminals or depots
- The integration creates device trackers dynamically as vehicles appear on the monitored lines

## Contributing

Contributions are welcome! Please open an issue or pull request on GitHub.

## License

This project is licensed under the MIT License.

## Disclaimer

This integration is not affiliated with STB Bucuresti. It uses publicly available data from the info.stb.ro website.
