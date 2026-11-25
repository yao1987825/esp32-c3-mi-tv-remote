# =============================================================================
#  build.ps1 - 编译 / 烧录 ESP32-C3 的 ESPHome 固件（小米电视蓝牙遥控器）
# =============================================================================
#
#  用法:
#     .\build.ps1            # 编译
#     .\build.ps1 -Upload    # 编译并烧录（不连串口看日志）
#     .\build.ps1 -Run       # 编译、烧录并打开串口日志
#
#  -----------------------------------------------------------------------
#  为什么要 staging 到 C:\esp32c3 ?
#  -----------------------------------------------------------------------
#  本工程位于含中文的路径 D:\esp32-c3开发版\...,
#  而 platformio / MinGW 的 gcc-ld 用 ANSI(本地代码页)解析 argv,
#  遇到中文路径会被误解码,于是在链接时报告
#      "No such file or directory" —— 那些文件其实真实存在。
#
#  解决办法:把「链接器看得见的路径」全部搬到纯 ASCII 目录:
#     C:\esp32c3\esphome\tv-remote.yaml     配置文件
#     C:\esp32c3\esphome\components\...     外部组件 (ble_mi_remote)
#     C:\esp32c3\esphome\.esphome\build\...  编译输出
#
#  源码本身留在原目录 —— 编译器对 UTF-8 路径没有问题。
# =============================================================================

[CmdletBinding()]
param(
    [switch]$Upload,
    [switch]$Run,
    [string]$Port = ''
)

$ErrorActionPreference = 'Stop'

$Root    = $PSScriptRoot
$Parent  = Split-Path (Split-Path $Root -Parent) -Parent
$CompSrc = Join-Path $Parent 'esphome-ble-mi-remote-main\esphome-ble-mi-remote-main\components'
$Stage   = 'C:\esp32c3\esphome'

# --- 0. 找到板子的串口 ------------------------------------------------------
# ESPHome 会把「串口」和「OTA」都列成候选，在非交互环境里会直接 EOF 崩掉，
# 所以这里必须显式指定 --device。
#
# ESP32-C3 的原生 USB (USB Serial/JTAG) 的 VID:PID = 303A:1001，
# 正好能和别的 USB-TTL 转换器区分开。
function Find-C3Port {
    $devices = @(Get-PnpDevice -Class Ports -ErrorAction SilentlyContinue |
        Where-Object { $_.InstanceId -like '*VID_303A&PID_1001*' -and $_.Status -eq 'OK' })
    if ($devices.Count -eq 0) { return '' }
    $m = [regex]::Match($devices[0].FriendlyName, '\((COM\d+)\)')
    if ($m.Success) { return $m.Groups[1].Value }
    return ''
}

if (-not $Port) { $Port = Find-C3Port }
if (-not $Port) {
    throw '找不到 ESP32-C3 的原生 USB 串口 (VID_303A&PID_1001)。请用**数据线**把板子插到这台 PC 上，或用 -Port COMx 指定端口。'
}
Write-Host "      烧录端口: $Port" -ForegroundColor DarkGray

# --- 1. stage ---------------------------------------------------------------
Write-Host '[1/3] stage -> C:\esp32c3\esphome' -ForegroundColor Cyan
if (-not (Test-Path -LiteralPath $CompSrc)) {
    throw "找不到组件目录: $CompSrc"
}
New-Item -ItemType Directory -Path (Join-Path $Stage 'components') -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $CompSrc 'ble_mi_remote') `
          -Destination (Join-Path $Stage 'components') -Recurse -Force
Copy-Item -LiteralPath (Join-Path $Root 'tv-remote.yaml') `
          -Destination (Join-Path $Stage 'tv-remote.yaml') -Force
# 2026-11-25: 配置里改用 `!secret` 引用凭据，secrets.yaml 必须一起 stage，
# 否则 esphome compile 会报 "Secret ... not defined" 直接失败。
# secrets.yaml 不进 Git 仓库（.gitignore），仓库里只有 secrets.yaml.example。
$secrets = Join-Path $Root 'secrets.yaml'
if (-not (Test-Path -LiteralPath $secrets)) {
    throw ("找不到 secrets.yaml —— 凭据（WiFi / OTA / web / API 密钥）都在里面。" +
           "先复制一份: Copy-Item secrets.yaml.example secrets.yaml，然后填上你的值。")
}
Copy-Item -LiteralPath $secrets -Destination (Join-Path $Stage 'secrets.yaml') -Force
Write-Host '      tv-remote.yaml + secrets.yaml + components/ble_mi_remote' -ForegroundColor DarkGray

# --- 2. 找到 esphome --------------------------------------------------------
$esphome = (Get-Command esphome -ErrorAction SilentlyContinue).Source
if (-not $esphome) {
    $guess = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\Scripts\esphome.exe'
    if (Test-Path -LiteralPath $guess) { $esphome = $guess }
}
if (-not $esphome) {
    throw '找不到 esphome —— 先运行: python -m pip install --upgrade esphome'
}

# --- 3. 编译 / 烧录 ---------------------------------------------------------
# 2026-11-23 踩坑: `esphome upload` **不会重新编译**，它直接把 build 目录里
# 现存的 firmware.bin 烧进去。改完 yaml 或组件源码后只跑 -Upload，板上还是
# 老固件（症状: 新加的实体在 HA / web_server 里根本不存在）。
# 所以这里一律先 compile，再 upload。
$yaml = Join-Path $Stage 'tv-remote.yaml'
if ($Run) {
    Write-Host '[2/3] esphome run (编译 + 烧录 + 日志)' -ForegroundColor Cyan
    & $esphome run $yaml --device $Port
} elseif ($Upload) {
    Write-Host '[2/3] esphome compile' -ForegroundColor Cyan
    & $esphome compile $yaml
    if ($LASTEXITCODE -ne 0) {
        throw "esphome compile 失败 (exit $LASTEXITCODE)"
    }
    Write-Host '[3/3] esphome upload (烧录)' -ForegroundColor Cyan
    & $esphome upload $yaml --device $Port
} else {
    Write-Host '[2/3] esphome compile' -ForegroundColor Cyan
    & $esphome compile $yaml
}
if ($LASTEXITCODE -ne 0) {
    throw "esphome 失败 (exit $LASTEXITCODE)"
}
Write-Host '[3/3] 完成' -ForegroundColor Green
