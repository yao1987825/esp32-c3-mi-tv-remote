"""BleMiRemote component."""

from __future__ import annotations

from typing import Final

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome import automation
from esphome.automation import maybe_simple_id
from esphome.components import binary_sensor, button, number
from esphome.const import (
    CONF_BATTERY_LEVEL,
    CONF_CODE,
    CONF_ID,
    CONF_MANUFACTURER_ID,
    CONF_NAME,
    CONF_VALUE,
    CONF_ICON,
    CONF_DISABLED_BY_DEFAULT,
    CONF_RESTORE_MODE    
)
from esphome.components.esp32 import add_idf_component, add_idf_sdkconfig_option
from esphome.core import CORE, ID
from esphome.cpp_generator import MockObj, TemplateArguments

from .const import (
    ACTION_COMBINATION_CLASS,
    ACTION_CONNECT_WAKE_CLASS,
    ACTION_PLAIN_ADVERT_CLASS,
    ACTION_POWER_WAKE_CLASS,
    ACTION_RECONNECT_ADVERT_CLASS,
    ACTION_PRESS_CLASS,
    ACTION_PRINT_CLASS,
    ACTION_RELEASE_CLASS,
    ACTION_SNIFF_CLASS,
    ACTION_START_CLASS,
    ACTION_STOP_CLASS,
    BINARY_SENSOR_STATE,
    SPECIAL_KEY,
    COMPONENT_BUTTON_CLASS,
    COMPONENT_CLASS,
    CONF_BLE_NAME,
    CONF_ADVERT_STYLE,
    CONF_BUTTONS,
    CONF_OWN_MAC,
    CONF_OWN_ADDR_RANDOM,
    CONF_TARGET_MAC_ADDRESS,
    CONF_WAKE_ON_PRESS,
    CONF_WAKE_KEYS,
    CONF_DIRECTED,
    CONF_HOLD_MS,
    CONF_NAMED,
    CONF_RECONNECT,
    CONF_SECONDS,
    CONF_STYLE,
    CONF_TEXT,
    CONF_WITH_TIMER,
    DOMAIN,
    NIMBLE_CPP_COMPONENT,
    NIMBLE_CPP_COMPONENT_REF,
    NIMBLE_CPP_COMPONENT_REPO,
)

CODEOWNERS: Final = ["@shammysha"]
AUTO_LOAD: Final = ["binary_sensor", "button"]


def validate_buttons(value):
    """`buttons:` 白名单 -> SPECIAL_KEY 里的条目列表。

    2026-11-25: 这个选项只控制**哪些按键会变成 button 实体**（也就是 HA 里
    能看到的那些）。组件的能力一点没少：没列出来的按键照样能用
    `ble_mi_remote.press: code: "Back"` 这种 action 发出去。
    """
    keys = [_lookup_key(name) for name in cv.ensure_list(cv.string)(value)]
    return keys


def validate_wake_keys(value):
    """`wake_keys:` -> 位掩码（bit N = special key N）。

    0 = 不限制（任意键都能唤醒）。见 const.py 里 CONF_WAKE_KEYS 的说明。
    """
    mask = 0
    for name in cv.ensure_list(cv.string)(value):
        key = _lookup_key(name)
        mask |= 1 << key[CONF_VALUE]
    return mask


def _lookup_key(name: str) -> dict:
    """按键名（大小写不敏感）-> SPECIAL_KEY 里的条目。"""
    known = {k[CONF_NAME].lower(): k for k in SPECIAL_KEY}
    key = known.get(name.lower())
    if key is None:
        raise cv.Invalid(
            f"未知的按键 '{name}'。可用: {', '.join(k[CONF_NAME] for k in SPECIAL_KEY)}"
        )
    return key

ble_mi_remote_ns = cg.esphome_ns.namespace(DOMAIN)

BleMiRemote = ble_mi_remote_ns.class_(COMPONENT_CLASS, cg.PollingComponent)
BleMiRemoteButton = ble_mi_remote_ns.class_(COMPONENT_BUTTON_CLASS, cg.Component)

