$ErrorActionPreference = 'Stop'
$rgRoot = Split-Path -Parent $PSScriptRoot
$rgTool = 'E:\develop\wechatpg\微信web开发者工具\cli.bat'
if (-not (Test-Path -LiteralPath $rgTool)) { throw '找不到微信开发者工具，请修改脚本中的工具安装路径。' }
Push-Location $rgRoot
try {
    & node scripts/build_miniprogram.mjs
    if ($LASTEXITCODE -ne 0) { throw '小程序数据生成失败。' }
    $rgReady = $false
    try { $rgStatus = Invoke-RestMethod 'http://127.0.0.1:8095/api/assistant/status' -TimeoutSec 3; $rgReady = $rgStatus.provider -eq 'DeepSeek' } catch {}
    if (-not $rgReady) {
        New-Item -ItemType Directory -Path (Join-Path $rgRoot 'runtime') -Force | Out-Null
        Start-Process -FilePath (Get-Command node).Source -ArgumentList 'serve-hk.mjs' -WorkingDirectory $rgRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $rgRoot 'runtime/mini-server.log') -RedirectStandardError (Join-Path $rgRoot 'runtime/mini-server-error.log')
    }
    & $rgTool open --project $PSScriptRoot --lang zh
    Write-Host '工程已打开。请在开发者工具点击编译，服务地址为 http://127.0.0.1:8095。'
} finally { Pop-Location }
