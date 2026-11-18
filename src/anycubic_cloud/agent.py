"""
OrcaSlicer Printer Agent Implementation for Anycubic Cloud.
Subclasses orca.printer_agent.PrinterAgentBase to provide native device tab integration.
"""

import os
import json
import logging
import orca
from orca.printer_agent import PrinterAgentBase, AgentInfo

from .cloud_client import AnycubicCloudClient
from .mqtt_client import AnycubicTelemetryBridge
from .token_manager import get_token, save_token

logger = logging.getLogger("anycubic_cloud.agent")


class AnycubicPrinterAgent(PrinterAgentBase):
    def __init__(self):
        super().__init__()
        self.agent_id = "anycubic_cloud"
        self.agent_name = "Anycubic Cloud"
        self.token = get_token()
        self.cloud_client = AnycubicCloudClient(token=self.token)
        self.telemetry_bridge = AnycubicTelemetryBridge(self.cloud_client)
        self.selected_machine = ""
        self.connected = False

        # OrcaSlicer callback hooks
        self._on_message_fn = None
        self._on_printer_connected_fn = None
        self._on_user_message_fn = None
        self._queue_on_main_fn = None

    def get_name(self) -> str:
        return self.agent_name

    def get_agent_info(self) -> AgentInfo:
        info = AgentInfo()
        info.id = self.agent_id
        info.name = self.agent_name
        return info

    def set_user_selected_machine(self, machine: str) -> None:
        self.selected_machine = str(machine) if machine else ""
        self.telemetry_bridge.set_printer(self.selected_machine)
        logger.info(f"Selected machine set to: {self.selected_machine}")

    def get_user_selected_machine(self) -> str:
        return self.selected_machine

    def connect_printer(self, params) -> bool:
        """Called by OrcaSlicer when activating the physical printer profile."""
        logger.info(f"connect_printer called with params: {params}")
        self.token = get_token()

        # If not logged in, pop up the native Anycubic login dialog window!
        if not self.token:
            logger.info("No token found. Opening Anycubic Login Dialog...")
            try:
                import subprocess
                candidates = [
                    os.path.join(os.path.dirname(__file__), "login_dialog.ps1"),
                    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "tools", "login_dialog.ps1")
                ]
                for script in candidates:
                    if os.path.exists(script):
                        subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", script], timeout=180)
                        self.token = get_token()
                        break
            except Exception as e:
                logger.error(f"Error launching login dialog: {e}")

        if not self.token:
            logger.warning("No Anycubic Cloud token configured.")
            if self._on_user_message_fn:
                self._on_user_message_fn("Anycubic Cloud: Faca login com usuario e senha para conectar sua impressora.")
            return False

        self.cloud_client.set_token(self.token)
        
        # Connect telemetry bridge
        self.telemetry_bridge.set_callback(self._handle_telemetry_update)
        self.telemetry_bridge.start()

        self.connected = True
        if self._on_printer_connected_fn:
            self._on_printer_connected_fn(True)

        return True

    def disconnect_printer(self) -> None:
        """Called by OrcaSlicer when deactivating or closing the printer."""
        logger.info("disconnect_printer called")
        self.connected = False
        self.telemetry_bridge.stop()
        if self._on_printer_connected_fn:
            self._on_printer_connected_fn(False)

    def _handle_telemetry_update(self, payload_dict):
        """Forward telemetry data to OrcaSlicer's DeviceManager."""
        if self._on_message_fn:
            json_str = json.dumps(payload_dict)
            try:
                self._on_message_fn("device/report", json_str)
            except Exception as e:
                logger.error(f"Error invoking _on_message_fn: {e}")

    def start_discovery(self) -> None:
        """Query Anycubic Cloud for registered printers and register them."""
        logger.info("start_discovery called")
        if not self.token:
            self.token = get_token()
            self.cloud_client.set_token(self.token)

        if not self.token:
            return

        try:
            printers = self.cloud_client.get_printers()
            logger.info(f"Discovered Anycubic printers: {printers}")
            # If a machine was not set, select the first online printer
            if printers and not self.selected_machine:
                first_id = printers[0].get("id") or printers[0].get("printer_id")
                if first_id:
                    self.set_user_selected_machine(str(first_id))
        except Exception as e:
            logger.error(f"Discovery error: {e}")

    def start_send_gcode_to_sdcard(self, params, update_fn, cancel_fn, wait_fn) -> int:
        """
        Upload sliced .gcode or .gcode.3mf directly to Anycubic Cloud storage.
        """
        logger.info("start_send_gcode_to_sdcard invoked")
        # Handshake verification check
        project_name = getattr(params, "project_name", "") or getattr(params, "task_name", "")
        if project_name == "verify_job":
            return 0 if self.token else -1

        file_path = getattr(params, "ftp_file", "") or getattr(params, "config_filename", "") or ""
        if not file_path or not os.path.exists(file_path):
            logger.error(f"Invalid file path: {file_path}")
            return -1

        if update_fn:
            update_fn(20, "Uploading to Anycubic Cloud...")

        try:
            upload_res = self.cloud_client.upload_file(file_path)
            if update_fn:
                update_fn(100, "Upload completed successfully!")
            return 0
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            if update_fn:
                update_fn(0, f"Upload error: {e}")
            return -1

    def start_print(self, params, update_fn, cancel_fn, wait_fn) -> int:
        """
        Send print job to target Anycubic printer via Anycubic Cloud.
        """
        logger.info("start_print invoked")
        if update_fn:
            update_fn(10, "Preparing Anycubic Cloud print task...")

        file_path = getattr(params, "ftp_file", "") or getattr(params, "config_filename", "") or ""
        task_name = getattr(params, "task_name", "") or os.path.basename(file_path)
        bed_leveling = getattr(params, "task_bed_leveling", True)
        flow_cali = getattr(params, "task_flow_cali", True)
        timelapse = getattr(params, "task_record_timelapse", True)
        ams_mapping = getattr(params, "ams_mapping", None)

        try:
            if update_fn:
                update_fn(30, "Uploading model to Anycubic Cloud...")

            upload_res = self.cloud_client.upload_file(file_path, custom_name=task_name)
            file_url_or_id = upload_res.get("file_id") or upload_res.get("url") or task_name

            if update_fn:
                update_fn(70, "Sending print command to printer...")

            printer_target = self.selected_machine or "1"
            res = self.cloud_client.start_print(
                printer_id=printer_target,
                file_url_or_id=file_url_or_id,
                file_name=task_name,
                bed_leveling=bed_leveling,
                flow_cali=flow_cali,
                timelapse=timelapse,
                ams_mapping=ams_mapping
            )

            if update_fn:
                update_fn(100, "Print task dispatched successfully!")
            return 0
        except Exception as e:
            logger.error(f"Print job dispatch failed: {e}")
            if update_fn:
                update_fn(0, f"Print error: {e}")
            return -1

    # Control Commands
    def send_message(self, message: str) -> None:
        logger.info(f"send_message: {message}")
        try:
            data = json.loads(message)
            cmd = data.get("command") or data.get("action")
            if cmd and self.selected_machine:
                self.cloud_client.control_printer(self.selected_machine, cmd)
        except Exception as e:
            logger.error(f"Error in send_message: {e}")

    def send_message_to_printer(self, message: str) -> None:
        self.send_message(message)

    # Setters for OrcaSlicer host callbacks
    def set_on_message_fn(self, callback) -> None:
        self._on_message_fn = callback

    def set_on_printer_connected_fn(self, callback) -> None:
        self._on_printer_connected_fn = callback

    def set_on_user_message_fn(self, callback) -> None:
        self._on_user_message_fn = callback

    def set_queue_on_main_fn(self, callback) -> None:
        self._queue_on_main_fn = callback

    # Pure virtual interface stubs to prevent pybind11 errors
    def start_local_print(self, params, update_fn, cancel_fn, wait_fn) -> int:
        return self.start_print(params, update_fn, cancel_fn, wait_fn)

    def start_local_print_with_record(self, params, update_fn, cancel_fn, wait_fn) -> int:
        return self.start_print(params, update_fn, cancel_fn, wait_fn)

    def start_sdcard_print(self, params, update_fn) -> None:
        pass

    def ping_bind(self) -> bool:
        return True

    def bind(self, params) -> bool:
        return True

    def unbind(self) -> bool:
        return True

    def bind_detect(self) -> bool:
        return True

    def check_cert(self) -> bool:
        return True

    def set_server_callback(self, callback) -> None:
        pass

    def set_on_local_connect_fn(self, callback) -> None:
        pass

    def set_on_local_message_fn(self, callback) -> None:
        pass

    def set_on_ssdp_msg_fn(self, callback) -> None:
        pass

    def set_on_subscribe_failure_fn(self, callback) -> None:
        pass
