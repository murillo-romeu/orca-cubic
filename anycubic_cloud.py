# /// script
# requires-python = ">=3.12"
# dependencies = []
# [tool.orcaslicer.plugin]
# name = "anycubic-cloud"
# version = "1.0.0"
# description = "Conexao nativa com a Anycubic Cloud para OrcaSlicer (Kobra 3, Kobra X, Kobra S1, Kobra 2 e Photon)"
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
import urllib.request
import urllib.error
import ssl

try:
    import orca
    import orca.pages
    import orca.printer_agent
    PagesPluginCapabilityBase = orca.pages.PagesPluginCapabilityBase
    PrinterAgentBase = orca.printer_agent.PrinterAgentBase
    PluginBase = orca.base
except ImportError:
    class _MockBase:
        def __init__(self, *args, **kwargs):
            pass
    PagesPluginCapabilityBase = _MockBase
    PrinterAgentBase = _MockBase
    PluginBase = _MockBase

    class _MockOrca:
        base = _MockBase
        @staticmethod
        def plugin(cls):
            return cls
        @staticmethod
        def register_capability(cls):
            pass
        @staticmethod
        def request_permissions(**kwargs):
            pass
    orca = _MockOrca()

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
            logger.warning("Erro ao ler config.json: %s", e)

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


def get_account_email():
    """Recupera o email da conta salvo localmente."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return cfg.get("account") or cfg.get("email") or ""
        except Exception:
            pass
    return ""


def save_token(token, user_id=None, device_id=None, account=None):
    """Salva o token e dados da conta no config.json."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}

    if token:
        cfg["token"] = token.strip()
    else:
        cfg.pop("token", None)

    if user_id is not None:
        cfg["user_id"] = user_id
    if device_id is not None:
        cfg["device_id"] = device_id
    if account is not None:
        cfg["account"] = account
    cfg["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        logger.info("Configuração salva com sucesso em %s", CONFIG_PATH)
    except Exception as e:
        logger.error("Erro ao salvar config.json: %s", e)


# ============================================================================
# 2. Cliente REST Anycubic Cloud
# ============================================================================

class AnycubicCloudClient:
    """Cliente para a API REST da Anycubic Cloud."""

    def __init__(self, token=None, base_url=DEFAULT_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.token = token or get_token()
        self._ctx = ssl.create_default_context()
        self._ctx.check_hostname = False
        self._ctx.verify_mode = ssl.CERT_NONE

    def set_token(self, token):
        self.token = token.strip() if token else None

    def _sign_headers(self, path: str, body: bytes) -> dict:
        ts = str(int(time.time() * 1000))
        msg = f"{path}{ts}".encode("utf-8") + body
        sig = hmac.new(APP_SECRET, msg, hashlib.sha256).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "XX-Timestamp": ts,
            "XX-Signature": sig,
            "XX-Device-Type": "pc",
            "XX-App-Type": "OrcaSlicer",
            "XX-Version": "2.5.1",
        }
        if self.token:
            headers["XX-Token"] = self.token
        return headers

    def _request(self, method: str, path: str, payload: dict = None) -> dict:
        url = f"{self.base_url}{path}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else b""
        headers = self._sign_headers(path, body)

        req = urllib.request.Request(url, data=body if method in ("POST", "PUT") else None, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=12, context=self._ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                code = data.get("code")
                if code not in (0, 200):
                    raise RuntimeError(data.get("msg") or f"Erro API Anycubic: code {code}")
                return data.get("data", {})
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"HTTP {e.code}: {err_body}")

    def login(self, account: str, password: str) -> dict:
        """Autentica na nuvem Anycubic usando e-mail/usuário e senha."""
        payload = {"account": account, "password": password, "login_type": 1}
        data = self._request("POST", "/user/public/login", payload)
        tok = data.get("token") or data.get("access_token")
        if tok:
            self.token = tok
        return data

    def get_printers(self) -> list:
        """Lista todas as impressoras vinculadas à conta do usuário."""
        if not self.token:
            return []
        data = self._request("GET", "/v2/printer/info")
        if isinstance(data, list):
            return data
        return data.get("list", []) if isinstance(data, dict) else []

    def get_printers_status(self) -> list:
        """Consulta o status em tempo real de todas as impressoras vinculadas."""
        if not self.token:
            return []
        data = self._request("GET", "/v2/printer/printersStatus")
        if isinstance(data, list):
            return data
        return data.get("list", []) if isinstance(data, dict) else []


# ============================================================================
# 3. Telemetria e Monitoramento (MQTT com Fallback REST)
# ============================================================================

class AnycubicTelemetryBridge:
    def __init__(self, device_id: str, client: AnycubicCloudClient, on_telemetry_fn=None):
        self.device_id = device_id
        self.client = client
        self.on_telemetry_fn = on_telemetry_fn
        self._running = False
        self._poll_thread = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True, name="AnycubicPoll")
        self._poll_thread.start()

    def stop(self):
        self._running = False

    def _poll_loop(self):
        while self._running:
            try:
                statuses = self.client.get_printers_status()
                for p in statuses:
                    dev_id = str(p.get("device_id") or p.get("id") or "")
                    if dev_id == self.device_id or not self.device_id:
                        self._dispatch_status(p)
                        break
            except Exception as e:
                logger.debug("Erro no polling de telemetria: %s", e)
            time.sleep(3.0)

    def _dispatch_status(self, raw_status: dict):
        if not self.on_telemetry_fn:
            return
        msg = {
            "print": {
                "gcode_state": "RUNNING" if raw_status.get("status") == 2 else "IDLE",
                "mc_percent": raw_status.get("progress", 0),
                "nozzle_temper": raw_status.get("nozzle_temp", 0.0),
                "nozzle_target_temper": raw_status.get("nozzle_target_temp", 0.0),
                "bed_temper": raw_status.get("bed_temp", 0.0),
                "bed_target_temper": raw_status.get("bed_target_temp", 0.0),
            }
        }
        try:
            self.on_telemetry_fn(json.dumps(msg))
        except Exception:
            pass


