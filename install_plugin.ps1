# Instalador do Plugin Anycubic Cloud para o OrcaSlicer

$orcaAppData = "$env:APPDATA\OrcaSlicer"
$pluginsDir = "$orcaAppData\orca_plugins"
$targetDir = "$pluginsDir\anycubic_cloud"
$orcaConf = "$orcaAppData\OrcaSlicer.conf"
$sourceDir = "$PSScriptRoot\src\anycubic_cloud"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "      Instalacao do Plugin Anycubic Cloud no OrcaSlicer   " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $orcaAppData)) {
    Write-Host " [ERRO] Diretorio do OrcaSlicer nao foi encontrado em: $orcaAppData" -ForegroundColor Red
    Write-Host "Certifique-se de que o OrcaSlicer esta instalado."
    Exit 1
}

# 1. Criar pasta de destino
if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    Write-Host " Diretorio criado: $targetDir" -ForegroundColor Green
}

# 2. Copiar arquivos do plugin
Write-Host " Copiando arquivos do plugin..." -ForegroundColor Cyan
$files = Get-ChildItem -Path $sourceDir -Force
foreach ($f in $files) {
    $dest = Join-Path $targetDir $f.Name
    if ($f.Name -eq "config.json" -and (Test-Path $dest)) {
        Write-Host "   Mantendo config.json existente." -ForegroundColor DarkGray
        continue
    }
    Copy-Item -Path $f.FullName -Destination $dest -Force
    Write-Host "   -> $($f.Name)" -ForegroundColor White
}

# 3. Habilitar use_printer_agents no OrcaSlicer.conf
if (Test-Path $orcaConf) {
    Write-Host " Verificando configuracao do OrcaSlicer (use_printer_agents)..." -ForegroundColor Cyan
    try {
        $confContent = Get-Content $orcaConf -Raw -Encoding UTF8
        if ($confContent -match '"use_printer_agents":\s*false') {
            Write-Host "   Ativando use_printer_agents: true no OrcaSlicer.conf..." -ForegroundColor Yellow
            Copy-Item $orcaConf "$orcaConf.backup_anycubic" -Force
            $updatedConf = $confContent -replace '"use_printer_agents":\s*false', '"use_printer_agents": true'
            Set-Content -Path $orcaConf -Value $updatedConf -Encoding UTF8
            Write-Host "    use_printer_agents ativado com sucesso!" -ForegroundColor Green
        } else {
            Write-Host "    use_printer_agents ja esta habilitado." -ForegroundColor Green
        }
    } catch {
        Write-Host "    Aviso ao atualizar OrcaSlicer.conf: $($_.Exception.Message)" -ForegroundColor DarkYellow
    }
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "         Plugin Anycubic Cloud Instalado com Sucesso!     " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "PROXIMOS PASSOS:" -ForegroundColor Cyan
Write-Host "1. Configure seu token executando:"
Write-Host "   powershell -ExecutionPolicy Bypass -File .\tools\get_token.ps1" -ForegroundColor Yellow
Write-Host ""
Write-Host "2. Abra o OrcaSlicer e em qualquer impressora (ex: Kobra X / Kobra series):"
Write-Host "   - Abra as configuracoes da impressora (icone de edicao ao lado do nome da impressora)"
Write-Host "   - Ative 'Modo Avancado' (Advanced)"
Write-Host "   - Em 'Basic Information' -> 'Printer Agent', selecione 'Anycubic Cloud'"
Write-Host ""
Write-Host "3. Pronto! Na aba 'Device' e no botao 'Print', voce estara conectado"
Write-Host "   diretamente na Anycubic Cloud, mantendo sua impressora na nuvem e no app!" -ForegroundColor Green
Write-Host ""
