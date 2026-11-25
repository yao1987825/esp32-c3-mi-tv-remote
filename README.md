# ESP32-C3 小米电视蓝牙遥控器

用一块 **ESP32-C3 SuperMini** 伪装成小米电视的**蓝牙 HID 遥控器**，
不但能按键，还能在电视待机时**把它唤醒**。

实测机型：**小米 MiTV4-ANSM0**（Android 6.0.1）。
固件用 ESPHome 写，Home Assistant 原生 API 接入，HA 面板上直接就是遥控器。

```
┌─────────────────┐
│      电源        │
│        ↑        │
│   ←   确认   →   │
│        ↓        │
│      返回        │
│   音量 −   音量 + │
└─────────────────┘
```

---

## 这个项目解决了什么

小米电视的遥控器本身就是蓝牙 HID 设备（电视上 `dumpsys input` 显示
「小米蓝牙语音遥控器」，`bus=0x0005` = `BUS_BLUETOOTH`）。
所以只要让板子伪装成一个**配对过的 HID 外设**，电视就会认它。

但「能按键」和「能把睡着的电视叫醒」是两回事，后者才是难的地方。

### 唤醒原理（一句话）

原装遥控器按电源键时，广播包里有一个 **AD 字段 `0xFE`**，装着**电视自己
蓝牙地址的后 3 字节（逆序）**。待机的电视扫到自己的地址，就知道「这条是
发给我的」，于是醒来并主动连回遥控器。

板子照抄这个包就行 —— 31 字节，逐字节对齐：

```
02 01 05              Flags
03 FF 00 01           Manufacturer data, company 0x0000
06 08 "MI RC"         短名
03 02 12 18           UUID 0x1812 (HID)
04 0D 04 05 00        设备类别
02 0A 00              TX power 0 dBm
04 FE AA 77 62        ★ 电视自己地址的尾 3 字节（0xFE = 小米唤醒字段）
```

**但这个包只能按需发。** 如果把它设成常态广播，电视每收到一帧都被点名，
没人按遥控器它也会自己开机（v1.0.0 踩过这个坑）。

所以组件里有两种广播包：

| 包 | 内容 | 什么时候发 |
|---|---|---|
| **常态包** `mi_idle` | 同结构，**没有 `0xFE` 字段** | 永远在发（电视不会自己醒） |
| **唤醒包** `mi_wake` | 带 `0xFE` 字段 | **只有按键时**发，持续 30 秒 |

---

## 快速开始

### 1. 准备

* 一块 ESP32-C3 SuperMini（ESP32-C3FH4 / 4 MB Flash）
* 一台装了 ESPHome 的电脑
* 电视和小米蓝牙遥控器（用来配对）

### 2. 填凭据

```bash
cd esp32-adb-remote/esphome
cp secrets.yaml.example secrets.yaml
```

编辑 `secrets.yaml`：

| 键 | 说明 |
|---|---|
| `wifi_ssid` / `wifi_password` | 板子要连的 WiFi（**必须和电视同一网段**） |
| `ota_password` / `web_password` | 板子自己的密码，随便起 |
| `api_encryption_key` | HA 原生 API 密钥，生成方式见文件里注释 |

> ⚠ `secrets.yaml` 已经在 `.gitignore` 里，**不会被提交**。
> 仓库里只有 `secrets.yaml.example`。

### 3. 编译烧录

```powershell
cd esp32-adb-remote/esphome
.\build.ps1 -Upload
```

> `build.ps1` 会把工程 stage 到 `C:\esp32c3\esphome` 再编译 ——
> 因为 MinGW 的链接器读不了含中文的路径。板子插在 **COM6**（或用 `-Port COMx` 指定）。

### 4. 配对

1. 电视 **设置 → 蓝牙 → 添加设备**
2. 板子开始广播后，电视上会出现 **「MI Remote」** → 点它
3. 电视屏幕会显示配对码 → 在板子串口日志里找
   ```
   [ble_mi_remote]: Pairing code: 123456
   ```
   输入配对码即可

> ⚠ 广播名**必须**是 `MI Remote`：这台电视的蓝牙列表只显示已缓存过的名字，
> 换名字（比如 `MI RC`）在设置页里根本扫不到。

### 5. 接 Home Assistant

设置 → 设备与服务 → 添加设备 → **ESPHome**

* 主机名：`mi-tv-remote.local` 或板子的 IP
* 端口：`6053`
* 加密密钥：`secrets.yaml` 里 `api_encryption_key` 的值

接上以后，按键会**自动**变成 HA 里的 button 实体。
面板配置见 `esp32-adb-remote/ha-panel-tv-remote.json`
（用 `tools/ha_dashboard.py` 读 / 写）。

---

## 目录结构

