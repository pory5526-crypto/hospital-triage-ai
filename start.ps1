# 医院智能导诊 AI 客服 · 一键启动（局域网可访问）
# 用法：双击 启动.bat，或右键「使用 PowerShell 运行」

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$envFile = Join-Path $root 'backend\.env'
$port = 8000

# 1) Python 虚拟环境
if (-not (Test-Path $python)) {
    Write-Host '[1/5] 首次运行，创建 Python 环境（约 1-2 分钟）…' -ForegroundColor Cyan
    python -m venv (Join-Path $root 'backend\.venv')
    & $python -m pip install --upgrade pip -q -i https://pypi.tuna.tsinghua.edu.cn/simple
    & $python -m pip install -r (Join-Path $root 'backend\requirements.txt') -i https://pypi.tuna.tsinghua.edu.cn/simple
}

# 2) 前端产物
$dist = Join-Path $root 'frontend\dist\index.html'
if (-not (Test-Path $dist)) {
    Write-Host '[2/5] 首次运行，构建前端页面…' -ForegroundColor Cyan
    Push-Location (Join-Path $root 'frontend')
    & npm.cmd install --no-audit --no-fund
    & npm.cmd run build
    Pop-Location
}

# 3) 配置文件
if (-not (Test-Path $envFile)) {
    Write-Host '[3/5] 生成配置文件 backend\.env（大模型 Key 可稍后再填）' -ForegroundColor Cyan
    Copy-Item (Join-Path $root '.env.example') $envFile
}

# 4) 取本机局域网 IP
$lanIp = (
    Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.)' -and $_.InterfaceAlias -notmatch 'VMware|Loopback|Meta' } |
    Sort-Object -Property SkipAsSource, InterfaceIndex |
    Select-Object -First 1
).IPAddress

if (-not $lanIp) { $lanIp = '127.0.0.1' }

# 5) 提示 & 启动（绑 0.0.0.0，局域网其它设备才能访问）
Write-Host ''
Write-Host '==================== 访问地址 ====================' -ForegroundColor Green
Write-Host ("  本机：      http://127.0.0.1:{0}" -f $port)
Write-Host ("  局域网：    http://{0}:{1}" -f $lanIp, $port) -ForegroundColor Yellow
Write-Host  '  （手机/同事电脑连同一个 WiFi 即可打开上面这个局域网地址）'
Write-Host '==================================================' -ForegroundColor Green
Write-Host ''
Write-Host '  关闭本窗口即停止服务' -ForegroundColor DarkGray
Write-Host ''

Start-Sleep -Milliseconds 800
Start-Process ("http://127.0.0.1:{0}" -f $port)

& $python -m uvicorn app.main:app --host 0.0.0.0 --port $port --app-dir (Join-Path $root 'backend')
