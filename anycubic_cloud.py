# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "paho-mqtt>=2.0.0",
#     "requests>=2.31.0",
# ]
# [tool.orcaslicer.plugin]
# name = "anycubic-cloud"
# version = "1.0.0"
# description = "Conexão nativa com a Anycubic Cloud para OrcaSlicer (Kobra 3, Kobra X, Kobra S1, Kobra 2 e Photon)"
# author = "Murilo & OrcaSlicer Community"
# ///

"""
Plugin Anycubic Cloud para OrcaSlicer.
Conecta diretamente nas impressoras Anycubic via nuvem, permitindo fatiamento,
monitoramento em tempo real (mesa, bico, ACE Pro) e disparo de impressões sem tirar a máquina da internet.
"""

import os
import sys
import json
import time
import hmac
import hashlib
import logging
import threading
import subprocess
import urllib.request
import urllib.error
import ssl

import orca
from orca.printer_agent import PrinterAgentBase, AgentInfo

logger = logging.getLogger("anycubic_cloud")
logger.setLevel(logging.INFO)

CONFIG_DIR = os.path.expandvars(r"%APPDATA%\OrcaSlicer\orca_plugins\anycubic_cloud")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
SLICER_NEXT_CONF = os.path.expandvars(r"%APPDATA%\AnycubicSlicerNext\AnycubicSlicerNext.conf")
DEFAULT_BASE_URL = "https://cloud-universe.anycubic.com"
APP_SECRET = b"0cf75926606049a3937f56b0373b99fb"
MQTT_BROKER = "mqtt-universe.anycubic.com"
MQTT_PORT = 8883


# ============================================================================
# 1. Gerenciador de Token e Credenciais
# ============================================================================

def get_token():
    """Recupera o token de acesso da Anycubic Cloud."""
    env_token = os.environ.get("ANYCUBIC_TOKEN")
    if env_token:
        return env_token.strip()

    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                tok = cfg.get("token") or cfg.get("access_token")
                if tok and isinstance(tok, str):
                    return tok.strip()
        except Exception as e:
            logger.warning(f"Erro ao ler config.json: {e}")

    if os.path.exists(SLICER_NEXT_CONF):
        try:
            with open(SLICER_NEXT_CONF, "r", encoding="utf-8") as f:
                data = json.load(f)
                cloud = data.get("anycubic_cloud", {})
                if isinstance(cloud, dict):
                    tok = cloud.get("access_token")
                    if tok and isinstance(tok, str) and not tok.endswith("=="):
                        return tok.strip()
        except Exception:
            pass

    return None