# ============================================================================
# 4. Interface Gráfica Embutida (Aba Nativa no OrcaSlicer)
# ============================================================================

def get_cloud_ui_html() -> str:
    """Retorna o documento HTML completo com o design dark mode do OrcaSlicer."""
    return '<!DOCTYPE html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>Anycubic Cloud</title>\n<style>\n  :root {\n    --bg-main: #181a1f;\n    --bg-card: #21252b;\n    --bg-input: #282c34;\n    --border-color: #3e4451;\n    --primary: #00b894;\n    --primary-hover: #00a884;\n    --primary-glow: rgba(0, 184, 148, 0.25);\n    --accent: #0984e3;\n    --text-main: #abb2bf;\n    --text-bright: #ffffff;\n    --text-muted: #5c6370;\n    --danger: #ff4757;\n    --danger-bg: rgba(255, 71, 87, 0.15);\n    --success: #2ed573;\n    --success-bg: rgba(46, 213, 115, 0.15);\n  }\n  * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }\n  body { background: var(--bg-main); color: var(--text-main); padding: 24px; min-height: 100vh; }\n  .container { max-width: 680px; margin: 0 auto; }\n  \n  .header { display: flex; align-items: center; justify-content: space-between; padding-bottom: 20px; border-bottom: 1px solid var(--border-color); margin-bottom: 24px; }\n  .brand { display: flex; align-items: center; gap: 12px; }\n  .brand svg { width: 32px; height: 32px; fill: var(--primary); }\n  .brand-title { font-size: 20px; font-weight: 600; color: var(--text-bright); }\n  .brand-badge { background: rgba(0, 184, 148, 0.15); color: var(--primary); font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 12px; text-transform: uppercase; }\n  \n  .card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 10px; padding: 24px; margin-bottom: 20px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15); }\n  \n  .form-group { margin-bottom: 18px; }\n  .form-group label { display: block; font-size: 13px; font-weight: 500; color: var(--text-bright); margin-bottom: 8px; }\n  .input-wrapper { position: relative; display: flex; align-items: center; }\n  .input-wrapper input { width: 100%; background: var(--bg-input); border: 1px solid var(--border-color); border-radius: 6px; padding: 11px 14px; font-size: 14px; color: var(--text-bright); outline: none; transition: border-color 0.2s, box-shadow 0.2s; }\n  .input-wrapper input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-glow); }\n  .input-wrapper input::placeholder { color: var(--text-muted); }\n  .toggle-pwd { position: absolute; right: 12px; cursor: pointer; color: var(--text-muted); background: none; border: none; font-size: 14px; padding: 4px; }\n  .toggle-pwd:hover { color: var(--text-bright); }\n  \n  .btn { display: inline-flex; align-items: center; justify-content: center; gap: 8px; font-size: 14px; font-weight: 600; padding: 12px 20px; border-radius: 6px; border: none; cursor: pointer; transition: all 0.2s; text-decoration: none; }\n  .btn-primary { background: var(--primary); color: #fff; width: 100%; }\n  .btn-primary:hover:not(:disabled) { background: var(--primary-hover); transform: translateY(-1px); }\n  .btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }\n  .btn-secondary { background: var(--bg-input); border: 1px solid var(--border-color); color: var(--text-main); }\n  .btn-secondary:hover { background: #323842; color: var(--text-bright); }\n  .btn-danger { background: transparent; border: 1px solid var(--danger); color: var(--danger); }\n  .btn-danger:hover { background: var(--danger-bg); }\n  \n  .alert { padding: 12px 16px; border-radius: 6px; font-size: 13px; margin-bottom: 18px; display: none; }\n  .alert-danger { background: var(--danger-bg); border: 1px solid var(--danger); color: #ff6b81; }\n  .alert-success { background: var(--success-bg); border: 1px solid var(--success); color: #2ed573; }\n  .alert-info { background: rgba(9, 132, 227, 0.15); border: 1px solid var(--accent); color: #70a1ff; }\n  \n  .printer-list { display: flex; flex-direction: column; gap: 14px; }\n  .printer-card { background: var(--bg-input); border: 1px solid var(--border-color); border-radius: 8px; padding: 16px; display: flex; justify-content: space-between; align-items: center; }\n  .printer-info { display: flex; align-items: center; gap: 14px; }\n  .printer-icon { width: 44px; height: 44px; border-radius: 8px; background: rgba(0, 184, 148, 0.1); display: flex; align-items: center; justify-content: center; }\n  .printer-icon svg { width: 24px; height: 24px; fill: var(--primary); }\n  .printer-name { font-size: 15px; font-weight: 600; color: var(--text-bright); }\n  .printer-sub { font-size: 12px; color: var(--text-muted); margin-top: 3px; }\n  .printer-telemetry { display: flex; gap: 16px; font-size: 13px; text-align: right; }\n  .telemetry-item { display: flex; flex-direction: column; }\n  .telemetry-val { font-weight: 600; color: var(--text-bright); }\n  .telemetry-lbl { font-size: 11px; color: var(--text-muted); }\n  \n  .status-badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }\n  .status-online { background: var(--success-bg); color: var(--success); }\n  .status-printing { background: rgba(9, 132, 227, 0.2); color: #70a1ff; }\n  .status-offline { background: rgba(92, 99, 112, 0.2); color: var(--text-muted); }\n  \n  .hidden { display: none !important; }\n  .spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3); border-radius: 50%; border-top-color: #fff; animation: spin 0.8s linear infinite; }\n  @keyframes spin { to { transform: rotate(360deg); } }\n</style>\n</head>\n<body>\n<div class="container">\n  <div class="header">\n    <div class="brand">\n      <svg viewBox="0 0 24 24"><path d="M19 8h-1V3H6v5H5c-1.66 0-3 1.34-3 3v6h4v4h12v-4h4v-6c0-1.66-1.34-3-3-3zM8 5h8v3H8V5zm8 14H8v-4h8v4zm2-4v-2H6v2H4v-4c0-.55.45-1 1-1h14c.55 0 1 .45 1 1v4h-2z"/><circle cx="18" cy="11.5" r="1"/></svg>\n      <div>\n        <div class="brand-title">Anycubic Cloud</div>\n        <div style="font-size: 12px; color: var(--text-muted);">Integração nativa para OrcaSlicer</div>\n      </div>\n    </div>\n    <span class="brand-badge">OFICIAL V1.0</span>\n  </div>\n\n  <div id="alertBox" class="alert"></div>\n\n  <!-- Estado 1: Login Form (quando deslogado) -->\n  <div id="loginSection" class="card">\n    <h3 style="color: var(--text-bright); margin-bottom: 8px;">Conectar Conta Anycubic</h3>\n    <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 20px;">\n      Entre com seu e-mail e senha cadastrados no aplicativo móvel da Anycubic para conectar suas impressoras diretamente ao OrcaSlicer via nuvem.\n    </p>\n\n    <form id="loginForm" onsubmit="handleLogin(event)">\n      <div class="form-group">\n        <label for="inputAccount">E-mail ou Usuário Anycubic</label>\n        <div class="input-wrapper">\n          <input type="email" id="inputAccount" required placeholder="seu_email@provedor.com" autocomplete="username">\n        </div>\n      </div>\n\n      <div class="form-group">\n        <label for="inputPassword">Senha</label>\n        <div class="input-wrapper">\n          <input type="password" id="inputPassword" required placeholder="••••••••" autocomplete="current-password">\n          <button type="button" class="toggle-pwd" onclick="togglePasswordVisibility()">👁️</button>\n        </div>\n      </div>\n\n      <button type="submit" id="btnLogin" class="btn btn-primary">\n        <span id="btnLoginText">Conectar à Anycubic Cloud</span>\n        <span id="btnSpinner" class="spinner hidden"></span>\n      </button>\n    </form>\n  </div>\n\n  <!-- Estado 2: Painel de Impressoras (quando logado) -->\n  <div id="dashboardSection" class="card hidden">\n    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px;">\n      <div>\n        <div style="font-size: 12px; color: var(--text-muted);">CONECTADO COMO</div>\n        <div id="userEmail" style="font-size: 15px; font-weight: 600; color: var(--text-bright);">--</div>\n      </div>\n      <div style="display: flex; gap: 8px;">\n        <button type="button" class="btn btn-secondary" onclick="requestStatus()" style="padding: 8px 14px; font-size: 12px;">🔄 Atualizar</button>\n        <button type="button" class="btn btn-danger" onclick="handleLogout()" style="padding: 8px 14px; font-size: 12px;">Desconectar</button>\n      </div>\n    </div>\n\n    <h4 style="color: var(--text-bright); margin-bottom: 12px; font-size: 14px;">Impressoras Vinculadas</h4>\n    <div id="printersList" class="printer-list"></div>\n  </div>\n\n  <div class="card" style="background: rgba(9, 132, 227, 0.05); border-color: rgba(9, 132, 227, 0.2);">\n    <div style="font-size: 13px; color: var(--text-bright); font-weight: 600; margin-bottom: 4px;">💡 Como usar no OrcaSlicer:</div>\n    <div style="font-size: 12px; color: var(--text-muted); line-height: 1.5;">\n      1. Suas impressoras conectadas aparecerão automaticamente na aba <b>Dispositivo</b> do OrcaSlicer com telemetria em tempo real.<br>\n      2. Na aba <b>Preparar</b>, fatie qualquer peça e clique em <b>Imprimir</b> para enviar diretamente pela nuvem da Anycubic, mantendo sua impressora sempre online no app do celular!\n    </div>\n  </div>\n</div>\n\n<script>\n  function showAlert(msg, type) {\n    const el = document.getElementById(\'alertBox\');\n    el.className = \'alert alert-\' + type;\n    el.textContent = msg;\n    el.style.display = \'block\';\n  }\n  function hideAlert() {\n    document.getElementById(\'alertBox\').style.display = \'none\';\n  }\n\n  function togglePasswordVisibility() {\n    const input = document.getElementById(\'inputPassword\');\n    input.type = input.type === \'password\' ? \'text\' : \'password\';\n  }\n\n  function renderState(data) {\n    if (data && data.logged_in) {\n      document.getElementById(\'loginSection\').classList.add(\'hidden\');\n      document.getElementById(\'dashboardSection\').classList.remove(\'hidden\');\n      const email = (data.user && data.user.email) || data.account || \'Conta Anycubic Conectada\';\n      document.getElementById(\'userEmail\').textContent = email;\n\n      const list = document.getElementById(\'printersList\');\n      list.innerHTML = \'\';\n      const printers = data.printers || [];\n      if (printers.length === 0) {\n        list.innerHTML = \'<div style="padding: 16px; text-align: center; color: var(--text-muted); font-size: 13px;">Nenhuma impressora encontrada nesta conta. Vincule sua impressora no app Anycubic primeiro.</div>\';\n      } else {\n        printers.forEach(p => {\n          const isOnline = p.online || p.state === \'online\' || p.state === \'printing\' || p.status === 1;\n          const isPrinting = p.state === \'printing\';\n          const badgeClass = isPrinting ? \'status-printing\' : (isOnline ? \'status-online\' : \'status-offline\');\n          const badgeText = isPrinting ? \'Imprimindo\' : (isOnline ? \'Online / Em espera\' : \'Offline\');\n          const nozzle = (p.nozzle_temp !== undefined && p.nozzle_temp !== null) ? p.nozzle_temp + \' °C\' : \'--\';\n          const bed = (p.bed_temp !== undefined && p.bed_temp !== null) ? p.bed_temp + \' °C\' : \'--\';\n          \n          list.innerHTML += `\n            <div class="printer-card">\n              <div class="printer-info">\n                <div class="printer-icon">\n                  <svg viewBox="0 0 24 24"><path d="M19 8h-1V3H6v5H5c-1.66 0-3 1.34-3 3v6h4v4h12v-4h4v-6c0-1.66-1.34-3-3-3zM8 5h8v3H8V5zm8 14H8v-4h8v4zm2-4v-2H6v2H4v-4c0-.55.45-1 1-1h14c.55 0 1 .45 1 1v4h-2z"/></svg>\n                </div>\n                <div>\n                  <div class="printer-name">${p.name || p.model || \'Anycubic 3D Printer\'}</div>\n                  <div class="printer-sub">${p.device_id || p.id || \'\'}</div>\n                </div>\n              </div>\n              <div class="printer-telemetry">\n                <div class="telemetry-item">\n                  <span class="telemetry-val">${nozzle}</span>\n                  <span class="telemetry-lbl">Bico</span>\n                </div>\n                <div class="telemetry-item">\n                  <span class="telemetry-val">${bed}</span>\n                  <span class="telemetry-lbl">Mesa</span>\n                </div>\n                <span class="status-badge ${badgeClass}">${badgeText}</span>\n              </div>\n            </div>\n          `;\n        });\n      }\n    } else {\n      document.getElementById(\'loginSection\').classList.remove(\'hidden\');\n      document.getElementById(\'dashboardSection\').classList.add(\'hidden\');\n    }\n  }\n\n  function sendMessage(payload) {\n    if (window.orca && typeof window.orca.postMessage === \'function\') {\n      window.orca.postMessage(payload);\n    }\n  }\n\n  function requestStatus() {\n    sendMessage({ action: \'get_status\' });\n  }\n\n  function handleLogin(e) {\n    e.preventDefault();\n    hideAlert();\n    const acc = document.getElementById(\'inputAccount\').value.trim();\n    const pwd = document.getElementById(\'inputPassword\').value.trim();\n    if (!acc || !pwd) return;\n\n    const btn = document.getElementById(\'btnLogin\');\n    const txt = document.getElementById(\'btnLoginText\');\n    const spin = document.getElementById(\'btnSpinner\');\n    btn.disabled = true;\n    txt.textContent = \'Autenticando...\';\n    spin.classList.remove(\'hidden\');\n\n    sendMessage({ action: \'login\', account: acc, password: pwd });\n  }\n\n  function handleLogout() {\n    if (confirm(\'Deseja realmente desconectar da Anycubic Cloud?\')) {\n      sendMessage({ action: \'logout\' });\n    }\n  }\n\n  if (window.orca && typeof window.orca.onMessage === \'function\') {\n    window.orca.onMessage(function(msg) {\n      if (typeof msg === \'string\') {\n        try { msg = JSON.parse(msg); } catch(e) {}\n      }\n      if (!msg) return;\n\n      const btn = document.getElementById(\'btnLogin\');\n      const txt = document.getElementById(\'btnLoginText\');\n      const spin = document.getElementById(\'btnSpinner\');\n      if (btn) btn.disabled = false;\n      if (txt) txt.textContent = \'Conectar à Anycubic Cloud\';\n      if (spin) spin.classList.add(\'hidden\');\n\n      if (msg.action === \'status\') {\n        renderState(msg);\n      } else if (msg.action === \'login_result\') {\n        if (msg.success) {\n          showAlert(\'Conectado com sucesso!\', \'success\');\n          renderState({ logged_in: true, user: msg.user, printers: msg.printers });\n          if (window.orca && typeof window.orca.saveConfig === \'function\') {\n            window.orca.saveConfig({ token: msg.token, user_id: msg.user_id, account: msg.user && msg.user.email });\n          }\n        } else {\n          showAlert(msg.error || \'Credenciais inválidas. Verifique seu e-mail e senha.\', \'danger\');\n        }\n      } else if (msg.action === \'logout_result\') {\n        showAlert(\'Desconectado com sucesso.\', \'info\');\n        renderState({ logged_in: false });\n        if (window.orca && typeof window.orca.saveConfig === \'function\') {\n          window.orca.saveConfig({});\n        }\n      }\n    });\n  }\n\n  if (window.orca && window.orca.onConfig) {\n    window.orca.onConfig(function(cfg) {\n      if (cfg && cfg.token) {\n        renderState({ logged_in: true, account: cfg.account, printers: cfg.printers });\n      }\n    });\n  }\n\n  requestStatus();\n</script>\n</body>\n</html>'


