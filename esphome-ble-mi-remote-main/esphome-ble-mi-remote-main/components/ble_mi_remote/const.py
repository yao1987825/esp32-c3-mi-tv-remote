"""BleMiRemote component const."""

# pylint: disable=line-too-long

from __future__ import annotations

from typing import Final

import esphome.config_validation as cv
from esphome.components import binary_sensor
from esphome.components.number import NumberMode
from esphome.const import (
    CONF_DEVICE_CLASS,
    CONF_DISABLED_BY_DEFAULT,
    CONF_ENTITY_CATEGORY,
    CONF_ICON,
    CONF_ID,
    CONF_INITIAL_VALUE,
    CONF_MAX_VALUE,
    CONF_MIN_VALUE,
    CONF_MODE,
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_RESTORE_VALUE,
    CONF_STEP,
    CONF_TYPE,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE,
    DEVICE_CLASS_CONNECTIVITY,
    ENTITY_CATEGORY_CONFIG,
    UNIT_MILLISECOND,
    UNIT_PERCENT,
)

DOMAIN: Final = "ble_mi_remote"

CONF_TEXT: Final = "text"
CONF_KEYS: Final = "keys"
CONF_RECONNECT: Final = "reconnect"
CONF_WITH_TIMER: Final = "with_timer"
# The BLE advertised device name, kept separate from the ESPHome entity name.
# The name is truncated to 15 BYTES, so a Chinese name gets cut mid-character
# and the TV shows garbage. Keep this one ASCII.
CONF_BLE_NAME: Final = "ble_name"
CONF_BUTTONS: Final = "buttons"
# 2026-11-25: `buttons:` 白名单 —— 只把列出来的按键做成 button 实体。
#
# 不写 = 全部按键都做成实体（向后兼容的老行为）。
# 写了 = 只有列出来的那些会出现在 HA 里，组件本身的能力一点不少：
# 其余按键照样能用 `ble_mi_remote.press: code: "..."` 这个 action 发出去。
#
# 用法:
#     ble_mi_remote:
#       buttons:
#         - Enter        # 确认
#         - Up
#         - Down
#         - Left
#         - Right
#         - Power
#         - Volume Up
#         - Volume Down

CONF_USE_DEFAULT_LIBS: Final = "use_default_libs"
# Optional: override the board's BLE address to impersonate the original
# Xiaomi remote (e.g. "D4:B8:FF:7D:AD:6D"). Empty = use the chip's own MAC.
# Some TVs only wake for the bonded remote's ADDRESS, not the packet content.
CONF_OWN_MAC: Final = "own_mac"

# 2026-11-23：把板子自己的芯片 MAC 改成 **random static** 地址
# （最高两位强制为 11），而不是芯片默认的 public 地址。
# 原装小米遥控器用的是 random static 地址（D4:B8:FF:7D:AD:6D）；
# 待机中的电视在筛选它接受的广播时，public 地址和 random static
# 地址很可能不是同一类。
# 注意：改了身份地址 = bond 作废，之后必须重新配对一次。
CONF_OWN_ADDR_RANDOM: Final = "own_addr_random"

# 2026-11-23：把电视的蓝牙地址写死在配置里。
# 唤醒包的 0xFE 字段装着**电视自己地址的后 3 字节**，所以板子必须知道这个
# 地址 —— 刚刷完固件、还没配对过时尤其重要。
CONF_TARGET_MAC_ADDRESS: Final = "target_mac_address"

# 2026-11-24：按一次键要不要顺便发**唤醒广播**（带 0xFE 字段的那个包）。
#
# 默认 False —— 板子只当一个纯遥控器：
#   · 亮屏时按电源 → 电视进关屏待机
#   · 待机时按任何键 → 什么也不会发生（电视不会被我们唤醒）
# 开机由用户自己用原装遥控器搞定。
#
# True = 旧行为：按键时额外发 30 秒唤醒包，电视在待机时会被我们唤醒。
# ⚠ 注意：0xFE 字段里装着电视自己的地址，是一封「点名信」。
#    常发 = 电视每收到一帧都被点名 = 没人按遥控器它也会自己开机。
CONF_WAKE_ON_PRESS: Final = "wake_on_press"

# 2026-11-25: 待机时**哪些键**允许把电视唤醒。
#
# 写了这个 = 只有列出来的键在电视待机时会发唤醒广播（带 0xFE 那个包），
# 其余键在待机时**什么都不做**（不唤醒、也不排队补发）。
# 不写 = 任意键都能唤醒（老行为，和原装遥控器一样）。
#
# 用法:
#     ble_mi_remote:
#       wake_keys:
#         - Power          # 只有电源键能开机
CONF_WAKE_KEYS: Final = "wake_keys"

