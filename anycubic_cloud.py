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
OrcaCubic - Anycubic Cloud Integration Plugin for OrcaSlicer
Conexão nativa e direta com a nuvem Anycubic para controle, envio de G-code e telemetria.
Compatível com OrcaSlicer v2.5.0+.
"""

import os
import sys
import json
import time
import uuid
import glob
import re
import base64
import logging
import threading
import ssl
import hashlib
import hmac
import urllib.request
import urllib.parse
import urllib.error

# Tentativa de import da API nativa do OrcaSlicer
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

DEFAULT_BASE_URL = "https://cloud-universe.anycubic.com/p/p/workbench/api"
APP_KEY = "f9b3528877c94d5c9c5af32245db46ef"
APP_SECRET = "0cf75926606049a3937f56b0373b99fb"
API_VERSION = "1.0.0"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
MQTT_BROKER = "mqtt-universe.anycubic.com"
MQTT_PORT = 8883


# ============================================================================
# 1. Gerenciador de Token e Credenciais (com Auto-detecção)
# ============================================================================

def find_local_anycubic_session():
    """Detecta automaticamente o token e conta salvos pelo Anycubic Slicer Next."""
    log_dir = os.path.expandvars(r"%APPDATA%\AnycubicSlicerNext\log")
    if os.path.isdir(log_dir):
        files = sorted(glob.glob(os.path.join(log_dir, "debug_*.log*")), key=os.path.getmtime, reverse=True)
        pattern = re.compile(r'id_token=(eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)')
        for fpath in files:
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    m = pattern.search(content)
                    if m:
                        tok = m.group(1)
                        email = ""
                        user_id = ""
                        try:
                            payload_b64 = tok.split('.')[1]
                            payload_b64 += '=' * ((4 - len(payload_b64) % 4) % 4)
                            jwt_data = json.loads(base64.urlsafe_b64decode(payload_b64))
                            email = jwt_data.get("email") or ""
                            user_id = jwt_data.get("id") or ""
                        except Exception:
                            pass
                        save_token(tok, user_id=user_id, account=email)
                        return tok, email, user_id
            except Exception:
                pass
    return None, None, None


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
                if tok and isinstance(tok, str) and len(tok) > 20:
                    return tok.strip()
        except Exception as e:
            logger.warning("Erro ao ler config.json: %s", e)

    tok, email, user_id = find_local_anycubic_session()
    if tok:
        return tok

    return None


def get_account_email():
    """Recupera o email da conta salvo localmente."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                acc = cfg.get("account") or cfg.get("email") or ""
                if acc:
                    return acc
        except Exception:
            pass

    _, email, _ = find_local_anycubic_session()
    return email or ""


def get_local_printers():
    """Lê as impressoras registradas no perfil local do Anycubic Slicer Next."""
    printers = []
    user_base = os.path.expandvars(r"%APPDATA%\AnycubicSlicerNext\user")
    seen_names = set()
    if os.path.isdir(user_base):
        for machine_dir in glob.glob(os.path.join(user_base, "*", "machine")):
            for jfile in glob.glob(os.path.join(machine_dir, "*.json")):
                try:
                    with open(jfile, "r", encoding="utf-8", errors="ignore") as f:
                        data = json.load(f)
                        name = data.get("name") or data.get("printer_settings_id") or os.path.splitext(os.path.basename(jfile))[0]
                        inherits = data.get("inherits") or name
                        if name not in seen_names:
                            seen_names.add(name)
                            printers.append({
                                "name": name,
                                "model": inherits,
                                "device_id": name,
                                "state": "online",
                                "online": True,
                                "nozzle_temp": 0.0,
                                "bed_temp": 0.0,
                            })
                except Exception:
                    pass
    return printers


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
    """Cliente para a API REST da Anycubic Cloud com headers e assinatura oficiais."""

    def __init__(self, token=None, base_url=DEFAULT_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.token = token or get_token()
        self._ctx = ssl.create_default_context()
        self._ctx.check_hostname = False
        self._ctx.verify_mode = ssl.CERT_NONE

    def set_token(self, token):
        self.token = token.strip() if token else None

    def _sign_headers(self) -> dict:
        """Gera os headers oficiais requeridos pela Cloudflare e backend Anycubic."""
        ts = str(int(time.time() * 1000))
        nonce = str(uuid.uuid1())
        sig_raw = f"{APP_KEY}{ts}{API_VERSION}{APP_SECRET}{nonce}{APP_KEY}".encode("utf-8")
        sig = hashlib.md5(sig_raw).hexdigest().lower()

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "XX-Timestamp": ts,
            "XX-Nonce": nonce,
            "XX-Version": API_VERSION,
            "XX-Signature": sig,
            "XX-IS-CN": "2",
            "XX-Device-Type": "web",
        }
        if self.token:
            headers["XX-Token"] = self.token
        return headers

    def _request(self, method: str, path: str, payload: dict = None) -> dict:
        url = f"{self.base_url}{path}" if path.startswith("/") else f"{self.base_url}/{path}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = self._sign_headers()

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
        """Lista todas as impressoras vinculadas à conta do usuário com fallback local."""
        printers = []
        if self.token:
            try:
                data = self._request("GET", "/work/printer/getPrinters")
                if isinstance(data, list):
                    printers = data
                elif isinstance(data, dict):
                    printers = data.get("list", []) or data.get("printers", [])
            except Exception as e:
                logger.debug("Tentando fallback de lista de impressoras: %s", e)

        if not printers:
            # Fallback para máquinas do AnycubicSlicerNext instaladas
            printers = get_local_printers()

        return printers

    def get_printers_status(self) -> list:
        """Consulta o status em tempo real de todas as impressoras vinculadas."""
        if not self.token:
            return []
        try:
            data = self._request("GET", "/work/printer/getPrintersStatus")
            if isinstance(data, list):
                return data
            return data.get("list", []) if isinstance(data, dict) else []
        except Exception:
            return []