CONFIG_SCHEMA: Final = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(BleMiRemote),
        cv.Optional(CONF_NAME, default=COMPONENT_CLASS): cv.Length(min=1),
        cv.Optional(CONF_MANUFACTURER_ID, default=COMPONENT_CLASS): cv.Length(min=1),
        cv.Optional(CONF_BATTERY_LEVEL, default=100): cv.int_range(min=0, max=100),
        cv.Optional(CONF_RECONNECT, default=True): cv.boolean,
        # BLE advertised name; falls back to CONF_NAME when left empty.
        # Keep it ASCII - the name is truncated to 15 bytes.
        cv.Optional(CONF_BLE_NAME, default=""): cv.string,
        # Optional BLE address override (e.g. "D4:B8:FF:7D:AD:6D") to
        # impersonate the original remote. Empty = use the chip's own MAC.
        cv.Optional(CONF_OWN_MAC, default=""): cv.string,
        # 2026-11-23: use the chip MAC as a RANDOM STATIC address instead of
        # the chip's public address. The original Xiaomi remote uses a random
        # static address; a TV in standby may only act on that kind of
        # address. Changing it invalidates the bond - pair again afterwards.
        cv.Optional(CONF_OWN_ADDR_RANDOM, default=False): cv.boolean,
        # 2026-11-23: the TV's BLE address. The wake packet's 0xFE field
        # carries the end of the TV's OWN address, so the board needs it even
        # before it has ever been paired.
        cv.Optional(CONF_TARGET_MAC_ADDRESS, default=""): cv.string,
        # 2026-11-23 「求同」：默认广播包的风格。
        #   "mi_idle"   = 常态包（**不含 0xFE**）—— 默认值，纯遥控器用这个。
        #                 电视在待机时不会因为我们广播而醒来。
        #   "mi_wake"   = 原装遥控器的 31 字节唤醒包（含 0xFE：电视自己地址的
        #                 后 3 字节）。⚠ 拿它当**常态**广播包的话，电视每收到
        #                 一帧都在被点名，会自己开机。
        #   "mi_orig"   = 同上结构但用我们自己的名字，且不含 0xFE 字段
        #   "mi_rc"     = 逐字节复刻原装遥控器（Flags 0x05 + "MI RC" +
        #                 UUID 0x1812 + TX Power 0x00 + 厂商数据 00 01）
        #   "mi_remote" = 原默认（Appearance + 小米 0x0046 厂商数据）
        cv.Optional(CONF_ADVERT_STYLE, default="mi_idle"): cv.one_of(
            "mi_idle", "mi_wake", "mi_orig", "mi_rc", "mi_remote"
        ),
        # 2026-11-24: 按一次键要不要顺便发唤醒广播（带 0xFE 的那个包）。
        # 默认 False = 板子只当纯遥控器：按键不会唤醒电视，开机由用户自己用
        # 原装遥控器搞定。True = 旧行为。
        cv.Optional(CONF_WAKE_ON_PRESS, default=False): cv.boolean,
        # 2026-11-25: 只把这些按键做成 button 实体（不写 = 全部）。
        # 见 const.py 里 CONF_BUTTONS 的说明。
        cv.Optional(CONF_BUTTONS): validate_buttons,
        # 2026-11-25: 待机时哪些键允许唤醒电视（不写 = 任意键）。
        # 见 const.py 里 CONF_WAKE_KEYS 的说明。
        cv.Optional(CONF_WAKE_KEYS): validate_wake_keys,
    }
)


async def to_code(config: dict) -> None:
    """Generate component

    :param config: dict
    """

    if not CORE.is_esp32:
        raise cv.Invalid("The component only supports ESP32.")

    # The old prebuilt Arduino core (used when this component was originally
    # written) had BT baked in by default - these have to be enabled
    # explicitly now, same as ESPHome's own esp32_ble component does, for
    # the bt/nimble component to be part of the build at all.
    add_idf_sdkconfig_option("CONFIG_BT_ENABLED", True)
    add_idf_sdkconfig_option("CONFIG_BT_NIMBLE_ENABLED", True)
    # own-commits bisection stage 1/5: sdkconfig only, no code changes yet.
    add_idf_sdkconfig_option("CONFIG_BT_NIMBLE_ROLE_CENTRAL", True)
    add_idf_sdkconfig_option("CONFIG_BT_NIMBLE_NVS_PERSIST", True)

    var = cg.new_Pvariable(
        config[CONF_ID],
        config[CONF_NAME],
        config[CONF_MANUFACTURER_ID],
        config[CONF_BATTERY_LEVEL],
        config[CONF_RECONNECT],
        config[CONF_BLE_NAME],
        config[CONF_OWN_MAC],
        config[CONF_ADVERT_STYLE]
    )

    await cg.register_component(var, config)

    # 2026-11-23: give the board its own random static BLE address.
    if config[CONF_OWN_ADDR_RANDOM]:
        cg.add(var.set_own_addr_random(True))

    # 2026-11-23: pin the TV's BLE address (needed for the wake field).
    if config[CONF_TARGET_MAC_ADDRESS]:
        cg.add(var.set_target_mac_address(config[CONF_TARGET_MAC_ADDRESS]))

    # 2026-11-24: should a key press also send the wake advertisement?
    # Default False - the board is a plain remote, it never wakes the TV.
    cg.add(var.set_wake_on_press(config[CONF_WAKE_ON_PRESS]))

    # 2026-11-25: which keys are allowed to wake the TV while it is in
    # standby. 0 = no restriction (any key wakes it - the old behaviour).
    if CONF_WAKE_KEYS in config:
        cg.add(var.set_wake_keys(config[CONF_WAKE_KEYS]))

    await adding_binary_sensors(var)

    await adding_special_keys(var, config.get(CONF_BUTTONS))

    add_idf_component(
        name=NIMBLE_CPP_COMPONENT,
        repo=NIMBLE_CPP_COMPONENT_REPO,
        ref=NIMBLE_CPP_COMPONENT_REF,
    )


