# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "paho-mqtt>=2.0.0",
#     "requests>=2.31.0",
# ]
# [tool.orcaslicer.plugin]
# name = "anycubic-cloud"
# version = "1.0.0"
# description = "Native Anycubic Cloud Connection for OrcaSlicer"
# author = "Anycubic & OrcaSlicer Community"
# ///

"""
Anycubic Cloud Plugin for OrcaSlicer.
Enables native connection, status monitoring, and cloud print dispatching for Anycubic printers
(such as Kobra 3, Kobra X, Kobra S1, and Kobra series) directly inside OrcaSlicer.
"""

import sys
import os

# Ensure local module directory is in sys.path
plugin_dir = os.path.dirname(os.path.abspath(__file__))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

import orca
from agent import AnycubicPrinterAgent
from token_manager import get_token, save_token


@orca.plugin
class AnycubicCloudPlugin(orca.PythonPluginBase):
    def register_capabilities(self):
        """Register the Anycubic Cloud Printer Agent into OrcaSlicer."""
        orca.register_capability(AnycubicPrinterAgent)
        try:
            orca.request_permissions(
                network=["mqtt-universe.anycubic.com", "cloud-universe.anycubic.com", "api.anycubic.com"]
            )
        except Exception:
            pass

    def has_config_ui(self) -> bool:
        """Tell OrcaSlicer to display our custom HTML login page instead of raw JSON."""
        return True

    def get_config_ui(self) -> str:
        """Return the embedded HTML configuration and login interface."""
        current_token = get_token() or ""
        logged_in = bool(current_token)

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Anycubic Cloud - Login</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #1e1e1e;
            color: #ffffff;
            margin: 0;
            padding: 24px;
        }}
        .card {{
            background: #2a2a2a;
            border-radius: 8px;
            padding: 24px;
            max-width: 440px;
            margin: 0 auto;
            border: 1px solid #3a3a3a;
        }}
        h2 {{
            margin-top: 0;
            color: #00a8ff;
            font-size: 20px;
        }}
        p {{
            color: #aaa;
            font-size: 13px;
            line-height: 1.4;
        }}
        label {{
            display: block;
            margin-top: 14px;
            font-size: 12px;
            font-weight: 600;
            color: #ddd;
        }}
        input[type="text"], input[type="password"] {{
            width: 100%;
            padding: 10px;
            margin-top: 6px;
            background: #363636;
            border: 1px solid #4a4a4a;
            border-radius: 4px;
            color: #fff;
            box-sizing: border-box;
            font-size: 14px;
        }}
        button {{
            width: 100%;
            padding: 12px;
            margin-top: 20px;
            background: #007aff;
            color: #fff;
            border: none;
            border-radius: 4px;
            font-size: 14px;
            font-weight: bold;
            cursor: pointer;
        }}
        button:hover {{
            background: #0062cc;
        }}
        .secondary-btn {{
            background: #444;
            margin-top: 10px;
        }}
        .secondary-btn:hover {{
            background: #555;
        }}
        .status {{
            margin-top: 14px;
            font-size: 13px;
            padding: 10px;
            border-radius: 4px;
            display: none;
        }}
        .status.success {{
            background: rgba(46, 204, 113, 0.2);
            color: #2ecc71;
            display: block;
        }}
        .status.error {{
            background: rgba(231, 76, 60, 0.2);
            color: #e74c3c;
            display: block;
        }}
    </style>
</head>
<body>
    <div class="card">
        <h2>Anycubic Cloud</h2>
        <p>Conecte sua conta para sincronizar suas impressoras (Kobra 3, Kobra X, Kobra S1) diretamente no OrcaSlicer mantendo o app Anycubic conectado.</p>
        
        <div id="statusBox" class="status {'success' if logged_in else ''}">
            {'✓ Conectado na Anycubic Cloud' if logged_in else ''}
        </div>

        <form id="loginForm" onsubmit="handleLogin(event)">
            <label>E-mail ou Usuário Anycubic:</label>
            <input type="text" id="email" required placeholder="exemplo@email.com">

            <label>Senha:</label>
            <input type="password" id="password" required placeholder="••••••••">

            <button type="submit" id="submitBtn">Entrar na Conta Anycubic</button>
            <button type="button" class="secondary-btn" onclick="openNativeWindow()">Abrir Janela de Login Completa</button>
        </form>
    </div>

    <script>
        async function handleLogin(e) {{
            e.preventDefault();
            const email = document.getElementById("email").value;
            const password = document.getElementById("password").value;
            const statusBox = document.getElementById("statusBox");
            const btn = document.getElementById("submitBtn");

            btn.disabled = true;
            btn.innerText = "Conectando...";
            statusBox.className = "status";
            statusBox.style.display = "block";
            statusBox.innerText = "Autenticando na Anycubic Cloud...";

            try {{
                const res = await fetch("https://cloud-universe.anycubic.com/user/public/login", {{
                    method: "POST",
                    headers: {{
                        "Content-Type": "application/json",
                        "XX-Device-Type": "pc",
                        "XX-Version": "2.0.0"
                    }},
                    body: JSON.stringify({{
                        account: email,
                        password: password,
                        login_type: 1
                    }})
                }});

                const data = await res.json();
                if (data.code === 0 || data.code === 200) {{
                    const token = data.data.access_token || data.data.token;
                    statusBox.className = "status success";
                    statusBox.innerText = "✓ Login realizado com sucesso!";
                    if (window.orca && window.orca.saveConfig) {{
                        window.orca.saveConfig(JSON.stringify({{ token: token, user_id: data.data.user_id }}));
                    }}
                }} else {{
                    statusBox.className = "status error";
                    statusBox.innerText = "Erro: " + (data.msg || "Usuário ou senha incorretos.");
                }}
            }} catch (err) {{
                statusBox.className = "status error";
                statusBox.innerText = "Erro ao conectar: " + err.message;
            }} finally {{
                btn.disabled = false;
                btn.innerText = "Entrar na Conta Anycubic";
            }}
        }}

        function openNativeWindow() {{
            if (window.orca && window.orca.postMessage) {{
                window.orca.postMessage({{ action: "open_login_window" }});
            }}
        }}
    </script>
</body>
</html>"""
        return html
