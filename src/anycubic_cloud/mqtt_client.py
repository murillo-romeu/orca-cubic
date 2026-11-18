"""
Anycubic Cloud MQTT & Telemetry Bridge.
Connects to Anycubic MQTT broker over TLS (port 8883) to stream real-time printer telemetry
(temperatures, print progress, ACE slots) to OrcaSlicer.
Includes a periodic REST fallback if MQTT packages are unavailable.
"""

import json
import time
import ssl
import logging
import threading

logger = logging.getLogger("anycubic_cloud.mqtt")

MQTT_BROKER = "mqtt-universe.anycubic.com"
MQTT_PORT = 8883


class AnycubicTelemetryBridge:
    def __init__(self, cloud_client, printer_id=None, on_telemetry_callback=None):
        self.cloud_client = cloud_client
        self.printer_id = printer_id
        self.on_telemetry_callback = on_telemetry_callback
        self.running = False
        self.thread = None
        self.mqtt_client = None

    def set_printer(self, printer_id):
        self.printer_id = str(printer_id) if printer_id else None

    def set_callback(self, callback):
        self.on_telemetry_callback = callback

    def start(self):
        """Start the telemetry background loop."""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info(f"Telemetry bridge started for printer {self.printer_id}")

    def stop(self):
        """Stop telemetry monitoring."""
        self.running = False
        if self.mqtt_client:
            try:
                self.mqtt_client.disconnect()
            except Exception:
                pass
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        logger.info("Telemetry bridge stopped")

    def _run_loop(self):
        """Attempt MQTT connection first; fallback to REST polling if needed."""
        has_paho = False
        try:
            import paho.mqtt.client as mqtt
            has_paho = True
        except ImportError:
            logger.info("paho-mqtt not installed; using active REST polling for telemetry.")

        if has_paho and self.cloud_client.token and self.printer_id:
            try:
                self._run_mqtt(mqtt)
                return
            except Exception as e:
                logger.warning(f"MQTT connection failed ({e}); falling back to REST polling.")

        # REST Polling Fallback loop (every 3 seconds)
        while self.running:
            try:
                if self.printer_id:
                    raw_status = self.cloud_client.get_printer_status(self.printer_id)
                    if raw_status:
                        normalized = self._normalize_telemetry(raw_status)
                        if self.on_telemetry_callback:
                            self.on_telemetry_callback(normalized)
            except Exception as e:
                logger.error(f"Error during REST telemetry poll: {e}")

            time.sleep(3.0)

    def _run_mqtt(self, mqtt):
        """Establish TLS MQTT connection and subscribe to device report topics."""
        client_id = f"OrcaSlicer_{self.printer_id}_{int(time.time())}"
        
        # Support both paho-mqtt v1 and v2 API
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id)
        except Exception:
            client = mqtt.Client(client_id)

        self.mqtt_client = client

        # Set username / token auth
        client.username_pw_set(username=self.cloud_client.token, password=self.cloud_client.token)

        # Configure SSL / TLS
        client.tls_set(cert_reqs=ssl.CERT_NONE)
        client.tls_insecure_set(True)

        def on_connect(c, userdata, flags, rc, properties=None):
            logger.info(f"Connected to Anycubic MQTT broker with rc={rc}")
            # Subscribe to printer reporting topics
            topics = [
                f"/device/{self.printer_id}/report",
                f"anycubic/cloud/device/{self.printer_id}/report",
                f"/farm/printer/{self.printer_id}/status",
                f"printer/{self.printer_id}/telemetry"
            ]
            for t in topics:
                c.subscribe(t)
                logger.info(f"Subscribed to {t}")

        def on_message(c, userdata, msg):
            try:
                payload = json.loads(msg.payload.decode("utf-8", errors="ignore"))
                normalized = self._normalize_telemetry(payload)
                if self.on_telemetry_callback:
                    self.on_telemetry_callback(normalized)
            except Exception as e:
                logger.error(f"Error handling MQTT message: {e}")

        client.on_connect = on_connect
        client.on_message = on_message

        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_start()

        while self.running:
            time.sleep(1.0)

        client.loop_stop()
        client.disconnect()

    def _normalize_telemetry(self, raw):
        """
        Convert Anycubic raw telemetry payload into standard OrcaSlicer / Bambu Device format.
        """
        telemetry = {}

        # 1. Hotend / Nozzle temperatures
        nozzle = raw.get("nozzle_temp") or raw.get("nozzle_temper") or raw.get("cur_temp") or 0.0
        nozzle_target = raw.get("nozzle_target_temp") or raw.get("target_temp") or 0.0
        telemetry["nozzle_temper"] = float(nozzle)
        telemetry["nozzle_target_temper"] = float(nozzle_target)

        # 2. Bed temperatures
        bed = raw.get("bed_temp") or raw.get("bed_temper") or 0.0
        bed_target = raw.get("bed_target_temp") or 0.0
        telemetry["bed_temper"] = float(bed)
        telemetry["bed_target_temper"] = float(bed_target)

        # 3. Print progress & status
        progress = raw.get("progress") or raw.get("mc_percent") or 0
        telemetry["mc_percent"] = int(progress)

        state = raw.get("status") or raw.get("gcode_state") or raw.get("state") or "IDLE"
        if isinstance(state, int):
            # Numeric status mappings
            state_map = {0: "IDLE", 1: "PREPARE", 2: "RUNNING", 3: "PAUSE", 4: "FINISH", 5: "FAILED"}
            state = state_map.get(state, "IDLE")
        telemetry["gcode_state"] = str(state).upper()

        # 4. Layer info
        telemetry["layer_num"] = int(raw.get("cur_layer") or raw.get("layer_num") or 0)
        telemetry["total_layer_num"] = int(raw.get("total_layer") or raw.get("total_layer_num") or 0)

        # 5. Remaining print time
        rem_seconds = raw.get("remain_time") or raw.get("mc_remaining_time") or 0
        telemetry["mc_remaining_time"] = int(rem_seconds) // 60 if rem_seconds > 500 else int(rem_seconds)

        # 6. Anycubic ACE Pro Multi-Color unit info
        if "ace_info" in raw or "ams" in raw:
            ace = raw.get("ace_info") or raw.get("ams") or {}
            telemetry["ams"] = ace

        return {
            "print": telemetry
        }