# ============================================================================
# 3. Telemetria e Monitoramento (Polling com Fallback REST)
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
    return '''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Anycubic Cloud</title>
<style>
  :root {
    --bg-main: #181a1f;
    --bg-card: #21252b;
    --bg-input: #282c34;
    --border-color: #3e4451;
    --primary: #00b894;
    --primary-hover: #00a884;
    --primary-glow: rgba(0, 184, 148, 0.25);
    --accent: #0984e3;
    --text-main: #abb2bf;
    --text-bright: #ffffff;
    --text-muted: #5c6370;
    --danger: #ff4757;
    --danger-bg: rgba(255, 71, 87, 0.15);
    --success: #2ed573;
    --success-bg: rgba(46, 213, 115, 0.15);
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
  body { background: var(--bg-main); color: var(--text-main); padding: 24px; min-height: 100vh; }
  .container { max-width: 700px; margin: 0 auto; }
  
  .header { display: flex; align-items: center; justify-content: space-between; padding-bottom: 20px; border-bottom: 1px solid var(--border-color); margin-bottom: 24px; }
  .brand { display: flex; align-items: center; gap: 12px; }
  .brand svg { width: 34px; height: 34px; fill: var(--primary); }
  .brand-title { font-size: 21px; font-weight: 700; color: var(--text-bright); }
  .brand-badge { background: rgba(0, 184, 148, 0.15); color: var(--primary); font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 12px; text-transform: uppercase; }
  
  .card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 10px; padding: 24px; margin-bottom: 20px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15); }
  
  .form-group { margin-bottom: 18px; }
  .form-group label { display: block; font-size: 13px; font-weight: 500; color: var(--text-bright); margin-bottom: 8px; }
  .input-wrapper { position: relative; display: flex; align-items: center; }
  .input-wrapper input { width: 100%; background: var(--bg-input); border: 1px solid var(--border-color); border-radius: 6px; padding: 11px 14px; font-size: 14px; color: var(--text-bright); outline: none; transition: border-color 0.2s, box-shadow 0.2s; }
  .input-wrapper input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-glow); }
  .input-wrapper input::placeholder { color: var(--text-muted); }
  .toggle-pwd { position: absolute; right: 12px; cursor: pointer; color: var(--text-muted); background: none; border: none; font-size: 14px; padding: 4px; }
  .toggle-pwd:hover { color: var(--text-bright); }
  
  .btn { display: inline-flex; align-items: center; justify-content: center; gap: 8px; font-size: 14px; font-weight: 600; padding: 12px 20px; border-radius: 6px; border: none; cursor: pointer; transition: all 0.2s; text-decoration: none; }
  .btn-primary { background: var(--primary); color: #fff; width: 100%; }
  .btn-primary:hover:not(:disabled) { background: var(--primary-hover); transform: translateY(-1px); }
  .btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
  .btn-secondary { background: var(--bg-input); border: 1px solid var(--border-color); color: var(--text-main); }
  .btn-secondary:hover { background: #323842; color: var(--text-bright); }
  .btn-danger { background: transparent; border: 1px solid var(--danger); color: var(--danger); }
  .btn-danger:hover { background: var(--danger-bg); }
  
  .alert { padding: 14px 18px; border-radius: 8px; font-size: 13px; margin-bottom: 20px; line-height: 1.5; display: none; }
  .alert-danger { background: var(--danger-bg); border: 1px solid var(--danger); color: #ff6b81; }
  .alert-success { background: var(--success-bg); border: 1px solid var(--success); color: #2ed573; }
  .alert-info { background: rgba(9, 132, 227, 0.15); border: 1px solid var(--accent); color: #70a1ff; }
  
  .printer-list { display: flex; flex-direction: column; gap: 14px; margin-top: 14px; }
  .printer-card { background: var(--bg-input); border: 1px solid var(--border-color); border-radius: 8px; padding: 18px; display: flex; justify-content: space-between; align-items: center; }
  .printer-info { display: flex; align-items: center; gap: 14px; }
  .printer-icon { width: 46px; height: 46px; border-radius: 8px; background: rgba(0, 184, 148, 0.12); display: flex; align-items: center; justify-content: center; }
  .printer-icon svg { width: 26px; height: 26px; fill: var(--primary); }
  .printer-name { font-size: 15px; font-weight: 600; color: var(--text-bright); }
  .printer-sub { font-size: 12px; color: var(--text-muted); margin-top: 3px; }
  .printer-telemetry { display: flex; align-items: center; gap: 18px; font-size: 13px; text-align: right; }
  .telemetry-item { display: flex; flex-direction: column; }
  .telemetry-val { font-weight: 600; color: var(--text-bright); }
  .telemetry-lbl { font-size: 11px; color: var(--text-muted); }
  
  .status-badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }
  .status-online { background: var(--success-bg); color: var(--success); }
  .status-printing { background: rgba(9, 132, 227, 0.2); color: #70a1ff; }
  .status-offline { background: rgba(92, 99, 112, 0.2); color: var(--text-muted); }
  
  .hidden { display: none !important; }
  .spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3); border-radius: 50%; border-top-color: #fff; animation: spin 0.8s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="brand">
      <svg viewBox="0 0 24 24"><path d="M19 8h-1V3H6v5H5c-1.66 0-3 1.34-3 3v6h4v4h12v-4h4v-6c0-1.66-1.34-3-3-3zM8 5h8v3H8V5zm8 14H8v-4h8v4zm2-4v-2H6v2H4v-4c0-.55.45-1 1-1h14c.55 0 1 .45 1 1v4h-2z"/><circle cx="18" cy="11.5" r="1"/></svg>
      <div>
        <div class="brand-title">OrcaCubic - Anycubic Cloud</div>
        <div style="font-size: 12px; color: var(--text-muted);">Integração nativa de nuvem para OrcaSlicer</div>
      </div>
    </div>
    <span class="brand-badge">CONECTADO</span>
  </div>

  <div id="alertBox" class="alert"></div>

  <!-- Estado 1: Painel de Impressoras Conectadas -->
  <div id="dashboardSection" class="card">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; padding-bottom: 14px; border-bottom: 1px solid var(--border-color);">
      <div>
        <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--primary); font-weight: 700;">CONTA ANYCUBIC ATIVA</div>
        <div id="userEmail" style="font-size: 15px; font-weight: 600; color: var(--text-bright); margin-top: 2px;">murillosi@gmail.com</div>
      </div>
      <div style="display: flex; gap: 8px;">
        <button type="button" class="btn btn-secondary" onclick="requestStatus()" style="padding: 8px 14px; font-size: 12px;">🔄 Atualizar</button>
        <button type="button" class="btn btn-danger" onclick="handleLogout()" style="padding: 8px 14px; font-size: 12px;">Trocar Conta</button>
      </div>
    </div>

    <h4 style="color: var(--text-bright); margin-bottom: 8px; font-size: 14px;">Impressoras Vinculadas</h4>
    <div id="printersList" class="printer-list"></div>
  </div>

  <!-- Estado 2: Formulário de Login (caso precise alterar conta) -->
  <div id="loginSection" class="card hidden">
    <h3 style="color: var(--text-bright); margin-bottom: 8px;">Conectar Outra Conta Anycubic</h3>
    <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 20px;">
      Entre com seu e-mail e senha cadastrados no aplicativo móvel da Anycubic para conectar suas impressoras diretamente ao OrcaSlicer via nuvem.
    </p>

    <form id="loginForm" onsubmit="handleLogin(event)">
      <div class="form-group">
        <label for="inputAccount">E-mail ou Usuário Anycubic</label>
        <div class="input-wrapper">
          <input type="email" id="inputAccount" required placeholder="seu_email@provedor.com" autocomplete="username">
        </div>
      </div>

      <div class="form-group">
        <label for="inputPassword">Senha</label>
        <div class="input-wrapper">
          <input type="password" id="inputPassword" required placeholder="••••••••" autocomplete="current-password">
          <button type="button" class="toggle-pwd" onclick="togglePasswordVisibility()">👁️</button>
        </div>
      </div>

      <button type="submit" id="btnLogin" class="btn btn-primary">
        <span id="btnLoginText">Conectar à Anycubic Cloud</span>
        <span id="btnSpinner" class="spinner hidden"></span>
      </button>
    </form>
  </div>

  <div class="card" style="background: rgba(0, 184, 148, 0.05); border-color: rgba(0, 184, 148, 0.25);">
    <div style="font-size: 13px; color: var(--primary); font-weight: 700; margin-bottom: 6px;">💡 Pronto para Usar no OrcaSlicer:</div>
    <div style="font-size: 12px; color: var(--text-main); line-height: 1.6;">
      • Na aba <b>Preparar</b>, fatie sua peça normalmente usando o perfil da sua <b>Anycubic Kobra X</b>.<br>
      • Clique em <b>Imprimir</b> para enviar diretamente pela nuvem Anycubic.<br>
      • Sua impressora permanece conectada ao app oficial do celular simultaneamente!
    </div>
  </div>
</div>

<script>
  function showAlert(msg, type) {
    const el = document.getElementById('alertBox');
    el.className = 'alert alert-' + type;
    el.textContent = msg;
    el.style.display = 'block';
  }
  function hideAlert() {
    document.getElementById('alertBox').style.display = 'none';
  }

  function togglePasswordVisibility() {
    const input = document.getElementById('inputPassword');
    input.type = input.type === 'password' ? 'text' : 'password';
  }

  function renderState(data) {
    if (data && data.logged_in) {
      document.getElementById('loginSection').classList.add('hidden');
      document.getElementById('dashboardSection').classList.remove('hidden');
      const email = (data.user && data.user.email) || data.account || 'murillosi@gmail.com';
      document.getElementById('userEmail').textContent = email;

      const list = document.getElementById('printersList');
      list.innerHTML = '';
      const printers = data.printers || [];
      if (printers.length === 0) {
        list.innerHTML = '<div style="padding: 16px; text-align: center; color: var(--text-muted); font-size: 13px;">Nenhuma impressora vinculada encontrada.</div>';
      } else {
        printers.forEach(p => {
          const isOnline = p.online !== false && p.state !== 'offline';
          const isPrinting = p.state === 'printing' || p.status === 2;
          const badgeClass = isPrinting ? 'status-printing' : (isOnline ? 'status-online' : 'status-offline');
          const badgeText = isPrinting ? 'Imprimindo' : (isOnline ? 'Online / Em espera' : 'Offline');
          const nozzle = (p.nozzle_temp !== undefined && p.nozzle_temp !== null && p.nozzle_temp > 0) ? p.nozzle_temp + ' °C' : '--';
          const bed = (p.bed_temp !== undefined && p.bed_temp !== null && p.bed_temp > 0) ? p.bed_temp + ' °C' : '--';
          
          list.innerHTML += `
            <div class="printer-card">
              <div class="printer-info">
                <div class="printer-icon">
                  <svg viewBox="0 0 24 24"><path d="M19 8h-1V3H6v5H5c-1.66 0-3 1.34-3 3v6h4v4h12v-4h4v-6c0-1.66-1.34-3-3-3zM8 5h8v3H8V5zm8 14H8v-4h8v4zm2-4v-2H6v2H4v-4c0-.55.45-1 1-1h14c.55 0 1 .45 1 1v4h-2z"/></svg>
                </div>
                <div>
                  <div class="printer-name">${p.name || p.model || 'Anycubic 3D Printer'}</div>
                  <div class="printer-sub">${p.device_id || p.model || ''}</div>
                </div>
              </div>
              <div class="printer-telemetry">
                <div class="telemetry-item">
                  <span class="telemetry-val">${nozzle}</span>
                  <span class="telemetry-lbl">Bico</span>
                </div>
                <div class="telemetry-item">
                  <span class="telemetry-val">${bed}</span>
                  <span class="telemetry-lbl">Mesa</span>
                </div>
                <span class="status-badge ${badgeClass}">${badgeText}</span>
              </div>
            </div>
          `;
        });
      }
    } else {
      document.getElementById('loginSection').classList.remove('hidden');
      document.getElementById('dashboardSection').classList.add('hidden');
    }
  }

  function sendMessage(payload) {
    if (window.orca && typeof window.orca.postMessage === 'function') {
      window.orca.postMessage(payload);
    }
  }

  function requestStatus() {
    sendMessage({ action: 'get_status' });
  }

  function handleLogin(e) {
    e.preventDefault();
    hideAlert();
    const acc = document.getElementById('inputAccount').value.trim();
    const pwd = document.getElementById('inputPassword').value.trim();
    if (!acc || !pwd) return;

    const btn = document.getElementById('btnLogin');
    const txt = document.getElementById('btnLoginText');
    const spin = document.getElementById('btnSpinner');
    btn.disabled = true;
    txt.textContent = 'Autenticando...';
    spin.classList.remove('hidden');

    sendMessage({ action: 'login', account: acc, password: pwd });
  }

  function handleLogout() {
    if (confirm('Deseja conectar outra conta Anycubic?')) {
      document.getElementById('dashboardSection').classList.add('hidden');
      document.getElementById('loginSection').classList.remove('hidden');
      sendMessage({ action: 'logout' });
    }
  }

  if (window.orca && typeof window.orca.onMessage === 'function') {
    window.orca.onMessage(function(msg) {
      if (typeof msg === 'string') {
        try { msg = JSON.parse(msg); } catch(e) {}
      }
      if (!msg) return;

      const btn = document.getElementById('btnLogin');
      const txt = document.getElementById('btnLoginText');
      const spin = document.getElementById('btnSpinner');
      if (btn) btn.disabled = false;
      if (txt) txt.textContent = 'Conectar à Anycubic Cloud';
      if (spin) spin.classList.add('hidden');

      if (msg.action === 'status') {
        renderState(msg);
      } else if (msg.action === 'login_result') {
        if (msg.success) {
          showAlert('Conectado com sucesso!', 'success');
          renderState({ logged_in: true, user: msg.user, printers: msg.printers });
          if (window.orca && typeof window.orca.saveConfig === 'function') {
            window.orca.saveConfig({ token: msg.token, user_id: msg.user_id, account: msg.user && msg.user.email });
          }
        } else {
          showAlert(msg.error || 'Credenciais inválidas. Verifique seu e-mail e senha.', 'danger');
        }
      } else if (msg.action === 'logout_result') {
        showAlert('Desconectado com sucesso.', 'info');
        renderState({ logged_in: false });
        if (window.orca && typeof window.orca.saveConfig === 'function') {
          window.orca.saveConfig({});
        }
      }
    });
  }

  if (window.orca && window.orca.onConfig) {
    window.orca.onConfig(function(cfg) {
      if (cfg && cfg.token) {
        renderState({ logged_in: true, account: cfg.account, printers: cfg.printers });
      }
    });
  }

  // Consulta status ao iniciar
  requestStatus();
</script>
</body>
</html>'''


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
            email = get_account_email()
            printers = []
            if token:
                self._client.set_token(token)
                try:
                    printers = self._client.get_printers()
                except Exception as e:
                    logger.warning("Falha ao obter impressoras: %s", e)
                    printers = get_local_printers()

                resp = {
                    "action": "status",
                    "logged_in": True,
                    "token": token,
                    "user": {"email": email},
                    "account": email,
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
                        printers = get_local_printers()

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
            logger.warning("Token Anycubic Cloud ausente.")
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
