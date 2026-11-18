<#
.SYNOPSIS
    Assistente para obter e configurar o token da Anycubic Cloud no OrcaSlicer.
#>

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$pluginConfigDir = "$env:APPDATA\OrcaSlicer\orca_plugins\anycubic_cloud"
$pluginConfigFile = "$pluginConfigDir\config.json"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "     Assistente de Token Anycubic Cloud para OrcaSlicer   " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Para que o OrcaSlicer conecte diretamente nas suas impressoras Anycubic,"
Write-Host "precisamos do seu token de acesso da conta Anycubic Cloud."
Write-Host ""
Write-Host "MÉTODO RECOMENDADO (Rápido e 100% garantido):" -ForegroundColor Green
Write-Host "1. Abra o navegador e faça login em: https://cloud-universe.anycubic.com"
Write-Host "2. Pressione F12 no navegador (Ferramentas do Desenvolvedor) e abra a aba 'Console'"
Write-Host "3. Cole o comando abaixo e aperte Enter:"
Write-Host "     window.localStorage['XX-Token']" -ForegroundColor Yellow
Write-Host "4. Copie o texto do token que aparecer entre aspas."
Write-Host ""
Write-Host "----------------------------------------------------------"

$userToken = Read-Host "Cole o seu token Anycubic aqui (ou aperte Enter para tentar ler localmente)"

if (-not [string]::IsNullOrWhiteSpace($userToken)) {
    $tokenClean = $userToken.Trim().Trim('"').Trim("'")
    
    if (-not (Test-Path $pluginConfigDir)) {
        New-Item -ItemType Directory -Force -Path $pluginConfigDir | Out-Null
    }

    $cfg = @{
        token = $tokenClean
        updated_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    }

    $cfg | ConvertTo-Json -Depth 4 | Set-Content -Path $pluginConfigFile -Encoding UTF8
    Write-Host ""
    Write-Host " Token salvo com sucesso em:" -ForegroundColor Green
    Write-Host "   $pluginConfigFile" -ForegroundColor White
    Write-Host ""
    Write-Host "Agora o OrcaSlicer já pode conectar nas suas impressoras Anycubic!" -ForegroundColor Green
    Exit
}

# Tentativa de busca automática nos arquivos de configuração locais
$slicerConf = "$env:APPDATA\AnycubicSlicerNext\AnycubicSlicerNext.conf"
if (Test-Path $slicerConf) {
    Write-Host "Verificando se existe token salvo no AnycubicSlicerNext.conf..." -ForegroundColor Cyan
    try {
        $json = Get-Content $slicerConf -Raw -Encoding UTF8 | ConvertFrom-Json
        $token = $json.anycubic_cloud.access_token
        if ($token -and -not $token.EndsWith("==")) {
            if (-not (Test-Path $pluginConfigDir)) {
                New-Item -ItemType Directory -Force -Path $pluginConfigDir | Out-Null
            }
            @{ token = $token } | ConvertTo-Json | Set-Content -Path $pluginConfigFile -Encoding UTF8
            Write-Host " Token extraído com sucesso do AnycubicSlicerNext!" -ForegroundColor Green
            Exit
        }
    } catch {
        # Config criptografada
    }
}

Write-Host "Dica: Cole o token obtido no navegador executando este script novamente." -ForegroundColor Yellow
