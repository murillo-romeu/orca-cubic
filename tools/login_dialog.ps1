<#
.SYNOPSIS
    Tela de Login Nativa da Anycubic Cloud para o OrcaSlicer.
#>

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$pluginConfigDir = "$env:APPDATA\OrcaSlicer\orca_plugins\anycubic_cloud"
$pluginConfigFile = "$pluginConfigDir\config.json"

# Form Setup
$form = New-Object System.Windows.Forms.Form
$form.Text = "Login - Anycubic Cloud (OrcaSlicer)"
$form.Size = New-Object System.Drawing.Size(460, 420)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.BackColor = [System.Drawing.Color]::FromArgb(35, 38, 43)
$form.ForeColor = [System.Drawing.Color]::White

# Title
$title = New-Object System.Windows.Forms.Label
$title.Text = "Conectar na Anycubic Cloud"
$title.Font = New-Object System.Drawing.Font("Segoe UI", 14, [System.Drawing.FontStyle]::Bold)
$title.Location = New-Object System.Drawing.Point(30, 20)
$title.Size = New-Object System.Drawing.Size(390, 32)
$title.ForeColor = [System.Drawing.Color]::FromArgb(0, 168, 255)
$form.Controls.Add($title)

$subtitle = New-Object System.Windows.Forms.Label
$subtitle.Text = "Entre com seus dados para sincronizar suas impressoras no OrcaSlicer."
$subtitle.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$subtitle.Location = New-Object System.Drawing.Point(30, 55)
$subtitle.Size = New-Object System.Drawing.Size(390, 25)
$subtitle.ForeColor = [System.Drawing.Color]::FromArgb(180, 185, 195)
$form.Controls.Add($subtitle)

# Email Label & Input
$lblEmail = New-Object System.Windows.Forms.Label
$lblEmail.Text = "E-mail ou Usuário Anycubic:"
$lblEmail.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$lblEmail.Location = New-Object System.Drawing.Point(30, 95)
$lblEmail.Size = New-Object System.Drawing.Size(390, 20)
$form.Controls.Add($lblEmail)

$txtEmail = New-Object System.Windows.Forms.TextBox
$txtEmail.Location = New-Object System.Drawing.Point(30, 118)
$txtEmail.Size = New-Object System.Drawing.Size(385, 28)
$txtEmail.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$txtEmail.BackColor = [System.Drawing.Color]::FromArgb(48, 52, 60)
$txtEmail.ForeColor = [System.Drawing.Color]::White
$txtEmail.BorderStyle = "FixedSingle"
$form.Controls.Add($txtEmail)

# Password Label & Input
$lblPass = New-Object System.Windows.Forms.Label
$lblPass.Text = "Senha:"
$lblPass.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$lblPass.Location = New-Object System.Drawing.Point(30, 160)
$lblPass.Size = New-Object System.Drawing.Size(390, 20)
$form.Controls.Add($lblPass)

$txtPass = New-Object System.Windows.Forms.TextBox
$txtPass.Location = New-Object System.Drawing.Point(30, 183)
$txtPass.Size = New-Object System.Drawing.Size(385, 28)
$txtPass.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$txtPass.BackColor = [System.Drawing.Color]::FromArgb(48, 52, 60)
$txtPass.ForeColor = [System.Drawing.Color]::White
$txtPass.PasswordChar = '*'
$txtPass.BorderStyle = "FixedSingle"
$form.Controls.Add($txtPass)

# Status Feedback Label
$lblStatus = New-Object System.Windows.Forms.Label
$lblStatus.Text = ""
$lblStatus.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$lblStatus.Location = New-Object System.Drawing.Point(30, 222)
$lblStatus.Size = New-Object System.Drawing.Size(385, 38)
$lblStatus.ForeColor = [System.Drawing.Color]::Yellow
$form.Controls.Add($lblStatus)

