$ErrorActionPreference = 'Stop'
$rgRoot = Split-Path -Parent $PSScriptRoot
Push-Location $rgRoot
try {
    & python enterprise/bootstrap.py
    if ($LASTEXITCODE -ne 0) { throw '生成本机配置失败。' }
    & docker compose --env-file runtime/enterprise.env -f compose.enterprise.yml up -d --build --wait
    if ($LASTEXITCODE -ne 0) { throw '容器启动未完成，请查看企业工作流使用说明。' }
    Write-Host '工作流控制台：http://127.0.0.1:8100'
    Write-Host '天气工作台：http://127.0.0.1:8096'
    Write-Host '管理员登录信息见 runtime/enterprise.env，勿上传或分享该文件。'
} finally { Pop-Location }