# 2026-11-23 「求同」模式：让板子**平时**的广播包就等于原装遥控器。
#   "mi_wake"  - 原装遥控器真正在发的那个 **31 字节唤醒包**：
#                  02 01 05              Flags
#                  03 FF 00 01           厂商数据 company 0x0000
#                  06 08 "MI RC"         短名
#                  03 02 12 18           UUID 0x1812 (HID)
#                  04 0D 04 05 00        设备类别字段
#                  02 0A 00              TX power 0 dBm
#                  04 FE <tv尾3字节>     小米唤醒字段：电视自己地址的后 3 字节
#                ★ 最后那个 0xFE 字段是关键：电视在里面看到自己的地址，
#                就知道「这条广播是发给我的」，于是醒来。
#                我们之前一直没发现它，是因为自己的嗅探器只打印固定几种
#                AD type，0x0D 和 0xFE 根本不在那张表里。
#   "mi_orig"  - 同上结构、但用我们自己的名字，且不含 0xFE 字段
#   "mi_rc"    - 完全复刻原装小米蓝牙遥控器的广播：
#             Flags 0x05 | UUID 0x1812 | ShortName "MI RC" | Name "MI RC"
#             | TX Power 0x00 | Manufacturer Data 00 01
#             电视在配对阶段看到的必须和原装一模一样，否则会连上又踢开。
#   "mi_remote" - 原来的默认（Flags 0x06 + Appearance + 名字 + 小米 0x0046 厂商数据）
CONF_ADVERT_STYLE: Final = "advert_style"

COMPONENT_CLASS: Final = "BleMiRemote"
COMPONENT_NUMBER_CLASS: Final = "BleMiRemoteNumber"
COMPONENT_BUTTON_CLASS: Final = "BleMiRemoteButton"

ACTION_START_CLASS: Final = "BleMiRemoteStartAction"
ACTION_STOP_CLASS: Final = "BleMiRemoteStopAction"
ACTION_PRINT_CLASS: Final = "BleMiRemotePrintAction"
ACTION_PRESS_CLASS: Final = "BleMiRemotePressAction"
ACTION_RELEASE_CLASS: Final = "BleMiRemoteReleaseAction"
ACTION_COMBINATION_CLASS: Final = "BleMiRemoteCombinationAction"
ACTION_CONNECT_WAKE_CLASS: Final = "BleMiRemoteConnectWakeAction"
ACTION_PLAIN_ADVERT_CLASS: Final = "BleMiRemotePlainAdvertAction"
ACTION_POWER_WAKE_CLASS: Final = "BleMiRemotePowerWakeAction"
ACTION_RECONNECT_ADVERT_CLASS: Final = "BleMiRemoteReconnectAdvertAction"
ACTION_SNIFF_CLASS: Final = "BleMiRemoteSniffAction"
# BLE sniffer: how long to listen to every advertisement in the air.
CONF_SECONDS: Final = "seconds"
# How long (ms) connect_wake keeps the link to the powered-off TV open.
# The TV's BLE host needs the connection to stay up to notice it and boot.
CONF_HOLD_MS: Final = "hold_ms"
# Send the wake broadcast as a DIRECTED advert to the bonded TV instead of an
# undirected one. Some TV firmware only reacts to a remote it has a bond with.
CONF_DIRECTED: Final = "directed"
# Also put the device name into the wake advertising packet. The classic
# MiPower packet is anonymous; a TV that matches its bonded remote by name
# needs the name to be in the packet.
CONF_NAMED: Final = "named"
# Which wake-broadcast flavour to send:
#   "mipower"   - classic Mi BOX packet (company id 0x0046 + 18 bytes)
#   "mi_rc"     - byte-for-byte the packet the ORIGINAL Xiaomi remote sends
#                 (captured 2026-11-23 with the board's own BLE sniffer)
#   "mi_rc_own" - same, but with our own device name
#   "mi_orig"   - the original's packet with OUR name in the complete local
#                 name field and the company-id-0x0000 manufacturer data
#   "mi_wake"   - the original's 31-byte packet INCLUDING the 0xFE field
#                 that carries the end of the TV's own address - the default,
#                 because this is the packet that wakes the TV up
CONF_STYLE: Final = "style"

"""NimBLE C++ wrapper library.

Original 2023 code pulled h2zero/NimBLE-Arduino 1.4.0 via the Arduino/
PlatformIO lib_deps mechanism (see git history). Current ESPHome's Arduino
framework builds that same library as an ESP-IDF component instead, and hit
real upstream ESP-IDF-5.5.5-compatibility gaps in NimBLE-Arduino's own
porting layer unrelated to this component's code. Pinning our own fork of
h2zero/esp-nimble-cpp (the ESP-IDF-native sibling library, same vintage) at
its last pre-2.x tag instead avoids that path entirely while keeping the
exact same NimBLE host generation the original code was written against -
esp-nimble-cpp had no tagged release between v1.4.1 (2022-10-30) and 2.0.0
(2024-12-14), so v1.4.1 is the version genuinely contemporary with this
component's original commit (2023-07-19).
"""
NIMBLE_CPP_COMPONENT: Final = "h2zero/esp-nimble-cpp"
NIMBLE_CPP_COMPONENT_REPO: Final = "https://github.com/shammysha/esp-nimble-cpp"
# BISECTION BUILD (nimble-cpp-bisect branch, not the reference - see
# mi-tv-nimble140-work). Pinned to a plain upstream tag pushed to our fork,
# advanced one step at a time toward current master to find which release
# introduced the real-Mi-TV ~18.5-20.5s post-bond disconnect. Change only
# this one line between rounds.
NIMBLE_CPP_COMPONENT_REF: Final = "ble-mi-remote-hd-directed"