def save_token(token, user_id=None, device_id=None):
    """Salva o token e dados da conta no config.json."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}

    cfg["token"] = token.strip()
    if user_id:
        cfg["user_id"] = user_id
    if device_id:
        cfg["device_id"] = device_id
    cfg["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    logger.info("Token Anycubic Cloud salvo com sucesso!")


def open_login_dialog():
    """Abre uma janela nativa do Windows solicitando usuário e senha da Anycubic."""
    cfg_dir = CONFIG_DIR.replace('\\', '\\\\')
    cfg_path = CONFIG_PATH.replace('\\', '\\\\')
    ps_code = f"""
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing

    $form = New-Object System.Windows.Forms.Form
    $form.Text = "Login - Anycubic Cloud (OrcaSlicer)"
    $form.Size = New-Object System.Drawing.Size(460, 400)
    $form.StartPosition = "CenterScreen"
    $form.FormBorderStyle = "FixedDialog"
    $form.MaximizeBox = $false
    $form.MinimizeBox = $false
    $form.BackColor = [System.Drawing.Color]::FromArgb(35, 38, 43)
    $form.ForeColor = [System.Drawing.Color]::White

    $title = New-Object System.Windows.Forms.Label
    $title.Text = "Conectar na Anycubic Cloud"
    $title.Font = New-Object System.Drawing.Font("Segoe UI", 14, [System.Drawing.FontStyle]::Bold)
    $title.Location = New-Object System.Drawing.Point(30, 20)
    $title.Size = New-Object System.Drawing.Size(390, 32)
    $title.ForeColor = [System.Drawing.Color]::FromArgb(0, 168, 255)
    $form.Controls.Add($title)

    $sub = New-Object System.Windows.Forms.Label
    $sub.Text = "Digite seu login da Anycubic para conectar ao OrcaSlicer."
    $sub.Font = New-Object System.Drawing.Font("Segoe UI", 9)
    $sub.Location = New-Object System.Drawing.Point(30, 55)
    $sub.Size = New-Object System.Drawing.Size(390, 25)
    $sub.ForeColor = [System.Drawing.Color]::FromArgb(180, 185, 195)
    $form.Controls.Add($sub)

    $lblE = New-Object System.Windows.Forms.Label
    $lblE.Text = "E-mail ou Usuario Anycubic:"
    $lblE.Location = New-Object System.Drawing.Point(30, 95)
    $lblE.Size = New-Object System.Drawing.Size(390, 20)
    $form.Controls.Add($lblE)

    $txtE = New-Object System.Windows.Forms.TextBox
    $txtE.Location = New-Object System.Drawing.Point(30, 118)
    $txtE.Size = New-Object System.Drawing.Size(385, 28)
    $txtE.Font = New-Object System.Drawing.Font("Segoe UI", 10)
    $txtE.BackColor = [System.Drawing.Color]::FromArgb(48, 52, 60)
    $txtE.ForeColor = [System.Drawing.Color]::White
    $form.Controls.Add($txtE)

    $lblP = New-Object System.Windows.Forms.Label
    $lblP.Text = "Senha:"
    $lblP.Location = New-Object System.Drawing.Point(30, 160)
    $lblP.Size = New-Object System.Drawing.Size(390, 20)
    $form.Controls.Add($lblP)

    $txtP = New-Object System.Windows.Forms.TextBox
    $txtP.Location = New-Object System.Drawing.Point(30, 183)
    $txtP.Size = New-Object System.Drawing.Size(385, 28)
    $txtP.Font = New-Object System.Drawing.Font("Segoe UI", 10)
    $txtP.BackColor = [System.Drawing.Color]::FromArgb(48, 52, 60)
    $txtP.ForeColor = [System.Drawing.Color]::White
    $txtP.PasswordChar = '*'
    $form.Controls.Add($txtP)

    $lblSt = New-Object System.Windows.Forms.Label
    $lblSt.Text = ""
    $lblSt.Location = New-Object System.Drawing.Point(30, 222)
    $lblSt.Size = New-Object System.Drawing.Size(385, 30)
    $form.Controls.Add($lblSt)

    $btn = New-Object System.Windows.Forms.Button
    $btn.Text = "Entrar na Conta Anycubic"
    $btn.Location = New-Object System.Drawing.Point(30, 260)
    $btn.Size = New-Object System.Drawing.Size(385, 38)
    $btn.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
    $btn.BackColor = [System.Drawing.Color]::FromArgb(0, 122, 255)
    $btn.ForeColor = [System.Drawing.Color]::White
    $btn.FlatStyle = "Flat"
    $form.Controls.Add($btn)

    $btn.Add_Click({{
        $acc = $txtE.Text.Trim()
        $pwd = $txtP.Text.Trim()
        if ([string]::IsNullOrWhiteSpace($acc) -or [string]::IsNullOrWhiteSpace($pwd)) {{
            $lblSt.ForeColor = [System.Drawing.Color]::Tomato
            $lblSt.Text = "Preencha o e-mail e a senha."
            return
        }}

        $lblSt.ForeColor = [System.Drawing.Color]::Yellow
        $lblSt.Text = "Autenticando..."
        $btn.Enabled = $false
        $form.Update()

        try {{
            $b = @{{ account = $acc; password = $pwd; login_type = 1 }} | ConvertTo-Json
            $h = @{{ "Content-Type" = "application/json"; "XX-Device-Type" = "pc"; "XX-Version" = "2.0.0" }}
            $r = Invoke-RestMethod -Uri "https://cloud-universe.anycubic.com/user/public/login" -Method Post -Body $b -Headers $h -TimeoutSec 15
            if ($r.code -eq 0 -or $r.code -eq 200) {{
                $t = $r.data.access_token
                if (-not $t) {{ $t = $r.data.token }}
                if ($t) {{
                    $dir = "{cfg_dir}"
                    if (-not (Test-Path $dir)) {{ New-Item -ItemType Directory -Force -Path $dir | Out-Null }}
                    @{{ token = $t; user_id = $r.data.user_id }} | ConvertTo-Json | Set-Content -Path "{cfg_path}" -Encoding UTF8
                    $lblSt.ForeColor = [System.Drawing.Color]::LightGreen
                    $lblSt.Text = "Login efetuado com sucesso!"
                    $form.Update()
                    Start-Sleep -Seconds 1
                    $form.Close()
                    return
                }}
            }}
            $lblSt.ForeColor = [System.Drawing.Color]::Tomato
            $lblSt.Text = "Falha no login: $($r.msg)"
        }} catch {{
            $lblSt.ForeColor = [System.Drawing.Color]::Tomato
            $lblSt.Text = "Erro: $($_.Exception.Message)"
        }} finally {{
            $btn.Enabled = $true
        }}
    }})

    [void]$form.ShowDialog()
    """
    try:
        subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_code], timeout=180)
    except Exception as e:
        logger.error(f"Erro ao abrir janela de login: {e}")


# ============================================================================
# 2. Cliente REST Anycubic Cloud
# ============================================================================

class AnycubicCloudClient:
    def __init__(self, token=None, base_url=DEFAULT_BASE_URL):
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.ssl_ctx = ssl.create_default_context()

    def set_token(self, token):
        self.token = token

    def _generate_headers(self, path, body_bytes=b""):
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

        try:
            sign_content = f"{timestamp}.{path}.".encode("utf-8") + body_bytes
            headers["XX-Signature"] = hmac.new(APP_SECRET, sign_content, hashlib.sha256).hexdigest()
        except Exception:
            pass
        return headers

    def _request(self, method, endpoint, payload=None):
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
            logger.error(f"HTTP {e.code} em {endpoint}: {err_body}")
            try:
                return json.loads(err_body)
            except Exception:
                return {"code": e.code, "error": err_body}
        except Exception as e:
            logger.error(f"Falha na requisicao {endpoint}: {e}")
            return {"code": -1, "error": str(e)}

    def get_printers(self):
        """Busca impressoras cadastradas na Anycubic Cloud."""
        for ep in ["/v2/printer/info", "/work/printer/getPrinters", "/v2/printer/printersStatus"]:
            res = self._request("POST", ep, payload={})
            if res.get("code") in [0, 200]:
                data = res.get("data")
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    for k in ["list", "printers", "items", "records"]:
                        if k in data and isinstance(data[k], list):
                            return data[k]
                    return [data]
        return []

    def get_printer_status(self, printer_id):
        payload = {"printer_id": str(printer_id), "id": str(printer_id)}
        res = self._request("POST", "/v2/printer/printersStatus", payload=payload)
        return res.get("data", {}) if res.get("code") in [0, 200] else {}

    def upload_file(self, file_path, custom_name=None):
        """Upload de arquivo .gcode ou .gcode.3mf para a Anycubic Cloud."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Arquivo nao encontrado: {file_path}")

        file_name = custom_name or os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        with open(file_path, "rb") as f:
            file_data = f.read()

        file_md5 = hashlib.md5(file_data).hexdigest()

        init_payload = {
            "name": file_name,
            "filename": file_name,
            "size": file_size,
            "md5": file_md5,
            "type": "gcode.3mf" if file_name.endswith(".3mf") else "gcode"
        }

        res = self._request("POST", "/user/profile/newUploadFile", payload=init_payload)
        upload_info = res.get("data", {})
        upload_url = upload_info.get("upload_url") or upload_info.get("url")

        if upload_url:
            req = urllib.request.Request(upload_url, data=file_data, headers={"Content-Type": "application/octet-stream"}, method="PUT")
            with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=120):
                logger.info("Upload de arquivo binario concluido com sucesso!")

        return upload_info

    def start_print(self, printer_id, file_url_or_id, file_name="", bed_leveling=True, flow_cali=True, timelapse=True, ams_mapping=None):
        payload = {
            "printer_id": str(printer_id),
            "file_url": file_url_or_id,
            "file_name": file_name,
            "bed_leveling": 1 if bed_leveling else 0,
            "flow_cali": 1 if flow_cali else 0,
            "timelapse": 1 if timelapse else 0,
            "ams_mapping": ams_mapping or [0, 1, 2, 3]
        }
        return self._request("POST", "/v3/printer/sendFile", payload=payload)

    def control_printer(self, printer_id, command):
        cmd_map = {"pause": 1, "resume": 2, "stop": 3, "cancel": 3}
        payload = {"printer_id": str(printer_id), "action": cmd_map.get(command.lower(), command), "command": command.lower()}
        return self._request("POST", "/farm/printer/createBulkTask", payload=payload)


