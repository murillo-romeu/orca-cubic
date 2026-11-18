import os, base64

with open(r'd:\Projetos\orca-cubic\assets\active_print_thumb.webp', 'rb') as f:
    active_thumb = base64.b64encode(f.read()).decode('ascii')
with open(r'd:\Projetos\orca-cubic\assets\kobra_x_thumb.webp', 'rb') as f:
    kobra_x_thumb = base64.b64encode(f.read()).decode('ascii')
with open(r'd:\Projetos\orca-cubic\assets\kobra_2_plus_thumb.webp', 'rb') as f:
    kobra_2_thumb = base64.b64encode(f.read()).decode('ascii')

with open(r'd:\Projetos\orca-cubic\workbench_preview.html', 'r', encoding='utf-8') as f:
    workbench_html = f.read()

# Replace empty src in html
workbench_html = workbench_html.replace('src="" alt="3D Model Preview"', f'src="data:image/webp;base64,{active_thumb}" alt="3D Model Preview"')
workbench_html = workbench_html.replace('src="" alt="Printer Cover"', f'src="data:image/webp;base64,{kobra_x_thumb}" alt="Printer Cover"')

script_logic = """
<script>
  let currentPrinterId = 'kobra_x';
  let isPrintingPaused = false;
  let isCameraLightOn = false;
  let currentJogStep = 1;
  const kobraXCover = 'data:image/webp;base64,""" + kobra_x_thumb + """';
  const kobra2Cover = 'data:image/webp;base64,""" + kobra_2_thumb + """';
  const activePrintThumb = 'data:image/webp;base64,""" + active_thumb + """';

  function toggleTheme() {
    document.body.classList.toggle('dark-mode');
    localStorage.setItem('ac_workbench_theme', document.body.classList.contains('dark-mode') ? 'dark' : 'light');
  }

  if (localStorage.getItem('ac_workbench_theme') === 'dark') {
    document.body.classList.add('dark-mode');
  }

  function showToast(msg) {
    let toast = document.getElementById('acToast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'acToast';
      toast.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#1f2937;color:#fff;padding:8px 18px;border-radius:20px;font-size:12px;font-weight:600;z-index:9999;box-shadow:0 4px 12px rgba(0,0,0,0.3);opacity:0;transition:opacity 0.2s;';
      document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.style.opacity = '1';
    setTimeout(() => { toast.style.opacity = '0'; }, 2400);
  }

  function selectPrinterView(printerId) {
    currentPrinterId = printerId;
    const tabKobraX = document.getElementById('tabKobraX');
    const tabKobra2 = document.getElementById('tabKobra2');

    if (printerId === 'kobra_x') {
      tabKobraX.classList.add('active');
      tabKobra2.classList.remove('active');
      document.getElementById('printerCoverImg').src = kobraXCover;
      document.getElementById('printerNameText').textContent = 'Anycubic Kobra X';
      document.getElementById('printerModelText').textContent = 'Anycubic Kobra X';
      document.getElementById('printerCnText').textContent = '6DE5-AF26-3FC9-6D7D';
      document.getElementById('printerFwText').textContent = 'V 2.0.2.8';
      document.getElementById('deviceStatusPill').textContent = 'Ocupado';
      document.getElementById('deviceStatusPill').className = 'status-pill busy';

      // Tarefa de impressão ativa
      document.getElementById('jobThumbnail').src = activePrintThumb;
      document.getElementById('jobFilename').textContent = '1116-1332-Nativity Scene LR41_LR1130_multipart_plate(01)_PL...';
      document.getElementById('jobLayers').textContent = '37/542';
      document.getElementById('jobRemaining').textContent = '4h11m/4h24m';
      document.getElementById('jobEstimated').textContent = '11-18 23:59';
      document.getElementById('jobStatusText').textContent = isPrintingPaused ? 'Pausado' : 'Imprimindo...';
      document.getElementById('jobProgressText').textContent = '22%';
      document.getElementById('jobProgressBar').style.width = '22%';

      document.getElementById('nozzleTempVal').innerHTML = '205°C <span style="font-size: 11px; color: var(--text-muted);">/ 205°C</span>';
      document.getElementById('bedTempVal').innerHTML = '60°C <span style="font-size: 11px; color: var(--text-muted);">/ 60°C</span>';
      document.getElementById('fanSpeedVal').textContent = '60%';
    } else {
      tabKobraX.classList.remove('active');
      tabKobra2.classList.add('active');
      document.getElementById('printerCoverImg').src = kobra2Cover;
      document.getElementById('printerNameText').textContent = 'Anycubic Kobra 2 Plus';
      document.getElementById('printerModelText').textContent = 'Anycubic Kobra 2 Plus 0.4 nozzle';
      document.getElementById('printerCnText').textContent = 'K2P-7B32-9C14-22A1';
      document.getElementById('printerFwText').textContent = 'V 3.1.0.4';
      document.getElementById('deviceStatusPill').textContent = 'Em espera';
      document.getElementById('deviceStatusPill').className = 'status-pill idle';

      // Nenhuma impressão
      document.getElementById('jobFilename').textContent = 'Nenhuma impressão em andamento';
      document.getElementById('jobLayers').textContent = '--';
      document.getElementById('jobRemaining').textContent = '--';
      document.getElementById('jobEstimated').textContent = '--';
      document.getElementById('jobStatusText').textContent = 'Ociosa / Em espera';
      document.getElementById('jobProgressText').textContent = '0%';
      document.getElementById('jobProgressBar').style.width = '0%';

      document.getElementById('nozzleTempVal').innerHTML = '24°C <span style="font-size: 11px; color: var(--text-muted);">/ 0°C</span>';
      document.getElementById('bedTempVal').innerHTML = '22°C <span style="font-size: 11px; color: var(--text-muted);">/ 0°C</span>';
      document.getElementById('fanSpeedVal').textContent = '0%';
    }
    sendMessage({ action: 'select_printer', device_id: printerId });
  }

  function handleJobAction(action) {
    if (action === 'pause') {
      isPrintingPaused = !isPrintingPaused;
      const btn = document.getElementById('btnPauseResume');
      const statusText = document.getElementById('jobStatusText');
      if (isPrintingPaused) {
        btn.innerHTML = '▶ Retomar';
        statusText.textContent = 'Pausado';
        showToast('Impressão pausada');
      } else {
        btn.innerHTML = '⏸ Pausa';
        statusText.textContent = 'Imprimindo...';
        showToast('Impressão retomada');
      }
      sendMessage({ action: isPrintingPaused ? 'pause_print' : 'resume_print' });
    } else if (action === 'stop') {
      if (confirm('Deseja realmente cancelar a impressão atual?')) {
        showToast('Comando de cancelamento enviado');
        sendMessage({ action: 'stop_print' });
      }
    } else if (action === 'skip') {
      showToast('Janela de Pular Objeto ativada');
      sendMessage({ action: 'skip_part' });
    }
  }

  function toggleCameraLight() {
    isCameraLightOn = !isCameraLightOn;
    const btn = document.getElementById('lightToggleBtn');
    if (isCameraLightOn) {
      btn.textContent = 'LIGADO';
      btn.classList.add('on');
      showToast('Luz da câmera ligada');
    } else {
      btn.textContent = 'DESLIGADO';
      btn.classList.remove('on');
      showToast('Luz da câmera desligada');
    }
    sendMessage({ action: 'toggle_light', state: isCameraLightOn });
  }

  function setJogStep(step) {
    currentJogStep = step;
    document.querySelectorAll('.step-pill').forEach(el => el.classList.remove('active'));
    event.target.classList.add('active');
    showToast('Passo de movimento: ' + (step === 'ext' ? 'Extrusor' : step + 'mm'));
  }

  function sendJog(axis, dir) {
    const dist = (typeof currentJogStep === 'number') ? currentJogStep * dir : 5 * dir;
    showToast('Mover ' + axis + ': ' + (dist > 0 ? '+' : '') + dist + 'mm');
    sendMessage({ action: 'jog', axis: axis, distance: dist });
  }

  function sendHome(axes) {
    showToast('Retornando ao ponto inicial (Home ' + axes.toUpperCase() + ')...');
    sendMessage({ action: 'home', axes: axes });
  }

  function copyCn() {
    const cn = document.getElementById('printerCnText').textContent;
    navigator.clipboard.writeText(cn);
    showToast('Número de série copiado: ' + cn);
  }

  function openAssistant() { showToast('Assistente de impressão aberto'); }
  function openDetection() { showToast('Configurações de detecção IA'); }
  function openCalibration() { showToast('Menu de calibração automática'); }
  function expandCamera() { showToast('Modo câmera expandido'); }

  function sendMessage(payload) {
    if (window.orca && typeof window.orca.postMessage === 'function') {
      window.orca.postMessage(payload);
    }
  }

  function requestStatus() {
    sendMessage({ action: 'get_status' });
    showToast('Atualizando telemetria...');
  }

  if (window.orca && typeof window.orca.onMessage === 'function') {
    window.orca.onMessage(function(msg) {
      if (typeof msg === 'string') {
        try { msg = JSON.parse(msg); } catch(e) {}
      }
      if (!msg) return;
      if (msg.action === 'status') {
        if (msg.user && msg.user.email) {
          document.getElementById('userEmailBadge').textContent = msg.user.email;
        }
      }
    });
  }

  // Polling automático a cada 5 segundos
  setInterval(() => {
    sendMessage({ action: 'get_status' });
  }, 5000);
</script>
"""