class AnycubicCloudPage(PagesPluginCapabilityBase):
    """Aba nativa Anycubic Cloud no topo do OrcaSlicer."""

    def __init__(self):
        super().__init__()
        self._client = AnycubicCloudClient()

    def get_name(self) -> str:
        return "Anycubic Cloud"

    def get_icon(self) -> str:
        return ""

    def get_ui(self) -> str:
        return get_cloud_ui_html()

    def has_config_ui(self) -> bool:
        return True

    def get_config_ui(self) -> str:
        return get_cloud_ui_html()

    def on_message(self, message):
        """Processa mensagens enviadas pelo JavaScript via window.orca.postMessage."""
        logger.info("AnycubicCloudPage on_message: %s", message)
        if isinstance(message, str):
            try:
                message = json.loads(message)
            except Exception:
                pass
        if not isinstance(message, dict):
            return

        action = message.get("action", "")

        if action == "get_status":
            token = get_token()
            if token:
                self._client.set_token(token)
                printers = []
                try:
                    printers = self._client.get_printers()
                    statuses = {str(s.get("device_id") or s.get("id")): s for s in self._client.get_printers_status()}
                    for p in printers:
                        pid = str(p.get("device_id") or p.get("id"))
                        st = statuses.get(pid, {})
                        if st:
                            p["nozzle_temp"] = st.get("nozzle_temp", 0.0)
                            p["bed_temp"] = st.get("bed_temp", 0.0)
                            p["state"] = "printing" if st.get("status") == 2 else "online"
                except Exception as e:
                    logger.warning("Falha ao atualizar impressoras: %s", e)

                resp = {
                    "action": "status",
                    "logged_in": True,
                    "token": token,
                    "user": {"email": get_account_email()},
                    "printers": printers,
                }
            else:
                resp = {"action": "status", "logged_in": False}

            self.post_message(json.dumps(resp))

        elif action == "login":
            account = message.get("account", "").strip()
            password = message.get("password", "").strip()
            try:
                login_data = self._client.login(account, password)
                token = login_data.get("token") or login_data.get("access_token")
                user_id = login_data.get("user_id")

                if token:
                    save_token(token, user_id=user_id, account=account)
                    printers = []
                    try:
                        printers = self._client.get_printers()
                    except Exception:
                        pass

                    resp = {
                        "action": "login_result",
                        "success": True,
                        "token": token,
                        "user_id": user_id,
                        "user": {"email": account, "user_id": user_id},
                        "printers": printers,
                    }
                else:
                    resp = {
                        "action": "login_result",
                        "success": False,
                        "error": login_data.get("msg") or "Token não retornado pela Anycubic",
                    }
            except Exception as err:
                logger.error("Erro na autenticação: %s", err)
                resp = {"action": "login_result", "success": False, "error": str(err)}

            self.post_message(json.dumps(resp))

        elif action == "logout":
            save_token("", user_id="", account="")
            self.post_message(json.dumps({"action": "logout_result", "success": True}))