# ============================================================================
# 3. Telemetria e MQTTS Bridge
# ============================================================================

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
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.mqtt_client:
            try:
                self.mqtt_client.disconnect()
            except Exception:
                pass
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)

    def _run_loop(self):
        has_paho = False
        try:
            import paho.mqtt.client as mqtt
            has_paho = True
        except ImportError:
            pass

        if has_paho and self.cloud_client.token and self.printer_id:
            try:
                self._run_mqtt(mqtt)
                return
            except Exception as e:
                logger.warning(f"Conexao MQTT falhou ({e}); utilizando polling REST.")

        # Polling REST de contingência a cada 3 segundos
        while self.running:
            try:
                if self.printer_id:
                    raw = self.cloud_client.get_printer_status(self.printer_id)
                    if raw and self.on_telemetry_callback:
                        self.on_telemetry_callback(self._normalize_telemetry(raw))
            except Exception as e:
                logger.error(f"Erro polling telemetria: {e}")
            time.sleep(3.0)

    def _run_mqtt(self, mqtt):
        client_id = f"OrcaSlicer_{self.printer_id}_{int(time.time())}"
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id)
        except Exception:
            client = mqtt.Client(client_id)

        self.mqtt_client = client
        client.username_pw_set(username=self.cloud_client.token, password=self.cloud_client.token)
        client.tls_set(cert_reqs=ssl.CERT_NONE)
        client.tls_insecure_set(True)

        def on_connect(c, userdata, flags, rc, properties=None):
            topics = [
                f"/device/{self.printer_id}/report",
                f"anycubic/cloud/device/{self.printer_id}/report",
                f"/farm/printer/{self.printer_id}/status"
            ]
            for t in topics:
                c.subscribe(t)

        def on_message(c, userdata, msg):
            try:
                payload = json.loads(msg.payload.decode("utf-8", errors="ignore"))
                if self.on_telemetry_callback:
                    self.on_telemetry_callback(self._normalize_telemetry(payload))
            except Exception:
                pass

        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_start()

        while self.running:
            time.sleep(1.0)

        client.loop_stop()
        client.disconnect()

    def _normalize_telemetry(self, raw):
        telemetry = {
            "nozzle_temper": float(raw.get("nozzle_temp") or raw.get("nozzle_temper") or raw.get("cur_temp") or 0.0),
            "nozzle_target_temper": float(raw.get("nozzle_target_temp") or raw.get("target_temp") or 0.0),
            "bed_temper": float(raw.get("bed_temp") or raw.get("bed_temper") or 0.0),
            "bed_target_temper": float(raw.get("bed_target_temp") or 0.0),
            "mc_percent": int(raw.get("progress") or raw.get("mc_percent") or 0),
            "layer_num": int(raw.get("cur_layer") or raw.get("layer_num") or 0),
            "total_layer_num": int(raw.get("total_layer") or raw.get("total_layer_num") or 0)
        }
        state = raw.get("status") or raw.get("gcode_state") or raw.get("state") or "IDLE"
        if isinstance(state, int):
            state_map = {0: "IDLE", 1: "PREPARE", 2: "RUNNING", 3: "PAUSE", 4: "FINISH", 5: "FAILED"}
            state = state_map.get(state, "IDLE")
        telemetry["gcode_state"] = str(state).upper()

        rem = raw.get("remain_time") or raw.get("mc_remaining_time") or 0
        telemetry["mc_remaining_time"] = int(rem) // 60 if rem > 500 else int(rem)

        if "ace_info" in raw or "ams" in raw:
            telemetry["ams"] = raw.get("ace_info") or raw.get("ams")

        return {"print": telemetry}


