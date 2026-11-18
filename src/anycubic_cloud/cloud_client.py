"""
Anycubic Cloud REST API Client.
Communicates with cloud-universe.anycubic.com to manage printers and print jobs.
"""

import os
import json
import time
import hmac
import hashlib
import logging
import urllib.request
import urllib.error
import ssl

logger = logging.getLogger("anycubic_cloud.api")

DEFAULT_BASE_URL = "https://cloud-universe.anycubic.com"
APP_SECRET = b"0cf75926606049a3937f56b0373b99fb"


class AnycubicCloudClient:
    def __init__(self, token=None, base_url=DEFAULT_BASE_URL):
        self.token = token
        self.base_url = base_url.rstrip("/")
        # Permissive SSL context for secure HTTPS requests
        self.ssl_ctx = ssl.create_default_context()

    def set_token(self, token):
        self.token = token

    def _generate_headers(self, path, body_bytes=b""):
        """Generate Anycubic Cloud request headers including XX-Token and signatures."""
        timestamp = str(int(time.time() * 1000))
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "XX-Device-Type": "pc",
            "XX-Version": "2.0.0",
            "XX-Timestamp": timestamp,
        }

        if self.token:
            headers["XX-Token"] = self.token
            headers["token"] = self.token
            headers["Authorization"] = f"Bearer {self.token}"

        # Calculate HMAC signature if secret is present
        try:
            sign_content = f"{timestamp}.{path}.".encode("utf-8") + body_bytes
            signature = hmac.new(APP_SECRET, sign_content, hashlib.sha256).hexdigest()
            headers["XX-Signature"] = signature
        except Exception:
            pass

        return headers

    def _request(self, method, endpoint, payload=None):
        """Execute an HTTP request to Anycubic Cloud API."""
        url = f"{self.base_url}{endpoint}"
        body_bytes = b""
        if payload is not None:
            if isinstance(payload, (dict, list)):
                body_bytes = json.dumps(payload).encode("utf-8")
            elif isinstance(payload, bytes):
                body_bytes = payload
            elif isinstance(payload, str):
                body_bytes = payload.encode("utf-8")

        headers = self._generate_headers(endpoint, body_bytes)
        req = urllib.request.Request(url, data=body_bytes if method.upper() in ["POST", "PUT"] else None, headers=headers, method=method.upper())

        try:
            with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=20) as resp:
                res_data = resp.read().decode("utf-8")
                try:
                    return json.loads(res_data)
                except Exception:
                    return {"code": 0, "raw": res_data}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            logger.error(f"HTTP {e.code} on {endpoint}: {err_body}")
            try:
                return json.loads(err_body)
            except Exception:
                return {"code": e.code, "error": err_body}
        except Exception as e:
            logger.error(f"Request failed on {endpoint}: {e}")
            return {"code": -1, "error": str(e)}

    def get_printers(self):
        """
        Fetch all user-associated printers from Anycubic Cloud.
        Returns a list of normalized printer info dictionaries.
        """
        # Try primary endpoints
        for ep in ["/v2/printer/info", "/work/printer/getPrinters", "/v2/printer/printersStatus"]:
            res = self._request("POST", ep, payload={})
            if res.get("code") == 0 or res.get("code") == 200:
                data = res.get("data")
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    # Check common container keys
                    for k in ["list", "printers", "items", "records"]:
                        if k in data and isinstance(data[k], list):
                            return data[k]
                    return [data]

        return []

    def get_printer_status(self, printer_id):
        """Fetch current status for a specific printer."""
        payload = {"printer_id": str(printer_id), "id": str(printer_id)}
        res = self._request("POST", "/v2/printer/printersStatus", payload=payload)
        if res.get("code") in [0, 200]:
            return res.get("data", {})
        return {}

    def get_multicolor_box_info(self, printer_id):
        """Fetch Anycubic Color Engine (ACE Pro) details."""
        payload = {"printer_id": str(printer_id)}
        res = self._request("POST", "/v2/printer/getMultiColorBoxInfo", payload=payload)
        if res.get("code") in [0, 200]:
            return res.get("data", {})
        return {}

    def upload_file(self, file_path, custom_name=None):
        """
        Upload a sliced .gcode or .gcode.3mf file to Anycubic Cloud.
        Returns upload info with file_id and cloud URL.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_name = custom_name or os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        with open(file_path, "rb") as f:
            file_data = f.read()

        file_md5 = hashlib.md5(file_data).hexdigest()

        # Step 1: Request upload token / slot
        init_payload = {
            "name": file_name,
            "filename": file_name,
            "size": file_size,
            "md5": file_md5,
            "type": "gcode.3mf" if file_name.endswith(".3mf") else "gcode"
        }

        res = self._request("POST", "/user/profile/newUploadFile", payload=init_payload)
        logger.info(f"Upload init response: {res}")

        upload_info = res.get("data", {})
        upload_url = upload_info.get("upload_url") or upload_info.get("url")

        if upload_url:
            # Upload directly to presigned storage URL
            req = urllib.request.Request(upload_url, data=file_data, headers={"Content-Type": "application/octet-stream"}, method="PUT")
            with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=120) as put_resp:
                logger.info(f"Binary upload completed with status: {put_resp.status}")

        return upload_info

    def start_print(self, printer_id, file_url_or_id, file_name="", bed_leveling=True, flow_cali=True, timelapse=True, ams_mapping=None):
        """
        Trigger a remote print on an Anycubic Cloud connected printer.
        """
        payload = {
            "printer_id": str(printer_id),
            "file_url": file_url_or_id,
            "file_name": file_name,
            "bed_leveling": 1 if bed_leveling else 0,
            "flow_cali": 1 if flow_cali else 0,
            "timelapse": 1 if timelapse else 0,
            "ams_mapping": ams_mapping or [0, 1, 2, 3]
        }
        res = self._request("POST", "/v3/printer/sendFile", payload=payload)
        logger.info(f"SendFile print trigger response: {res}")
        return res

    def control_printer(self, printer_id, command):
        """
        Send print control commands: 'pause', 'resume', 'stop'/'cancel'.
        """
        cmd_map = {
            "pause": 1,
            "resume": 2,
            "stop": 3,
            "cancel": 3
        }
        action_val = cmd_map.get(command.lower(), command)
        payload = {
            "printer_id": str(printer_id),
            "action": action_val,
            "command": command.lower()
        }
        res = self._request("POST", "/farm/printer/createBulkTask", payload=payload)
        return res