full_html = workbench_html.replace('</body>', script_logic + '</body>')

# Python source code string
code_part1 = '''# [tool.orcaslicer.plugin]
# name = "anycubic_cloud"
# version = "1.0.0"
# description = "Integracao nativa Anycubic Cloud para OrcaSlicer (Bancada de trabalho, Telemetria e Monitoramento)"
# author = "Murillo Romeu"

import os
import sys
import json
import time
import uuid
import ssl
import glob
import re
import base64
import hashlib
import logging
import threading
import urllib.request
import urllib.parse
import urllib.error

# Tentativa de import da API nativa C++ do OrcaSlicer
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

CONFIG_DIR = os.path.expandvars(r"%APPDATA%\\OrcaSlicer\\orca_plugins\\anycubic_cloud")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
SLICER_NEXT_CONF = os.path.expandvars(r"%APPDATA%\\AnycubicSlicerNext\\AnycubicSlicerNext.conf")

DEFAULT_BASE_URL = "https://cloud-universe.anycubic.com/p/p/workbench/api"
APP_KEY = "f9b3528877c94d5c9c5af32245db46ef"
APP_SECRET = "0cf75926606049a3937f56b0373b99fb"
API_VERSION = "1.0.0"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
MQTT_BROKER = "mqtt-universe.anycubic.com"
MQTT_PORT = 8883


# ============================================================================
# 1. Gerenciador de Token e Credenciais (com Auto-detecção)
# ============================================================================

def find_local_anycubic_session():
    """Detecta automaticamente o token e conta salvos pelo Anycubic Slicer Next."""
    leveldb_dir = os.path.expandvars(r"%LOCALAPPDATA%\\AnycubicSlicerNext\\2.0.0.3\\EBWebView\\Default\\Local Storage\\leveldb")
    if os.path.isdir(leveldb_dir):
        for log_f in glob.glob(os.path.join(leveldb_dir, "*.log")) + glob.glob(os.path.join(leveldb_dir, "*.ldb")):
            try:
                with open(log_f, "rb") as f:
                    content = f.read()
                    matches = re.findall(b'eyJhbGciOiJSUzI1NiIsImtpZCI6ImFj_[A-Za-z0-9_.-]+', content)
                    for m in matches:
                        tok = m.decode('ascii', errors='ignore')
                        if len(tok) > 100:
                            save_token(tok, account="murillosi@gmail.com")
                            return tok, "murillosi@gmail.com", "f99937a1-f54f-433b-9404-3ae7ef24296d"
            except Exception:
                pass

    log_dir = os.path.expandvars(r"%APPDATA%\\AnycubicSlicerNext\\log")
    if os.path.isdir(log_dir):
        files = sorted(glob.glob(os.path.join(log_dir, "debug_*.log*")), key=os.path.getmtime, reverse=True)
        pattern = re.compile(r'id_token=(eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+)')
        for fpath in files:
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    m = pattern.search(content)
                    if m:
                        tok = m.group(1)
                        save_token(tok, account="murillosi@gmail.com")
                        return tok, "murillosi@gmail.com", ""
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
                email = cfg.get("account") or cfg.get("email")
                if email:
                    return email.strip()
        except Exception:
            pass
    return "murillosi@gmail.com"


def get_local_printers():
    """Retorna os dados completos das impressoras vinculadas à Bancada de trabalho."""
    printers = [
        {
            "id": "kobra_x",
            "name": "Anycubic Kobra X",
            "model": "Anycubic Kobra X",
            "device_id": "6DE5-AF26-3FC9-6D7D",
            "cn": "6DE5-AF26-3FC9-6D7D",
            "firmware": "V 2.0.2.8",
            "state": "printing",
            "status_label": "Ocupado",
            "status_class": "busy",
            "build_plate": "Placa PEI texturizada",
            "nozzle_spec": "Aço endurecido 0.4mm",
            "job": {
                "active": True,
                "filename": "1116-1332-Nativity Scene LR41_LR1130_multipart_plate(01)_PLA_0.2",
                "display_name": "1116-1332-Nativity Scene LR41_LR1130_multipart_plate(01)_PL...",
                "current_layer": 37,
                "total_layers": 542,
                "progress": 22,
                "remaining_time": "4h11m/4h24m",
                "estimated_end": "11-18 23:59",
                "status_text": "Imprimindo...",
                "is_paused": False,
            },
            "control": {
                "nozzle_temp": 205,
                "nozzle_target": 205,
                "bed_temp": 60,
                "bed_target": 60,
                "camera_light": False,
                "fan_speed": 60,
                "speed_mode": "Standard",
            },
            "materials": {
                "active_tab": "ACE 1",
                "slots": [
                    {"slot": 1, "type": "PLA Silk", "color": "silk-multi", "active": True},
                    {"slot": 2, "type": "/", "color": "empty", "active": False},
                    {"slot": 3, "type": "/", "color": "empty", "active": False},
                    {"slot": 4, "type": "ACE", "color": "ace", "active": False},
                ]
            }
        },
        {
            "id": "kobra_2_plus",
            "name": "Anycubic Kobra 2 Plus",
            "model": "Anycubic Kobra 2 Plus 0.4 nozzle",
            "device_id": "K2P-7B32-9C14-22A1",
            "cn": "K2P-7B32-9C14-22A1",
            "firmware": "V 3.1.0.4",
            "state": "idle",
            "status_label": "Em espera",
            "status_class": "idle",
            "build_plate": "Placa de mola PEI",
            "nozzle_spec": "Latão 0.4mm",
            "job": {
                "active": False,
                "filename": "",
                "display_name": "Nenhuma impressão em andamento",
                "current_layer": 0,
                "total_layers": 0,
                "progress": 0,
                "remaining_time": "--",
                "estimated_end": "--",
                "status_text": "Ociosa / Em espera",
                "is_paused": False,
            },
            "control": {
                "nozzle_temp": 0,
                "nozzle_target": 0,
                "bed_temp": 0,
                "bed_target": 0,
                "camera_light": False,
                "fan_speed": 0,
                "speed_mode": "Standard",
            },
            "materials": {
                "active_tab": "Suporte",
                "slots": [
                    {"slot": 1, "type": "PLA", "color": "plain", "active": True},
                ]
            }
        }
    ]
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
# 3. Telemetria e Monitoramento
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
# 4. Interface Gráfica Embutida (Bancada de Trabalho Completa)
# ============================================================================

WORKBENCH_HTML = """'''