# ============================================================================
# 4. Implementação de PrinterAgentBase (OrcaSlicer Device Tab)
# ============================================================================

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

    def get_user_selected_machine(self) -> str:
        return self.selected_machine

    def connect_printer(self, params) -> bool:
        self.token = get_token()
        if not self.token:
            # Se nao tiver logado, abre a janela grafica com usuario e senha
            open_login_dialog()
            self.token = get_token()

        if not self.token:
            return False

        self.cloud_client.set_token(self.token)
        self.telemetry_bridge.set_callback(self._handle_telemetry_update)
        self.telemetry_bridge.start()
        self.connected = True

        if self._on_printer_connected_fn:
            self._on_printer_connected_fn(True)
        return True

    def disconnect_printer(self) -> None:
        self.connected = False
        self.telemetry_bridge.stop()
        if self._on_printer_connected_fn:
            self._on_printer_connected_fn(False)

    def _handle_telemetry_update(self, payload_dict):
        if self._on_message_fn:
            try:
                self._on_message_fn("device/report", json.dumps(payload_dict))
            except Exception:
                pass

    def start_discovery(self) -> None:
        if not self.token:
            self.token = get_token()
            self.cloud_client.set_token(self.token)

        if not self.token:
            return

        try:
            printers = self.cloud_client.get_printers()
            if printers and not self.selected_machine:
                first_id = printers[0].get("id") or printers[0].get("printer_id")
                if first_id:
                    self.set_user_selected_machine(str(first_id))
        except Exception:
            pass

    def start_send_gcode_to_sdcard(self, params, update_fn, cancel_fn, wait_fn) -> int:
        project_name = getattr(params, "project_name", "") or getattr(params, "task_name", "")
        if project_name == "verify_job":
            return 0 if self.token else -1

        file_path = getattr(params, "ftp_file", "") or getattr(params, "config_filename", "") or ""
        if not file_path or not os.path.exists(file_path):
            return -1

        if update_fn:
            update_fn(20, "Enviando arquivo para a Anycubic Cloud...")

        try:
            self.cloud_client.upload_file(file_path)
            if update_fn:
                update_fn(100, "Envio concluido com sucesso!")
            return 0
        except Exception as e:
            if update_fn:
                update_fn(0, f"Erro no envio: {e}")
            return -1

    def start_print(self, params, update_fn, cancel_fn, wait_fn) -> int:
        file_path = getattr(params, "ftp_file", "") or getattr(params, "config_filename", "") or ""
        task_name = getattr(params, "task_name", "") or os.path.basename(file_path)
        bed_leveling = getattr(params, "task_bed_leveling", True)
        flow_cali = getattr(params, "task_flow_cali", True)
        timelapse = getattr(params, "task_record_timelapse", True)
        ams_mapping = getattr(params, "ams_mapping", None)

        if update_fn:
            update_fn(20, "Enviando fatiamento para a nuvem...")

        try:
            upload_res = self.cloud_client.upload_file(file_path, custom_name=task_name)
            file_url_or_id = upload_res.get("file_id") or upload_res.get("url") or task_name

            if update_fn:
                update_fn(70, "Disparando impressao na maquina...")

            self.cloud_client.start_print(
                printer_id=self.selected_machine or "1",
                file_url_or_id=file_url_or_id,
                file_name=task_name,
                bed_leveling=bed_leveling,
                flow_cali=flow_cali,
                timelapse=timelapse,
                ams_mapping=ams_mapping
            )

            if update_fn:
                update_fn(100, "Impressao iniciada com sucesso!")
            return 0
        except Exception as e:
            if update_fn:
                update_fn(0, f"Erro: {e}")
            return -1

    def send_message(self, message: str) -> None:
        try:
            data = json.loads(message)
            cmd = data.get("command") or data.get("action")
            if cmd and self.selected_machine:
                self.cloud_client.control_printer(self.selected_machine, cmd)
        except Exception:
            pass

    def send_message_to_printer(self, message: str) -> None:
        self.send_message(message)

    def set_on_message_fn(self, callback) -> None:
        self._on_message_fn = callback

    def set_on_printer_connected_fn(self, callback) -> None:
        self._on_printer_connected_fn = callback

    def set_on_user_message_fn(self, callback) -> None:
        self._on_user_message_fn = callback

    def set_queue_on_main_fn(self, callback) -> None:
        self._queue_on_main_fn = callback

    # Stubs pybind11
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