# Login Button
$btnLogin = New-Object System.Windows.Forms.Button
$btnLogin.Text = "Entrar na Conta Anycubic"
$btnLogin.Location = New-Object System.Drawing.Point(30, 270)
$btnLogin.Size = New-Object System.Drawing.Size(385, 38)
$btnLogin.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$btnLogin.BackColor = [System.Drawing.Color]::FromArgb(0, 122, 255)
$btnLogin.ForeColor = [System.Drawing.Color]::White
$btnLogin.FlatStyle = "Flat"
$btnLogin.FlatAppearance.BorderSize = 0
$btnLogin.Cursor = [System.Windows.Forms.Cursors]::Hand
$form.Controls.Add($btnLogin)

# Fallback Web Button
$btnWeb = New-Object System.Windows.Forms.Button
$btnWeb.Text = "Abrir Portal Anycubic no Navegador (QR Code / Web)"
$btnWeb.Location = New-Object System.Drawing.Point(30, 320)
$btnWeb.Size = New-Object System.Drawing.Size(385, 32)
$btnWeb.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnWeb.BackColor = [System.Drawing.Color]::FromArgb(55, 60, 70)
$btnWeb.ForeColor = [System.Drawing.Color]::White
$btnWeb.FlatStyle = "Flat"
$btnWeb.FlatAppearance.BorderSize = 0
$btnWeb.Cursor = [System.Windows.Forms.Cursors]::Hand
$form.Controls.Add($btnWeb)

# Logic: Do Login via REST API
$btnLogin.Add_Click({
    $account = $txtEmail.Text.Trim()
    $password = $txtPass.Text.Trim()

    if ([string]::IsNullOrWhiteSpace($account) -or [string]::IsNullOrWhiteSpace($password)) {
        $lblStatus.ForeColor = [System.Drawing.Color]::Tomato
        $lblStatus.Text = "Por favor, preencha o e-mail e a senha."
        return
    }

    $lblStatus.ForeColor = [System.Drawing.Color]::Yellow
    $lblStatus.Text = "Conectando aos servidores da Anycubic..."
    $btnLogin.Enabled = $false
    $form.Update()

    try {
        $body = @{
            account = $account
            password = $password
            login_type = 1
        } | ConvertTo-Json

        $headers = @{
            "Content-Type" = "application/json"
            "XX-Device-Type" = "pc"
            "XX-Version" = "2.0.0"
        }

        $res = Invoke-RestMethod -Uri "https://cloud-universe.anycubic.com/user/public/login" -Method Post -Body $body -Headers $headers -TimeoutSec 15

        if ($res.code -eq 0 -or $res.code -eq 200) {
            $token = $res.data.access_token
            if (-not $token) { $token = $res.data.token }

            if ($token) {
                if (-not (Test-Path $pluginConfigDir)) {
                    New-Item -ItemType Directory -Force -Path $pluginConfigDir | Out-Null
                }

                $cfg = @{
                    token = $token
                    user_id = $res.data.user_id
                    user_nickname = $res.data.user_nickname
                    updated_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
                }
                $cfg | ConvertTo-Json -Depth 4 | Set-Content -Path $pluginConfigFile -Encoding UTF8

                $lblStatus.ForeColor = [System.Drawing.Color]::LightGreen
                $lblStatus.Text = "Login efetuado com sucesso! Conectando ao OrcaSlicer..."
                $form.Update()
                Start-Sleep -Seconds 1
                $form.Close()
                return
            }
        }

        # Tratamento de erro ou captcha
        $errMsg = if ($res.msg) { $res.msg } else { "Falha no login. Verifique o usuário e senha." }
        $lblStatus.ForeColor = [System.Drawing.Color]::Tomato
        $lblStatus.Text = "Erro: $errMsg"
    } catch {
        $lblStatus.ForeColor = [System.Drawing.Color]::Tomato
        $lblStatus.Text = "Erro de conexão: $($_.Exception.Message)"
    } finally {
        $btnLogin.Enabled = $true
    }
})

# Logic: Open browser portal
$btnWeb.Add_Click({
    Start-Process "https://cloud-universe.anycubic.com"
    $lblStatus.ForeColor = [System.Drawing.Color]::Cyan
    $lblStatus.Text = "Portal aberto no navegador. Caso prefira, cole o token no get_token.ps1."
})

# Show Dialog
[void]$form.ShowDialog()
