#!/usr/bin/env python3
"""
Meshtastic Zigbee Bridge
Listens to MQTT events from Zigbee2MQTT and forwards motion detection events to Meshtastic nodes.
"""

import json
import logging
import os
import signal
import subprocess
import sys
import time
from typing import Optional

import paho.mqtt.client as mqtt


class MeshtasticZigbeeBridge:
    def __init__(self):
        self.setup_logging()
        self.load_config()
        self.mqtt_client: Optional[mqtt.Client] = None
        self.running = True
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def setup_logging(self):
        """Setup logging configuration."""
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)

    def load_config(self):
        """Load configuration from environment variables."""
        self.mqtt_broker = os.getenv('MQTT_BROKER', 'localhost')
        self.mqtt_port = int(os.getenv('MQTT_PORT', '1883'))
        self.mqtt_username = os.getenv('MQTT_USERNAME')
        self.mqtt_password = os.getenv('MQTT_PASSWORD')
        self.mqtt_topics = os.getenv('MQTT_TOPICS', 'zigbee2mqtt/motion_outdoor,zigbee2mqtt/door_outdoor').split(',')
        self.meshtastic_port = os.getenv('MESHTASTIC_PORT', '/dev/ttyUSB0')
        self.channel_index = int(os.getenv('CHANNEL_INDEX', '5'))
        
        self.logger.info(f"Configuration loaded:")
        self.logger.info(f"  MQTT Broker: {self.mqtt_broker}:{self.mqtt_port}")
        self.logger.info(f"  MQTT Topics: {', '.join(self.mqtt_topics)}")
        self.logger.info(f"  Meshtastic Port: {self.meshtastic_port}")
        self.logger.info(f"  Channel Index: {self.channel_index}")

    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback for when MQTT client connects to broker."""
        if rc == 0:
            self.logger.info("Connected to MQTT broker")
            for topic in self.mqtt_topics:
                topic = topic.strip()
                client.subscribe(topic)
                self.logger.info(f"Subscribed to topic: {topic}")
        else:
            self.logger.error(f"Failed to connect to MQTT broker, return code {rc}")

    def on_mqtt_disconnect(self, client, userdata, rc):
        """Callback for when MQTT client disconnects from broker."""
        self.logger.info(f"Disconnected from MQTT broker, return code {rc}")

    def on_mqtt_message(self, client, userdata, msg):
        """Handle incoming MQTT messages."""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            self.logger.debug(f"Received message on topic '{topic}': {payload}")
            
            # Parse JSON payload
            data = json.loads(payload)
            
            # Check for motion detection event
            if 'occupancy' in data and data.get('occupancy') is True:
                self.logger.info("Motion detected! Sending message to Meshtastic channel...")
                self.send_meshtastic_message("Motion detected")
            
            # Check for door sensor events
            elif ('tamper' in data and data.get('tamper') is True) or \
                 ('contact' in data and data.get('contact') is False):
                self.logger.info("Door triggered! Sending message to Meshtastic channel...")
                self.send_meshtastic_message("Door triggered!")
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON payload: {e}")
        except Exception as e:
            self.logger.error(f"Error processing MQTT message: {e}")

    def setup_mqtt_client(self):
        """Setup and configure MQTT client."""
        self.mqtt_client = mqtt.Client()
        
        # Set username and password if provided
        if self.mqtt_username and self.mqtt_password:
            self.mqtt_client.username_pw_set(self.mqtt_username, self.mqtt_password)
        
        # Set callbacks
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
        self.mqtt_client.on_message = self.on_mqtt_message
        
        # Enable logging for MQTT client
        self.mqtt_client.enable_logger(self.logger)

    def check_meshtastic_cli(self):
        """Check if Meshtastic CLI is available."""
        try:
            result = subprocess.run(['meshtastic', '--help'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                self.logger.info("Meshtastic CLI is available")
                return True
            else:
                self.logger.error("Meshtastic CLI returned error")
                return False
        except subprocess.TimeoutExpired:
            self.logger.error("Meshtastic CLI command timed out")
            return False
        except FileNotFoundError:
            self.logger.error("Meshtastic CLI not found. Please install meshtastic package.")
            return False
        except Exception as e:
            self.logger.error(f"Failed to check Meshtastic CLI: {e}")
            return False

    def send_meshtastic_message(self, message: str):
        """Send a text message to the target Meshtastic channel using CLI."""
        try:
            self.logger.info(f"Sending message '{message}' to channel index {self.channel_index}")
            
            # Build the CLI command
            cmd = ['meshtastic', '--port', self.meshtastic_port, '--ch-index', str(self.channel_index), '--send', message]
            
            # Execute the command
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                self.logger.info("Message sent successfully")
                if result.stdout:
                    self.logger.debug(f"Meshtastic output: {result.stdout.strip()}")
            else:
                self.logger.error(f"Failed to send message. Return code: {result.returncode}")
                if result.stderr:
                    self.logger.error(f"Error output: {result.stderr.strip()}")
                if result.stdout:
                    self.logger.error(f"Standard output: {result.stdout.strip()}")
            
        except subprocess.TimeoutExpired:
            self.logger.error("Meshtastic command timed out")
        except Exception as e:
            self.logger.error(f"Failed to send Meshtastic message: {e}")

    def connect_mqtt(self):
        """Connect to MQTT broker."""
        try:
            self.logger.info(f"Connecting to MQTT broker {self.mqtt_broker}:{self.mqtt_port}")
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to MQTT broker: {e}")
            return False

    def run(self):
        """Main application loop."""
        self.logger.info("Starting Meshtastic Zigbee Bridge...")
        
        try:
            # Check if Meshtastic CLI is available
            if not self.check_meshtastic_cli():
                self.logger.error("Meshtastic CLI is not available, exiting")
                return 1
            
            # Setup MQTT client
            self.setup_mqtt_client()
            
            # Connect to MQTT broker
            if not self.connect_mqtt():
                self.logger.error("Failed to connect to MQTT broker, exiting")
                return 1
            
            # Start MQTT client loop
            self.mqtt_client.loop_start()
            
            self.logger.info("Bridge is running. Press Ctrl+C to stop.")
            
            # Main loop
            while self.running:
                try:
                    time.sleep(1)
                except KeyboardInterrupt:
                    break
            
        except Exception as e:
            self.logger.error(f"Fatal error: {e}")
            return 1
        
        finally:
            self.cleanup()
        
        self.logger.info("Bridge stopped")
        return 0

    def cleanup(self):
        """Cleanup resources."""
        self.logger.info("Cleaning up resources...")
        
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()


def main():
    """Entry point for the application."""
    # Load environment variables from .env file if it exists
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # dotenv is optional
    
    bridge = MeshtasticZigbeeBridge()
    return bridge.run()


if __name__ == "__main__":
    sys.exit(main())