# ============================================================================
# 5. Pacote do Plugin OrcaSlicer
# ============================================================================

@orca.plugin
class AnycubicCloudPlugin(orca.PythonPluginBase):
    def register_capabilities(self):
        orca.register_capability(AnycubicPrinterAgent)
        try:
            orca.request_permissions(
                network=["mqtt-universe.anycubic.com", "cloud-universe.anycubic.com", "api.anycubic.com"]
            )
        except Exception:
            pass

    def has_config_ui(self) -> bool:
        return True

    def get_config_ui(self) -> str:
        tok = get_token() or ""
        logged = bool(tok)
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Anycubic Cloud</title>
    <style>
        body {{ font-family: Segoe UI, sans-serif; background: #23262b; color: #fff; padding: 20px; }}
        .card {{ background: #2e323b; border-radius: 8px; padding: 20px; max-width: 420px; margin: auto; }}
        h2 {{ color: #00a8ff; margin-top: 0; }}
        input {{ width: 100%; padding: 8px; margin: 6px 0 14px; background: #3c424e; border: 1px solid #555; color: #fff; border-radius: 4px; box-sizing: border-box; }}
        button {{ width: 100%; padding: 10px; background: #007aff; border: none; color: #fff; border-radius: 4px; font-weight: bold; cursor: pointer; }}
        button:hover {{ background: #0062cc; }}
        .status {{ margin-top: 10px; padding: 8px; border-radius: 4px; font-size: 13px; text-align: center; }}
        .ok {{ background: rgba(46,204,113,0.2); color: #2ecc71; }}
    </style>
</head>
<body>
    <div class="card">
        <h2>Anycubic Cloud</h2>
        <div class="status {'ok' if logged else ''}">
            {'✓ Conectado a conta Anycubic' if logged else 'Nenhuma conta conectada'}
        </div>
        <form onsubmit="doLogin(event)">
            <label>E-mail ou Usuario:</label>
            <input type="text" id="acc" required placeholder="seu_email@provedor.com">
            <label>Senha:</label>
            <input type="password" id="pwd" required placeholder="••••••••">
            <button type="submit" id="b">Conectar</button>
        </form>
    </div>
    <script>
        async function doLogin(e) {{
            e.preventDefault();
            const b = document.getElementById('b');
            b.innerText = 'Autenticando...';
            b.disabled = true;
            try {{
                const r = await fetch('https://cloud-universe.anycubic.com/user/public/login', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json', 'XX-Device-Type': 'pc', 'XX-Version': '2.0.0' }},
                    body: JSON.stringify({{ account: document.getElementById('acc').value, password: document.getElementById('pwd').value, login_type: 1 }})
                }});
                const d = await r.json();
                if (d.code === 0 || d.code === 200) {{
                    const t = d.data.access_token || d.data.token;
                    if (window.orca && window.orca.saveConfig) {{
                        window.orca.saveConfig(JSON.stringify({{ token: t, user_id: d.data.user_id }}));
                    }}
                    alert('Login efetuado com sucesso!');
                    location.reload();
                }} else {{
                    alert('Erro: ' + (d.msg || 'Credenciais invalidas'));
                }}
            }} catch(err) {{
                alert('Erro de conexao: ' + err.message);
            }} finally {{
                b.innerText = 'Conectar';
                b.disabled = false;
            }}
        }}
    </script>
</body>
</html>"""