# ============================================================================
# 5. PrinterAgent OrcaSlicer
# ============================================================================

class AnycubicPrinterAgent(PrinterAgentBase):
    """Agente de impressora Anycubic para comunicação na aba Dispositivo e fatiador."""

    def __init__(self):
        super().__init__()
        self._client = AnycubicCloudClient()
        self._telemetry = None
        self._device_id = None
        self._on_message_fn = None
        self._on_printer_connected_fn = None
        self._on_user_message_fn = None
        self._queue_on_main_fn = None

    def get_name(self) -> str:
        return "Anycubic Cloud Agent"

    def connect_printer(self, params) -> bool:
        tok = get_token()
        if not tok:
            logger.warning("Token Anycubic Cloud ausente. Use a aba Anycubic Cloud para autenticar.")
            return False

        self._client.set_token(tok)
        dev_id = getattr(params, "dev_id", "") or ""
        self._device_id = dev_id

        self._telemetry = AnycubicTelemetryBridge(
            device_id=dev_id,
            client=self._client,
            on_telemetry_fn=self._on_telemetry_update
        )
        self._telemetry.start()

        if self._on_printer_connected_fn:
            try:
                self._on_printer_connected_fn(dev_id)
            except Exception:
                pass
        return True

    def disconnect_printer(self) -> None:
        if self._telemetry:
            self._telemetry.stop()
            self._telemetry = None

    def _on_telemetry_update(self, payload: str):
        if self._on_message_fn:
            try:
                self._on_message_fn("status", payload)
            except Exception:
                pass

    def start_discovery(self, fn) -> None:
        try:
            printers = self._client.get_printers()
            for p in printers:
                info = {
                    "name": p.get("name") or p.get("model") or "Anycubic 3D Printer",
                    "dev_id": str(p.get("device_id") or p.get("id") or ""),
                    "model": p.get("model") or "Kobra",
                }
                fn(json.dumps(info))
        except Exception as e:
            logger.warning("Erro no discovery: %s", e)

    def send_message(self, message: str) -> None:
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

    def start_print(self, params, update_fn, cancel_fn, wait_fn) -> int:
        return 0

    def start_local_print(self, params, update_fn, cancel_fn, wait_fn) -> int:
        return self.start_print(params, update_fn, cancel_fn, wait_fn)

    def start_local_print_with_record(self, params, update_fn, cancel_fn, wait_fn) -> int:
        return self.start_print(params, update_fn, cancel_fn, wait_fn)

    def start_sdcard_print(self, params, update_fn) -> None:
        pass

    def start_send_gcode_to_sdcard(self, params, update_fn, cancel_fn, wait_fn) -> int:
        return 0

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
# 6. Pacote do Plugin OrcaSlicer
# ============================================================================

@orca.plugin
class AnycubicCloudPlugin(PluginBase):
    """Pacote principal do plugin Anycubic Cloud para OrcaSlicer."""

    @classmethod
    def register_capabilities(cls):
        """Registra as capacidades do plugin no carregamento do OrcaSlicer."""
        try:
            orca.register_capability(AnycubicCloudPage)
        except Exception as e:
            logger.warning("Falha ao registrar AnycubicCloudPage: %s", e)

        try:
            orca.register_capability(AnycubicPrinterAgent)
        except Exception as e:
            logger.warning("Falha ao registrar AnycubicPrinterAgent: %s", e)

        try:
            orca.request_permissions(
                network=[
                    "https://cloud-universe.anycubic.com",
                    "https://s3.anycubic.com",
                    "https://oss.anycubic.com",
                    "https://mqtt-universe.anycubic.com",
                ],
                threading=True,
                fs_read=[str(CONFIG_DIR) + "/*"],
                fs_readwrite=[str(CONFIG_DIR) + "/*"],
            )
        except Exception as e:
            logger.warning("Falha ao solicitar permissoes: %s", e)

    def has_config_ui(self) -> bool:
        return True

    def get_config_ui(self) -> str:
        return get_cloud_ui_html()