async def adding_special_keys(var: MockObj, buttons=None) -> None:
    """Adding buttons

    :param var: MockObj
    :param buttons: 2026-11-25 - 白名单（`buttons:` 配置项）。
        None = 全部按键都做成实体（老行为）；给了列表 = 只有列表里的那些。
        注意这只影响**实体**，不影响按键本身能不能发出去 ——
        其余按键照样能用 `ble_mi_remote.press: code: "..."` 这个 action。
    """

    keys = SPECIAL_KEY if buttons is None else buttons

    for key in keys:
        new_key: MockObj = await button.new_button(
            {
                CONF_ID: cv.declare_id(BleMiRemoteButton)(key[CONF_ID]),
                CONF_NAME: DOMAIN.replace("_", "-") + "-" + key[CONF_NAME],
                CONF_ICON: key[CONF_ICON],
                CONF_DISABLED_BY_DEFAULT: False
            }        
        )
        cg.add(new_key.set_parent(var))

        if CONF_VALUE not in key:
            continue

        cg.add(new_key.set_value(key[CONF_VALUE]))


async def adding_binary_sensors(var: MockObj) -> None:
    """Adding binary sensor

    :param var: MockObj
    """

    cg.add(
        var.set_state_sensor(await binary_sensor.new_binary_sensor(BINARY_SENSOR_STATE))
    )


OPERATION_BASE_SCHEMA: Final = cv.Schema(
    {
        cv.Required(CONF_ID): cv.use_id(BleMiRemote),
    }
)

BleMiRemoteReleaseAction = ble_mi_remote_ns.class_(
    ACTION_RELEASE_CLASS, automation.Action
)


@automation.register_action(
    f"{DOMAIN}.release",
    BleMiRemoteReleaseAction,
    maybe_simple_id(OPERATION_BASE_SCHEMA),
    synchronous=True,
)
async def ble_mi_remote_release_to_code(
    config: dict, action_id: ID, template_arg: TemplateArguments, args: list
) -> MockObj:
    """Action release

    :param config: dict
    :param action_id: ID
    :param template_arg: TemplateArguments
    :param args: list
    :return: MockObj
    """

    paren: MockObj = await cg.get_variable(config[CONF_ID])

    return cg.new_Pvariable(action_id, template_arg, paren)


BleMiRemotePressAction = ble_mi_remote_ns.class_(ACTION_PRESS_CLASS, automation.Action)


@automation.register_action(
    f"{DOMAIN}.press",
    BleMiRemotePressAction,
    OPERATION_BASE_SCHEMA.extend(
        {
            cv.Required(CONF_CODE): cv.Any(
                cv.templatable(cv.uint8_t),
                cv.templatable(cv.string)
            ),
            # with_timer=False keeps the key held down instead of arming the
            # auto-release timer, so a following ble_mi_remote.release action
            # decides when the key comes up. That is what makes a real HID
            # long-press possible (the TV's long-press power to shut down).
            # Default True keeps the original press-and-auto-release behaviour.
            cv.Optional(CONF_WITH_TIMER, default=True): cv.boolean,
        }
    ),
    synchronous=True,
)