```
esp32-adb-remote/
  esphome/
    tv-remote.yaml          ★ 主配置（凭据走 !secret）
    secrets.yaml.example    ★ 凭据模板
    build.ps1               编译烧录脚本（stage 到 C:\esp32c3）
    README.md               烧录 / 配对 / 接 HA 的详细步骤
  release/v1.0.0 ~ v1.2.1/  各版本固件归档（factory.bin / ota.bin）
  正式版发布说明-*.md        每个版本的改动 + 实测日志
  蓝牙待机唤醒-根因与修复_*.md  ★ 唤醒机制的完整排查过程
  ha-panel-tv-remote.json   HA 的「电视遥控」面板配置

esphome-ble-mi-remote-main/  ★ 组件源码（见下方「致谢与来源」）
  components/ble_mi_remote/

tools/                      运维 / 排障脚本（凭据走 credentials.py）
```

---

## 组件新增的两个配置项

上游组件一次把所有按键都做成实体。这里加了开关：

```yaml
ble_mi_remote:
  # 只把这些按键做成 button 实体（HA 里就只看得见它们）
  # 组件本身的能力一点不少 —— 没列出来的键照样能用
  # ble_mi_remote.press: code: "Back" 这个 action 发出去。
  buttons:
    - Enter
    - Up
    - Down
    - Left
    - Right
    - Power
    - Back
    - Volume Up
    - Volume Down

  # 待机时哪些键允许把电视唤醒（不写 = 任意键，原装遥控器的行为）
  wake_keys:
    - Power
```

### 按键是怎么被电视翻译的

电视用 `/system/usr/keylayout/Vendor_2717_Product_32b8.kl` 决定
「Linux keycode → Android keycode」的映射。**这个文件里没有的 keycode 会被
内核静默丢弃** —— 板子日志一切正常，电视却毫无反应。

所以确认键（OK）一开始是坏的：它发的是消费页 usage `0x41`，电视内核认成
`KEY_SELECT`(353)，而 .kl 里没有 353。

原装遥控器的确认键走的是**键盘页 usage `0x28` (Enter)** →
`KEY_ENTER`(28) → .kl 里 `key 28 DPAD_CENTER` → 电视的「确认」键。

组件里 `pressEnter()` 就是干这个的。完整实测见
[正式版发布说明-v1.2.0](esp32-adb-remote/正式版发布说明-v1.2.0_2026-11-25.md)。

---

## ⚠ 这台电视的电源键行为

| 操作 | 电视的反应 | 后果 |
|---|---|---|
| **短按** | 关屏待机 | 还能被 BLE 唤醒，板子照常连得上 |
| **长按** | **彻底关机** | 电视的 BLE 主机也停了 → **任何 BLE 唤醒都唤不醒**（连原装遥控器都不行），只有拔电源才能恢复 |

所以项目里**没有任何长按电源的按钮**。别自己加。

---

## 排障工具

```powershell
# 抓板子串口日志
python tools/capture_boot.py COM6 30
python tools/capture_boot.py COM6 60 --no-reset   # 不复位，只监听

# 触发按键（走板子的 web_server）
python tools/tv_remote.py list
python tools/tv_remote.py "Power"

# 正式版验收：启动日志 + 逐个探测实体
python tools/verify_release.py COM6

# 回归：待机时只有电源键能唤醒电视
python tools/verify_wake_only_power.py

# 回归：电视不会自己醒
python tools/test_no_self_wake.py --minutes 3 --skip-control

# HA 侧：实体改中文显示名 / 改 entity_id / 读写面板
python tools/ha_localize.py --token <TOKEN> apply
python tools/ha_entity_registry.py --token <TOKEN> rename
python tools/ha_dashboard.py --token <TOKEN> show tv-remote
```

所有脚本的凭据都从 `tools/credentials.py` 读
（`cp tools/credentials.example.py tools/credentials.py`），
或者用环境变量 `TV_REMOTE_*`。

### 排查「电视不吃某个键」

1. `adb shell cat /system/usr/keylayout/Vendor_2717_Product_32b8.kl`
   —— 电视认哪些 keycode
2. `adb shell getevent -lt` —— 我们发出的 usage 被认成什么
3. `adb shell cat /sys/class/hidraw/hidraw1/device/report_descriptor`
   —— 原装遥控器发什么（不用 root 就能读）

---

## 致谢与来源

`components/ble_mi_remote/` 派生自
**[shammysha/esphome-ble-mi-remote](https://github.com/shammysha/esphome-ble-mi-remote)**
（原作者未附带 license 文件，本仓库保留其署名与链接，仅供学习研究）。

上游又派生自：
* [dmamontov/esphome-blekeyboard](https://github.com/dmamontov/esphome-blekeyboard)
* [T-vK/ESP32-BLE-Keyboard](https://github.com/T-vK/ESP32-BLE-Keyboard)

本仓库在它之上做了这些改动（细节见各版本的发布说明）：

* 修「待机时唤不醒」：实现 31 字节唤醒包（`0xFE` 字段）
* 修「电视自己开机」：常态包和唤醒包分离
* 修「按了没反应」：修 `isBonded()` 地址类型不匹配、`TEMPLATABLE_VALUE` 取值 bug
* 修「确认键无效」：改走键盘页 usage `0x28`（ENTER）
* 新增 `buttons:` / `wake_keys:` 两个配置项
* 删掉语音键、删掉长按电源（会彻底关机）
* BLE 嗅探器、按键队列、断线重连等一堆排障工具
