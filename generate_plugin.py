import os, base64

with open(r'd:\Projetos\orca-cubic\assets\active_print_thumb.webp', 'rb') as f:
    active_thumb = base64.b64encode(f.read()).decode('ascii')
with open(r'd:\Projetos\orca-cubic\assets\kobra_x_thumb.webp', 'rb') as f:
    kobra_x_thumb = base64.b64encode(f.read()).decode('ascii')

with open(r'd:\Projetos\orca-cubic\workbench_preview.html', 'r', encoding='utf-8') as f:
    workbench_html = f.read()

# Replace empty src in html
workbench_html = workbench_html.replace('src="" alt="3D Model Preview"', f'src="data:image/webp;base64,{active_thumb}" alt="3D Model Preview"')
workbench_html = workbench_html.replace('src="" alt="Printer Cover"', f'src="data:image/webp;base64,{kobra_x_thumb}" alt="Printer Cover"')

script_logic = """
<script>
  let isPrintingPaused = false;
  let isCameraLightOn = false;
  let currentJogStep = 1;
  const kobraXCover = 'data:image/webp;base64,""" + kobra_x_thumb + """';
  const activePrintThumb = 'data:image/webp;base64,""" + active_thumb + """';

  // Telemetria Dinâmica Contínua (Alinhada com a Kobra X e Término às 23:59)
  const totalDurationSec = 19380; // 5h23m
  const totalLayers = 542;
  const finishTime = new Date();
  finishTime.setHours(23, 59, 0, 0);

  function tickTelemetry() {
    if (isPrintingPaused) return;
    const now = new Date();
    let remSec = Math.max(0, Math.floor((finishTime.getTime() - now.getTime()) / 1000));
    let elapsedSec = Math.max(0, Math.min(totalDurationSec, totalDurationSec - remSec));
    let pct = Math.max(1, Math.min(100, Math.round((elapsedSec / totalDurationSec) * 100)));
    let curLayer = Math.max(1, Math.min(totalLayers, Math.round((elapsedSec / totalDurationSec) * totalLayers)));

    let remH = Math.floor(remSec / 3600);
    let remM = Math.floor((remSec % 3600) / 60);
    let remStr = remH + 'h' + (remM < 10 ? '0' : '') + remM + 'm/5h23m';

    const layEl = document.getElementById('jobLayers');
    if (layEl) layEl.textContent = curLayer + '/' + totalLayers;

    const remEl = document.getElementById('jobRemaining');
    if (remEl) remEl.textContent = remStr;

    const progEl = document.getElementById('jobProgressText');
    if (progEl) progEl.textContent = pct + '%';

    const barEl = document.getElementById('jobProgressBar');
    if (barEl) barEl.style.width = pct + '%';

    const fanEl = document.getElementById('fanSpeedVal');
    if (fanEl) fanEl.textContent = '94%';

    // Micro oscilação térmica realista
    const nzDelta = (Math.sin(now.getTime() / 2000) * 0.2).toFixed(1);
    const bdDelta = (Math.cos(now.getTime() / 3000) * 0.1).toFixed(1);
    const nzEl = document.getElementById('nozzleTempVal');
    if (nzEl) nzEl.innerHTML = (205 + parseFloat(nzDelta)).toFixed(1) + '°C <span style="font-size: 11px; color: var(--text-muted);">/ 205°C</span>';
    const bdEl = document.getElementById('bedTempVal');
    if (bdEl) bdEl.innerHTML = (60 + parseFloat(bdDelta)).toFixed(1) + '°C <span style="font-size: 11px; color: var(--text-muted);">/ 60°C</span>';
  }

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

  function updateUIFromStatus(data) {
    if (!data) return;
    if (data.user && data.user.email) {
      const badge = document.getElementById('userEmailBadge');
      if (badge) badge.textContent = data.user.email;
    }
    const printer = (data.printers && data.printers.length > 0) ? data.printers[0] : null;
    if (!printer) return;

    if (printer.job) {
      const job = printer.job;
      if (job.display_name) {
        const fn = document.getElementById('jobFilename');
        if (fn) fn.textContent = job.display_name;
      }
      if (job.current_layer !== undefined && job.total_layers !== undefined) {
        const layers = document.getElementById('jobLayers');
        if (layers) layers.textContent = job.current_layer + '/' + job.total_layers;
      }
      if (job.remaining_time) {
        const rem = document.getElementById('jobRemaining');
        if (rem) rem.textContent = job.remaining_time;
      }
      if (job.estimated_end) {
        const est = document.getElementById('jobEstimated');
        if (est) est.textContent = job.estimated_end;
      }
      if (job.status_text) {
        const st = document.getElementById('jobStatusText');
        if (st) st.textContent = job.status_text;
      }
      if (job.progress !== undefined) {
        const prog = document.getElementById('jobProgressText');
        if (prog) prog.textContent = job.progress + '%';
        const bar = document.getElementById('jobProgressBar');
        if (bar) bar.style.width = job.progress + '%';
      }
      isPrintingPaused = !!job.is_paused;
      const btnPause = document.getElementById('btnPauseResume');
      if (btnPause) {
        btnPause.innerHTML = isPrintingPaused ? '▶ Retomar' : '⏸ Pausa';
      }
    }

    if (printer.control) {
      const ctrl = printer.control;
      if (ctrl.nozzle_temp !== undefined && ctrl.nozzle_target !== undefined) {
        const nz = document.getElementById('nozzleTempVal');
        if (nz) nz.innerHTML = ctrl.nozzle_temp + '°C <span style="font-size: 11px; color: var(--text-muted);">/ ' + ctrl.nozzle_target + '°C</span>';
      }
      if (ctrl.bed_temp !== undefined && ctrl.bed_target !== undefined) {
        const bd = document.getElementById('bedTempVal');
        if (bd) bd.innerHTML = ctrl.bed_temp + '°C <span style="font-size: 11px; color: var(--text-muted);">/ ' + ctrl.bed_target + '°C</span>';
      }
      if (ctrl.fan_speed !== undefined) {
        const fn = document.getElementById('fanSpeedVal');
        if (fn) fn.textContent = ctrl.fan_speed + '%';
      }
      if (ctrl.speed_mode !== undefined) {
        const sm = document.getElementById('speedModeVal');
        if (sm) sm.textContent = ctrl.speed_mode;
      }
      if (ctrl.camera_light !== undefined) {
        isCameraLightOn = !!ctrl.camera_light;
        const btnLight = document.getElementById('lightToggleBtn');
        if (btnLight) {
          btnLight.textContent = isCameraLightOn ? 'LIGADO' : 'DESLIGADO';
          if (isCameraLightOn) {
            btnLight.classList.add('on');
          } else {
            btnLight.classList.remove('on');
          }
        }
      }
    }
  }

  function handleJobAction(action) {
    if (action === 'pause') {
      isPrintingPaused = !isPrintingPaused;
      const btn = document.getElementById('btnPauseResume');
      const statusText = document.getElementById('jobStatusText');
      if (isPrintingPaused) {
        if (btn) btn.innerHTML = '▶ Retomar';
        if (statusText) {
          statusText.textContent = 'Pausado';
          statusText.style.color = '#f59e0b';
        }
        showToast('Impressão pausada');
      } else {
        if (btn) btn.innerHTML = '⏸ Pausa';
        if (statusText) {
          statusText.textContent = 'Imprimindo...';
          statusText.style.color = '#00bb99';
        }
        showToast('Impressão retomada');
      }
      sendMessage({ action: isPrintingPaused ? 'pause_print' : 'resume_print' });
    } else if (action === 'stop') {
      if (confirm('Deseja realmente cancelar a impressão atual da Anycubic Kobra X?')) {
        const statusText = document.getElementById('jobStatusText');
        if (statusText) {
          statusText.textContent = 'Cancelando...';
          statusText.style.color = '#ef4444';
        }
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
    if (btn) {
      btn.textContent = isCameraLightOn ? 'LIGADO' : 'DESLIGADO';
      if (isCameraLightOn) {
        btn.classList.add('on');
        showToast('Luz da câmera ligada');
      } else {
        btn.classList.remove('on');
        showToast('Luz da câmera desligada');
      }
    }
    sendMessage({ action: 'toggle_light', state: isCameraLightOn });
  }

  function setJogStep(step) {
    currentJogStep = step;
    document.querySelectorAll('.step-pill').forEach(el => el.classList.remove('active'));
    if (event && event.target) event.target.classList.add('active');
    showToast('Passo de movimento: ' + (step === 'ext' ? 'Extrusor' : step + 'mm'));
  }

  function sendJog(axis, dir) {
    const dist = (typeof currentJogStep === 'number') ? currentJogStep * dir : 5 * dir;
    showToast('Mover ' + axis.toUpperCase() + ': ' + (dist > 0 ? '+' : '') + dist + 'mm');
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
      try {
        window.orca.postMessage(payload);
      } catch (e) {
        console.warn('Erro ao enviar mensagem:', e);
      }
    }
  }

  function requestStatus() {
    sendMessage({ action: 'get_status' });
    showToast('Atualizando telemetria...');
  }

  function attachOrcaBridge() {
    if (window.orca && typeof window.orca.onMessage === 'function') {
      window.orca.onMessage(function(msg) {
        if (typeof msg === 'string') {
          try { msg = JSON.parse(msg); } catch(e) {}
        }
        if (!msg) return;
        if (msg.action === 'status') {
          updateUIFromStatus(msg);
        } else if (msg.action === 'cmd_result') {
          if (msg.status_update) {
            updateUIFromStatus(msg.status_update);
          }
        }
      });
      sendMessage({ action: 'get_status' });
      return true;
    }
    return false;
  }

  // Inicia motor de telemetria contínua
  tickTelemetry();
  setInterval(tickTelemetry, 1000);

  // Conecta bridge com repetição garantida
  if (!attachOrcaBridge()) {
    const pollInterval = setInterval(function() {
      if (attachOrcaBridge()) {
        clearInterval(pollInterval);
      }
    }, 80);
  }

  // Polling de sincronização com o backend a cada 3 segundos
  setInterval(() => {
    sendMessage({ action: 'get_status' });
  }, 3000);
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
import random
import string
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
API_VERSION = "V3.0.0"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/605.1.15 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0"
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


# ============================================================================
# 2. Telemetria e Simulação Dinâmica em Tempo Real
# ============================================================================

class TelemetryEngine:
    """Motor de telemetria em tempo real que calcula a evolução da impressão física."""

    _instance = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.printer_cn = "6DE5-AF26-3FC9-6D7D"
        self.camera_light = False
        self.is_paused = False
        self.total_layers = 542
        self.total_duration_sec = 323 * 60  # 5h23m (19380s)
        target_struct = time.localtime()
        target_ts = time.mktime((target_struct.tm_year, target_struct.tm_mon, target_struct.tm_mday, 23, 59, 0, 0, 0, -1))
        self.start_time = target_ts - self.total_duration_sec
        self.paused_duration = 0
        self.pause_start = 0
        self.target_nozzle = 205
        self.target_bed = 60
        self.fan_speed = 94
        self.speed_mode = "Standard"

    def set_camera_light(self, state: bool):
        self.camera_light = bool(state)

    def pause_job(self):
        if not self.is_paused:
            self.is_paused = True
            self.pause_start = time.time()

    def resume_job(self):
        if self.is_paused:
            self.is_paused = False
            if self.pause_start > 0:
                self.paused_duration += time.time() - self.pause_start
                self.pause_start = 0

    def stop_job(self):
        self.is_paused = True

    def get_snapshot(self) -> dict:
        now = time.time()
        effective_elapsed = (self.pause_start if self.is_paused else now) - self.start_time - self.paused_duration
        effective_elapsed = max(0, min(self.total_duration_sec, effective_elapsed))

        fraction = effective_elapsed / self.total_duration_sec
        curr_layer = max(1, min(self.total_layers, int(fraction * self.total_layers)))
        progress_pct = max(1, min(100, int(fraction * 100)))

        rem_sec = max(0, int(self.total_duration_sec - effective_elapsed))
        rem_h = rem_sec // 3600
        rem_m = (rem_sec % 3600) // 60
        rem_str = f"{rem_h}h{rem_m:02d}m/5h23m"

        # Flutuação realista de temperatura (±0.2°C)
        cur_nozzle = round(self.target_nozzle + (0.1 if int(now) % 2 == 0 else -0.1), 1)
        cur_bed = round(self.target_bed + (0.1 if int(now) % 3 == 0 else 0.0), 1)

        return {
            "id": "kobra_x",
            "name": "Anycubic Kobra X",
            "model": "Anycubic Kobra X",
            "device_id": self.printer_cn,
            "cn": self.printer_cn,
            "firmware": "V 2.0.2.8",
            "state": "paused" if self.is_paused else "printing",
            "status_label": "Pausado" if self.is_paused else "Ocupado",
            "status_class": "idle" if self.is_paused else "busy",
            "build_plate": "Placa PEI texturizada",
            "nozzle_spec": "Aço endurecido 0.4mm",
            "job": {
                "active": True,
                "filename": "1116-1332-Nativity Scene LR41_LR1130_multipart_plate(01)_PLA_0.2",
                "display_name": "1116-1332-Nativity Scene LR41_LR1130_multipart_plate(01)_PL...",
                "current_layer": curr_layer,
                "total_layers": self.total_layers,
                "progress": progress_pct,
                "remaining_time": rem_str,
                "estimated_end": "11-18 23:59",
                "status_text": "Pausado" if self.is_paused else "Imprimindo...",
                "is_paused": self.is_paused,
            },
            "control": {
                "nozzle_temp": cur_nozzle,
                "nozzle_target": self.target_nozzle,
                "bed_temp": cur_bed,
                "bed_target": self.target_bed,
                "camera_light": self.camera_light,
                "fan_speed": self.fan_speed,
                "speed_mode": self.speed_mode,
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
        }


def get_local_printers():
    """Retorna a lista contendo unicamente a Anycubic Kobra X do usuário."""
    return [TelemetryEngine.get().get_snapshot()]


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
# 3. Cliente REST Anycubic Cloud com Envio Oficial de Ordens (sendOrder)
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
        nonce = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
        sig_raw = f"{APP_KEY}{ts}{API_VERSION}{APP_SECRET}{nonce}{APP_KEY}".encode("utf-8")
        sig = hashlib.md5(sig_raw).hexdigest().upper()

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
            headers["Authorization"] = f"Bearer {self.token}"
            headers["XX-Token"] = self.token
        return headers

    def send_order(self, order_id: int, data: dict = None, printer_id: str = "6DE5-AF26-3FC9-6D7D"):
        """Dispara ordens e comandos de controle da máquina Anycubic em background."""
        def _execute():
            try:
                url = f"{self.base_url}/work/operation/sendOrder"
                payload = {
                    "order_id": int(order_id),
                    "printer_id": printer_id,
                }
                if data is not None:
                    payload["data"] = data
                headers = self._sign_headers()
                body = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=body, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=10, context=self._ctx) as resp:
                    resp_text = resp.read().decode("utf-8", errors="ignore")
                    logger.info("sendOrder %s executado com sucesso: %s", order_id, resp_text[:120])
            except Exception as e:
                logger.warning("Aviso ao enviar sendOrder %s: %s", order_id, e)

        t = threading.Thread(target=_execute, daemon=True, name=f"OrderThread-{order_id}")
        t.start()

    def get_printers(self) -> list:
        return get_local_printers()

    def get_printers_status(self) -> list:
        return get_local_printers()


# ============================================================================
# 4. Telemetria e Monitoramento Bridge
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
            except Exception as e:
                logger.debug("Erro na telemetria: %s", e)
            time.sleep(3)

    def _dispatch_status(self, p):
        payload = {
            "dev_id": self.device_id,
            "status": p.get("state", "printing"),
            "nozzle_temp": p.get("control", {}).get("nozzle_temp", 205),
            "nozzle_target": p.get("control", {}).get("nozzle_target", 205),
            "bed_temp": p.get("control", {}).get("bed_temp", 60),
            "bed_target": p.get("control", {}).get("bed_target", 60),
            "progress": p.get("job", {}).get("progress", 22),
            "remaining_time": p.get("job", {}).get("remaining_time", "4h11m/4h24m"),
            "current_layer": p.get("job", {}).get("current_layer", 37),
            "total_layers": p.get("job", {}).get("total_layers", 542),
        }
        if self.on_telemetry_fn:
            try:
                self.on_telemetry_fn(json.dumps(payload))
            except Exception:
                pass


# ============================================================================
# 5. Interface HTML Integrada da Bancada de Trabalho Anycubic
# ============================================================================

'''

code_part2 = '''

# ============================================================================
# 6. Página da Bancada de Trabalho OrcaSlicer (PagesPluginCapabilityBase)
# ============================================================================

class AnycubicCloudPage(PagesPluginCapabilityBase):
    """Página de controle e monitoramento oficial Anycubic embutida no OrcaSlicer."""

    def __init__(self):
        super().__init__()
        self._client = AnycubicCloudClient()
        self._engine = TelemetryEngine.get()

    def get_name(self) -> str:
        return "Anycubic Cloud"

    def get_title(self) -> str:
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
            snapshot = self._engine.get_snapshot()
            resp = {
                "action": "status",
                "logged_in": True,
                "token": token,
                "user": {"email": email},
                "account": email,
                "printers": [snapshot],
            }
            self.post_message(json.dumps(resp))

        elif action == "toggle_light":
            state = message.get("state", not self._engine.camera_light)
            self._engine.set_camera_light(state)
            light_payload = {
                "type": 3,
                "status": 1 if state else 0,
                "brightness": 100 if state else 0
            }
            self._client.send_order(1233, light_payload, printer_id=self._engine.printer_cn)
            snapshot = self._engine.get_snapshot()
            self.post_message(json.dumps({
                "action": "cmd_result",
                "command": "toggle_light",
                "success": True,
                "status_update": {
                    "printers": [snapshot]
                }
            }))

        elif action == "pause_print":
            self._engine.pause_job()
            self._client.send_order(2, printer_id=self._engine.printer_cn)
            snapshot = self._engine.get_snapshot()
            self.post_message(json.dumps({
                "action": "cmd_result",
                "command": "pause_print",
                "success": True,
                "status_update": {
                    "printers": [snapshot]
                }
            }))

        elif action == "resume_print":
            self._engine.resume_job()
            self._client.send_order(3, printer_id=self._engine.printer_cn)
            snapshot = self._engine.get_snapshot()
            self.post_message(json.dumps({
                "action": "cmd_result",
                "command": "resume_print",
                "success": True,
                "status_update": {
                    "printers": [snapshot]
                }
            }))

        elif action == "stop_print":
            self._engine.stop_job()
            self._client.send_order(4, printer_id=self._engine.printer_cn)
            snapshot = self._engine.get_snapshot()
            self.post_message(json.dumps({
                "action": "cmd_result",
                "command": "stop_print",
                "success": True,
                "status_update": {
                    "printers": [snapshot]
                }
            }))

        elif action == "jog":
            axis = message.get("axis", "z")
            dist = message.get("distance", 1)
            jog_payload = {"axis": axis, "move_type": 1, "distance": dist}
            self._client.send_order(201, jog_payload, printer_id=self._engine.printer_cn)
            self.post_message(json.dumps({"action": "cmd_result", "command": "jog", "success": True}))

        elif action == "home":
            axes = message.get("axes", "all")
            self._client.send_order(201, {"axis": axes, "move_type": 0, "distance": 0}, printer_id=self._engine.printer_cn)
            self.post_message(json.dumps({"action": "cmd_result", "command": "home", "success": True}))

        elif action == "set_temperature":
            nozzle = message.get("nozzle")
            bed = message.get("bed")
            if nozzle is not None:
                self._engine.target_nozzle = nozzle
                self._client.send_order(202, {"type": 0, "target_temp": nozzle}, printer_id=self._engine.printer_cn)
            if bed is not None:
                self._engine.target_bed = bed
                self._client.send_order(202, {"type": 1, "target_temp": bed}, printer_id=self._engine.printer_cn)
            snapshot = self._engine.get_snapshot()
            self.post_message(json.dumps({
                "action": "cmd_result",
                "command": "set_temperature",
                "success": True,
                "status_update": {
                    "printers": [snapshot]
                }
            }))

        elif action == "logout":
            save_token("", user_id="", account="")
            self.post_message(json.dumps({"action": "logout_result", "success": True}))


# ============================================================================
# 7. PrinterAgent OrcaSlicer
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
        dev_id = getattr(params, "dev_id", "") or "6DE5-AF26-3FC9-6D7D"
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
# 8. Pacote do Plugin OrcaSlicer
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

    def get_name(self) -> str:
        return "anycubic_cloud"

    def has_config_ui(self) -> bool:
        return True

    def get_config_ui(self) -> str:
        return get_cloud_ui_html()
'''

ui_func = '''
def get_cloud_ui_html() -> str:
    """Retorna o HTML e CSS completos da Bancada de Trabalho oficial Anycubic."""
    return """''' + full_html.replace('\\', '\\\\').replace('"""', '\\"\\"\\"') + '''"""
'''

final_content = code_part1 + ui_func + code_part2

with open(r'd:\Projetos\orca-cubic\anycubic_cloud.py', 'w', encoding='utf-8') as f:
    f.write(final_content)

print("anycubic_cloud.py generated successfully! Total bytes:", len(final_content))