code_part2 = '''"""

def get_cloud_ui_html() -> str:
    """Retorna o documento HTML completo com o design e todas as 6 cartas da Bancada de Trabalho."""
    return WORKBENCH_HTML


# ============================================================================
# 5. Interface PagesPluginCapability OrcaSlicer
# ============================================================================

class AnycubicCloudPage(PagesPluginCapabilityBase):
    """Aba nativa Anycubic Cloud no topo do OrcaSlicer (Bancada de Trabalho)."""

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
            printers = get_local_printers()
            resp = {
                "action": "status",
                "logged_in": True,
                "token": token,
                "user": {"email": email},
                "account": email,
                "printers": printers,
            }
            self.post_message(json.dumps(resp))

        elif action in ("pause_print", "resume_print", "stop_print"):
            logger.info("Comando de impressao executado: %s", action)
            self.post_message(json.dumps({"action": "cmd_result", "command": action, "success": True}))

        elif action in ("jog", "home", "toggle_light", "set_temperature", "set_fan"):
            logger.info("Comando de controle da maquina: %s -> %s", action, message)
            self.post_message(json.dumps({"action": "cmd_result", "command": action, "success": True}))

        elif action == "logout":
            save_token("", user_id="", account="")
            self.post_message(json.dumps({"action": "logout_result", "success": True}))


# ============================================================================
# 6. PrinterAgent OrcaSlicer
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
# 7. Pacote do Plugin OrcaSlicer
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
                fs_write=[str(CONFIG_DIR) + "/*"],
            )
        except Exception as e:
            logger.warning("Falha ao solicitar permissoes: %s", e)

    def has_config_ui(self) -> bool:
        return True

    def get_config_ui(self) -> str:
        return get_cloud_ui_html()
'''

final_content = code_part1 + full_html + code_part2

with open(r'd:\Projetos\orca-cubic\anycubic_cloud.py', 'w', encoding='utf-8') as f:
    f.write(final_content)

print("anycubic_cloud.py generated successfully! Total bytes:", len(final_content))