async def ble_mi_remote_press_to_code(
    config: dict, action_id: ID, template_arg: TemplateArguments, args: list
) -> MockObj:
    """Action press

    :param config: dict
    :param action_id: ID
    :param template_arg: TemplateArguments
    :param args: list
    :return: MockObj
    """

    paren: MockObj = await cg.get_variable(config[CONF_ID])
    var: MockObj = cg.new_Pvariable(action_id, template_arg, paren)

    is_number = True;

    try:
        config[CONF_CODE] = int(config[CONF_CODE])
    except:
        try:
            config[CONF_CODE] = int(config[CONF_CODE], 16)
        except:
            is_number = False

    # set_key()/set_special() are both TEMPLATABLE_VALUE(uint8_t, ...) - current
    # ESPHome's TemplatableFn requires every value passed to one, literal or not,
    # to go through cg.templatable() typed to match (uint8_t here, not the
    # cg.std_string this used to be called with once up front - that only ever
    # worked by accident, per the TemplatableFn migration notes).
    if is_number:
        cg.add(var.set_key(await cg.templatable(config[CONF_CODE], args, cg.uint8)))
        cg.add(var.set_use_special(False))
    else:
        template_ = config[CONF_CODE].lower()
        for i, k in enumerate(SPECIAL_KEY):
            if k[CONF_NAME].lower() == template_:
                cg.add(var.set_special(await cg.templatable(k[CONF_VALUE], args, cg.uint8)))
                # 2026-11-23: say EXPLICITLY that this is a special key - the
                # action can no longer tell from TemplatableValue::has_value()
                # whether a value was set at all.
                cg.add(var.set_use_special(True))
                break
    cg.add(var.set_with_timer(config[CONF_WITH_TIMER]))
    return var


BleMiRemoteConnectWakeAction = ble_mi_remote_ns.class_(ACTION_CONNECT_WAKE_CLASS, automation.Action)


@automation.register_action(
    f"{DOMAIN}.connect_wake",
    BleMiRemoteConnectWakeAction,
    OPERATION_BASE_SCHEMA.extend(
        {
            # How long to keep the link to the powered-off TV open.
            cv.Optional(CONF_HOLD_MS, default=12000): cv.int_range(min=0, max=60000),
        }
    ),
    synchronous=True,
)
async def ble_mi_remote_connect_wake_to_code(
    config: dict, action_id: ID, template_arg: TemplateArguments, args: list
) -> MockObj:
    """Action connect_wake

    :param config: dict
    :param action_id: ID
    :param template_arg: TemplateArguments
    :param args: list
    :return: MockObj
    """

    paren: MockObj = await cg.get_variable(config[CONF_ID])
    var: MockObj = cg.new_Pvariable(action_id, template_arg, paren)

    cg.add(var.set_hold_ms(config[CONF_HOLD_MS]))
    return var


BleMiRemotePlainAdvertAction = ble_mi_remote_ns.class_(ACTION_PLAIN_ADVERT_CLASS, automation.Action)


BleMiRemotePowerWakeAction = ble_mi_remote_ns.class_(ACTION_POWER_WAKE_CLASS, automation.Action)


BleMiRemoteReconnectAdvertAction = ble_mi_remote_ns.class_(
    ACTION_RECONNECT_ADVERT_CLASS, automation.Action
)


BleMiRemoteSniffAction = ble_mi_remote_ns.class_(ACTION_SNIFF_CLASS, automation.Action)


@automation.register_action(
    f"{DOMAIN}.sniff",
    BleMiRemoteSniffAction,
    OPERATION_BASE_SCHEMA.extend(
        {
            cv.Optional(CONF_SECONDS, default=30): cv.int_range(min=1, max=300),
        }
    ),
    synchronous=True,
)
async def ble_mi_remote_sniff_to_code(
    config: dict, action_id: ID, template_arg: TemplateArguments, args: list
) -> MockObj:
    """Action sniff - listen to every BLE advertisement and dump the bytes.

    :param config: dict
    :param action_id: ID
    :param template_arg: TemplateArguments
    :param args: list
    :return: MockObj
    """

    paren: MockObj = await cg.get_variable(config[CONF_ID])
    var: MockObj = cg.new_Pvariable(action_id, template_arg, paren)

    cg.add(var.set_seconds(config[CONF_SECONDS]))
    return var


