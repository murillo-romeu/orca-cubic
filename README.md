# Anycubic Cloud Plugin para OrcaSlicer 🖨️☁️

Plugin nativo para o **OrcaSlicer** que permite conectar, monitorar e enviar impressões diretamente para impressoras **Anycubic** (como **Kobra 3, Kobra X, Kobra S1, Kobra 2**) através da **Anycubic Cloud**, **sem precisar tirar a impressora da internet** e **mantendo o aplicativo oficial Anycubic no celular 100% funcionando**.

---

## 🌟 Vantagens desta Abordagem

* **Sem Modificações no Firmware:** Não precisa instalar firmwares alternativos nem desbloquear modo LAN fechado.
* **Mantém o App Anycubic Conectado:** O aplicativo do celular continua recebendo status, notificações e controle normalmente.
* **Nativo no OrcaSlicer:** Utiliza a arquitetura oficial de plugins em Python do OrcaSlicer (`orca.printer_agent.PrinterAgentBase`), aparecendo diretamente nas configurações da impressora e na aba **Device**.
* **Telemetria em Tempo Real:** Monitora temperatura do bico e da mesa, progresso da impressão, camadas e suporte às 4 baias do **ACE Pro (Anycubic Color Engine)**.

---

## 📁 Estrutura do Projeto

```text
orca-cubic/
├── install_plugin.ps1              # Script de instalação automática para o OrcaSlicer
├── README.md                       # Documentação completa
├── tools/
│   └── get_token.ps1               # Assistente interativo para obter o Token Anycubic
└── src/
    └── anycubic_cloud/
        ├── anycubic_cloud.py       # Ponto de entrada do plugin (PEP 723 + @orca.plugin)
        ├── agent.py                # Implementação de PrinterAgentBase (OrcaSlicer)
        ├── cloud_client.py         # Cliente REST da Anycubic Cloud (Upload e tarefas)
        ├── mqtt_client.py          # Cliente MQTTS (TLS :8883) para telemetria em tempo real
        ├── token_manager.py        # Gerenciamento de credenciais e tokens
        ├── config.json             # Arquivo local de credenciais do usuário
        └── .install_state.json     # Manifesto de registro de plugin do OrcaSlicer
```

---

## 🚀 Como Instalar e Usar (Passo a Passo)

### Passo 1: Instalar o Plugin no OrcaSlicer

Abra o **PowerShell** na pasta do projeto (`d:\Projetos\orca-cubic`) e execute:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_plugin.ps1
```

Esse script irá:
1. Copiar a pasta do plugin para `%AppData%\OrcaSlicer\orca_plugins\anycubic_cloud\`.
2. Habilitar automaticamente a flag `"use_printer_agents": true` no seu `OrcaSlicer.conf` (necessária para ativar os agentes de conexão).

---

### Passo 2: Configurar seu Token de Acesso da Anycubic

A Anycubic usa tokens de sessão para autorizar o slicer e o MQTT. Para configurar:

1. Acesse no seu navegador o portal oficial: **[https://cloud-universe.anycubic.com](https://cloud-universe.anycubic.com)** e faça login com sua conta Anycubic.
2. Pressione **F12** no navegador (Ferramentas de Desenvolvedor) e clique na aba **Console**.
3. Digite o seguinte comando e aperte Enter:
   ```javascript
   window.localStorage["XX-Token"]
   ```
4. Copie o código do token exibido entre aspas.
5. Execute o assistente no PowerShell:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\tools\get_token.ps1
   ```
   E cole o token copiado. O script salvará o token no arquivo `config.json` do plugin.

---

### Passo 3: Ativar o Agente no OrcaSlicer

1. Abra o **OrcaSlicer**.
2. Ao lado do nome da sua impressora (ex: **Anycubic Kobra X 0.4 nozzle** ou Kobra 3), clique no ícone de edição (lápis) para abrir as **Configurações da Impressora**.
3. Certifique-se de que a opção **Modo Avançado (Advanced)** no canto superior direito esteja marcada.
4. Na aba **Basic Information**:
   * No campo **Printer Agent**, selecione: **`Anycubic Cloud`**.
5. Clique em **Salvar (Save)**.

---

### Passo 4: Fatiar e Imprimir!

* **Aba Device:** Ao selecionar sua impressora, o OrcaSlicer conecta na Anycubic Cloud e passa a exibir as temperaturas, status e informações da máquina.
* **Botão Print:** Ao fatiar qualquer modelo e clicar em **Print**, o arquivo fatiado é enviado diretamente para a nuvem da Anycubic, disparando a impressão na sua impressora física com nivelamento automático e gravação de timelapse.

---

## 🛠️ Tecnologias Utilizadas

* **OrcaSlicer CPython Bridge (`orca` module):** Pybind11 / CPython 3.12 embutido no OrcaSlicer.
* **PEP 723 Inline Metadata:** Especificação moderna de metadados e dependências Python para plugins OrcaSlicer.
* **Anycubic Cloud Universe REST API:** Upload de arquivos e orquestração de tarefas.
* **MQTTS TLS (Porta 8883):** Conexão criptografada contínua para recebimento de telemetria sub-segundo da máquina.