"""Binary sensors"""
BINARY_SENSOR_STATE: Final = {
    CONF_ID: cv.declare_id(binary_sensor.BinarySensor)("connected"),
    CONF_NAME: "Connected",
    CONF_DEVICE_CLASS: DEVICE_CLASS_CONNECTIVITY,
    CONF_DISABLED_BY_DEFAULT: False
}

"""Special buttons"""
SPECIAL_KEY: Final = [
    {
        CONF_NAME: "Enter",
        CONF_ID: "key_enter",
        CONF_ICON: "mdi:play",
        CONF_VALUE: 0
    },{   
        CONF_NAME: "Up",
        CONF_ID: "key_up",
        CONF_ICON: "mdi:arrow-up-drop-circle-outline",
        CONF_VALUE: 1
  
    },{
        CONF_NAME: "Down",
        CONF_ID: "key_down",
        CONF_ICON: "mdi:arrow-down-drop-circle-outline",
        CONF_VALUE: 2
    },{
        CONF_NAME: "Left",
        CONF_ID: "key_left",
        CONF_ICON: "mdi:arrow-left-drop-circle-outline",
        CONF_VALUE: 3
    },{
        CONF_NAME: "Right",
        CONF_ID: "key_right",
        CONF_ICON: "mdi:arrow-right-drop-circle-outline",
        CONF_VALUE: 4
    },{        
        CONF_NAME: "Power",
        CONF_ID: "key_power",
        CONF_ICON: "mdi:power-cycle",
        CONF_VALUE: 5
    },{
        # 2026-11-25: 「Voice」(6) 已删除 —— 板子上没有麦克风，这个键在电视上
        # 只会弹「找不到语音输入」的提示，纯属噪音。
        # ★ 删掉条目之后，其余键的 CONF_VALUE **一律不能重编号** ★
        #   CONF_VALUE 就是报告描述符里消费页位图的位号，重编号会让所有键
        #   发错 usage。
        CONF_NAME: "Volume Up",
        CONF_ID: "key_volumeup",
        CONF_ICON: "mdi:volume-plus",
        CONF_VALUE: 7
    },{
        CONF_NAME: "Volume Down",
        CONF_ID: "key_volumedown",
        CONF_ICON: "mdi:volume-minus",
        CONF_VALUE: 8
    },{
        CONF_NAME: "Select",
        CONF_ID: "key_select",
        CONF_ICON: "mdi:form-select",
        CONF_VALUE: 9
    },{
        CONF_NAME: "Movie",
        CONF_ID: "key_movie",
        CONF_ICON: "mdi:multimedia",
        CONF_VALUE: 10
    },{
        CONF_NAME: "Green",
        CONF_ID: "key_green",
        CONF_ICON: "mdi:radiobox-marked",
        CONF_VALUE: 11
    },{
        CONF_NAME: "Blue",
        CONF_ID: "key_blue",
        CONF_ICON: "mdz:radiobox-marked",
        CONF_VALUE: 12
    },{
        CONF_NAME: "MI HOME",
        CONF_ID: "key_mihome",
        CONF_ICON: "mdi:alpha-m-circle-outline",
        CONF_VALUE: 13
    },{
        CONF_NAME: "Email",
        CONF_ID: "key_email",
        CONF_ICON: "mdi:radiobox-marked",
        CONF_VALUE: 14
    },{
        CONF_NAME: "Calculator",
        CONF_ID: "key_calculator",
        CONF_ICON: "mdi:calculator",
        CONF_VALUE: 15
    },{
        CONF_NAME: "Files",
        CONF_ID: "key_files",
        CONF_ICON: "mdi:folder-file-outline",
        CONF_VALUE: 16
    },{
        # 2026-11-25: 「Voice2」(17) 也删了 —— 它和 Voice 用的是同一个
        # 消费页 usage (0xCF)，本来就是重复键，同样没有麦克风。
        CONF_NAME: "Android TV",
        CONF_ID: "key_androidtv",
        CONF_ICON: "mdi:android",
        CONF_VALUE: 18
    },{
        CONF_NAME: "Back",
        CONF_ID: "key_back",
        CONF_ICON: "mdi:arrow-left-bold-outline",
        CONF_VALUE: 19
    },{
        CONF_NAME: "Forward",
        CONF_ID: "key_forward",
        CONF_ICON: "mdi:arrow-right-bold-outline",
        CONF_VALUE: 20
    },{
        CONF_NAME: "Stop",
        CONF_ID: "key_stop",
        CONF_ICON: "mdi:stop-circle-outline",
        CONF_VALUE: 21
    },{
        CONF_NAME: "Refresh",
        CONF_ID: "key_refresh",
        CONF_ICON: "mdi:refresh",
        CONF_VALUE: 22
    },{
        CONF_NAME: "Bookmarks",
        CONF_ID: "key_bookmarks",
        CONF_ICON: "mdi:bookmark-box-outline",
        CONF_VALUE: 23
    }
]

