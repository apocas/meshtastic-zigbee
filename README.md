# Meshtastic Zigbee Bridge

A Python application that bridges MQTT events from Zigbee2MQTT to Meshtastic radio networks.

## Features

- Listens to MQTT messages from Zigbee2MQTT
- Filters for motion detection events (occupancy sensors)
- Filters for door/window sensor events (contact and tamper detection)
- Sends notifications to a specific Meshtastic channel
- Configurable via environment variables

## Setup

1. Install uv if you haven't already:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Install the Meshtastic CLI:

   ```bash
   pip install meshtastic
   ```

3. Install dependencies:

   ```bash
   uv sync
   ```

4. Configure environment variables (copy `.env.example` to `.env` and modify):
   - `MQTT_BROKER`: MQTT broker hostname/IP
   - `MQTT_PORT`: MQTT broker port (default: 1883)
   - `MQTT_TOPICS`: Comma-separated list of Zigbee2MQTT topics to monitor
   - `MESHTASTIC_PORT`: Serial port for Meshtastic device (default: /dev/ttyUSB0)
   - `CHANNEL_INDEX`: Meshtastic channel index to send messages to (default: 5)

5. Run the application:

   ```bash
   uv run python main.py
   ```

## Configuration

The application monitors the configured MQTT topics for sensor events:

- **Motion Detection**: When an occupancy event with `"occupancy": true` is detected, it sends a "Motion detected" message
- **Door/Window Sensors**: When a contact sensor reports `"contact": false` or `"tamper": true`, it sends a "Door triggered!" message

All messages are sent to the specified Meshtastic channel index.
