$ErrorActionPreference = 'Stop'
$rgProjectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $rgProjectRoot
try {
    if (-not (Test-Path -LiteralPath 'runtime/enterprise.env')) {
        throw '缺少本机配置，请先按企业工作流说明初始化；不要把密钥写在本脚本中。'
    }
    & docker compose --env-file runtime/enterprise.env -f compose.enterprise.yml up -d --wait
    if ($LASTEXITCODE -ne 0) { throw '平台未就绪，请检查Docker Desktop是否运行。' }
    $rgNode = (Get-Command node).Source
    Start-Process -FilePath $rgNode -ArgumentList @('scripts/interview_browser.mjs') -WorkingDirectory $rgProjectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $rgProjectRoot 'runtime/interview-launch.log') -RedirectStandardError (Join-Path $rgProjectRoot 'runtime/interview-launch-error.log')
    Write-Host '面试浏览器正在打开；若已有专用浏览器窗口，请直接使用已有窗口。'
    Write-Host '主平台：http://127.0.0.1:8100/'
} finally { Pop-Location }