@automation.register_action(
    f"{DOMAIN}.reconnect_advert",
    BleMiRemoteReconnectAdvertAction,
    maybe_simple_id(OPERATION_BASE_SCHEMA),
    synchronous=True,
)
async def ble_mi_remote_reconnect_advert_to_code(
    config: dict, action_id: ID, template_arg: TemplateArguments, args: list
) -> MockObj:
    """Action reconnect_advert - plain undirected advertising, bond kept.

    :param config: dict
    :param action_id: ID
    :param template_arg: TemplateArguments
    :param args: list
    :return: MockObj
    """

    paren: MockObj = await cg.get_variable(config[CONF_ID])

    return cg.new_Pvariable(action_id, template_arg, paren)


@automation.register_action(
    f"{DOMAIN}.power_wake",
    BleMiRemotePowerWakeAction,
    OPERATION_BASE_SCHEMA.extend(
        {
            # Undirected = the classic MiPower broadcast every device hears.
            # Directed = addressed to the bonded TV, for firmware that only
            # wakes for a remote it already has a bond with.
            cv.Optional(CONF_DIRECTED, default=False): cv.boolean,
            # Also put the device name into the advertising packet.
            cv.Optional(CONF_NAMED, default=False): cv.boolean,
            # Which wake-broadcast flavour: mipower / mi_rc / mi_rc_own /
            # mi_orig / mi_wake. "mi_wake" is the default: the original
            # remote's 31-byte packet including the 0xFE field with the end
            # of the TV's own address - the only one this TV answers to.
            cv.Optional(CONF_STYLE, default="mi_wake"): cv.one_of(
                "mipower", "mi_rc", "mi_rc_own", "mi_orig", "mi_wake", lower=True
            ),
        }
    ),
    synchronous=True,
)
async def ble_mi_remote_power_wake_to_code(
    config: dict, action_id: ID, template_arg: TemplateArguments, args: list
) -> MockObj:
    """Action power_wake - send the Xiaomi wake broadcast.

    :param config: dict
    :param action_id: ID
    :param template_arg: TemplateArguments
    :param args: list
    :return: MockObj
    """

    paren: MockObj = await cg.get_variable(config[CONF_ID])
    var: MockObj = cg.new_Pvariable(action_id, template_arg, paren)

    cg.add(var.set_directed(config[CONF_DIRECTED]))
    cg.add(var.set_named(config[CONF_NAMED]))
    cg.add(var.set_style(config[CONF_STYLE]))
    return var


@automation.register_action(
    f"{DOMAIN}.plain_advert",
    BleMiRemotePlainAdvertAction,
    maybe_simple_id(OPERATION_BASE_SCHEMA),
    synchronous=True,
)
async def ble_mi_remote_plain_advert_to_code(
    config: dict, action_id: ID, template_arg: TemplateArguments, args: list
) -> MockObj:
    """Action plain_advert

    :param config: dict
    :param action_id: ID
    :param template_arg: TemplateArguments
    :param args: list
    :return: MockObj
    """

    paren: MockObj = await cg.get_variable(config[CONF_ID])

    return cg.new_Pvariable(action_id, template_arg, paren)


BleMiRemoteStartAction = ble_mi_remote_ns.class_(ACTION_START_CLASS, automation.Action)


@automation.register_action(
    f"{DOMAIN}.start",
    BleMiRemoteStartAction,
    maybe_simple_id(OPERATION_BASE_SCHEMA),
    synchronous=True,
)
async def ble_mi_remote_start_to_code(
    config: dict, action_id: ID, template_arg: TemplateArguments, args: list
) -> MockObj:
    """Action start

    :param config: dict
    :param action_id: ID
    :param template_arg: TemplateArguments
    :param args: list
    :return: MockObj
    """

    paren: MockObj = await cg.get_variable(config[CONF_ID])

    return cg.new_Pvariable(action_id, template_arg, paren)


BleMiRemoteStopAction = ble_mi_remote_ns.class_(ACTION_STOP_CLASS, automation.Action)


@automation.register_action(
    f"{DOMAIN}.stop",
    BleMiRemoteStopAction,
    maybe_simple_id(OPERATION_BASE_SCHEMA),
    synchronous=True,
)
async def ble_mi_remote_stop_to_code(
    config: dict, action_id: ID, template_arg: TemplateArguments, args: list
) -> MockObj:
    """Action stop

    :param config: dict
    :param action_id: ID
    :param template_arg: TemplateArguments
    :param args: list
    :return: MockObj
    """

    paren: MockObj = await cg.get_variable(config[CONF_ID])

    return cg.new_Pvariable(action_id, template_arg, paren)
