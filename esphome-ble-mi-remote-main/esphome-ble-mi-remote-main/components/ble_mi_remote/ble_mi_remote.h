#pragma once

#ifdef USE_ESP32

#include "esphome/core/component.h"
#include "esphome/core/preferences.h"
#include "esphome/components/binary_sensor/binary_sensor.h"
#include "sdkconfig.h"
#include <NimBLEServer.h>
#include "NimBLECharacteristic.h"
#include "NimBLEHIDDevice.h"
// Explicit, not relying on a transitive include (order varies per
// translation unit) - needed for NimBLEAdvertisementData below.
#include "NimBLEAdvertising.h"
// Explicit, not relying on a transitive include (order varies per
// translation unit) - needed for NimBLEAdvertisementData below.
#include "NimBLEScan.h"
#include <string>
#include <vector>
#include <cstring>


const uint8_t SPECIAL_KEYS_COUNT = 24;

// 2026-11-25: HID usage for "Enter" on the Keyboard/Keypad page (0x07).
//
// 这台电视的 keylayout 文件是 /system/usr/keylayout/Vendor_2717_Product_32b8.kl
// （原装遥控器和我们的板子共用同一个）。实测（adb shell getevent -lt）：
//
//   消费页 usage 0x41 (Menu Pick) → Linux KEY_SELECT (353) → .kl 里没有 → 被丢弃
//   键盘页 usage 0x28 (Enter)    → Linux KEY_ENTER  (28)  → .kl: key 28 DPAD_CENTER
//
// 原装遥控器的中间键（确认/播放暂停）走的正是**键盘页 0x28**，所以我们的
// 确认键也必须走键盘报告，消费页那个 0x41 在这台电视上永远没反应。
const uint8_t HID_USAGE_ENTER = 0x28;

const uint8_t SPECIAL_MENU_PICK = 0;
const uint8_t SPECIAL_MENU_UP = 1;
const uint8_t SPECIAL_MENU_DOWN = 2;
const uint8_t SPECIAL_MENU_LEFT = 3;
const uint8_t SPECIAL_MENU_RIGHT = 4;
const uint8_t SPECIAL_POWER = 5;
const uint8_t SPECIAL_VOICE = 6;
const uint8_t SPECIAL_VOLUME_UP = 7;
const uint8_t SPECIAL_VOLUME_DOWN = 8;
const uint8_t SPECIAL_TASK_SELECT = 9;
const uint8_t SPECIAL_MOVIE_BROWSER = 10;
const uint8_t SPECIAL_BUTTON_GREEN = 11;
const uint8_t SPECIAL_BUTTON_BLUE = 12;
const uint8_t SPECIAL_MI_HOME = 13;
const uint8_t SPECIAL_EMAIL_READER = 14;
const uint8_t SPECIAL_CALCULATOR = 15;
const uint8_t SPECIAL_LOCAL_BROWSER = 16;
const uint8_t SPECIAL_VOICE2 = 17;
const uint8_t SPECIAL_ANDROID_HOME = 18;
const uint8_t SPECIAL_BACK = 19;
const uint8_t SPECIAL_FORWARD = 20;
const uint8_t SPECIAL_STOP = 21;
const uint8_t SPECIAL_REFRESH = 22;
const uint8_t SPECIAL_BOOKMARK = 23;

//  Low level key report: up to 6 keys and shift, ctrl etc at once
typedef struct {
  uint8_t modifiers;
  uint8_t reserved;
  uint8_t keys[6];
} KeyReport;

typedef struct {
	uint8_t keys[3];
} SpecialKeyReport;



namespace esphome {
	namespace ble_mi_remote {
		class BleMiRemote : public PollingComponent, public NimBLEServerCallbacks, public NimBLECharacteristicCallbacks, public NimBLEScanCallbacks {
			public:
				BleMiRemote(std::string name, std::string manufacturer_id, uint8_t battery_level = 100, bool reconnect = true,
				            std::string ble_name = "", std::string own_mac = "",
				            std::string advert_style = "mi_remote");

				void setup() override;
				void update() override;

				float get_setup_priority() const override { return setup_priority::AFTER_BLUETOOTH; }

				void set_delay(uint32_t delay_ms = 8) { this->_delay_ms = delay_ms; };
				void set_release_delay(uint32_t delay_ms = 8) { _release_delay = delay_ms; };
				void set_battery_level(uint8_t level = 100);

				void set_state_sensor(binary_sensor::BinarySensor *state_sensor) { state_sensor_ = state_sensor; }

				void press(uint8_t key, bool with_timer = true);
				void pressSpecial(uint8_t key, bool with_timer = true);
				void release();

				// 2026-11-25: the OK / confirm key.
				//
				// It does NOT go through the Consumer Control bitmap (usage
				// 0x41 "Menu Pick"): on this TV that usage is turned into
				// Linux KEY_SELECT (353), and the TV's keylayout file has no
				// entry for 353 - the key is silently dropped and the button
				// does nothing at all.
				//
				// The original Xiaomi remote sends its centre button through
				// the KEYBOARD report with usage 0x28 (Enter), and the TV's
				// keylayout maps KEY_ENTER (28) to DPAD_CENTER - that is the
				// "确认" key, and in the player it is also play/pause.
				//
				// Our report descriptor already declares the same 6-byte
				// keyboard array with usage minimum 0x28, so no descriptor
				// change (and no re-pairing) is needed.
				void pressEnter();

				void start();
				void stop();

				void begin(void);
				void end(void);
				void sendReport(KeyReport* keys);
				void sendReport(SpecialKeyReport* keys);

				// Gap fix, functional (not stage 5): real Component lifecycle
				// hooks, fire automatically on any reboot (incl. OTA) - not
				// button-gated, not diagnostics. Both just call stop() on
				// esp-idf, for a clean disconnect/advertising-stop before the
				// actual reboot instead of relying on the hardware reset alone.
				void on_shutdown() override;
				void on_safe_shutdown() override;

				// own-commits bisection: connectWakeStart, ported for full
				// structural parity with esp-idf (per user request, even
				// though it's only ever invoked via its own button action -
				// dead code otherwise, can't affect a normal pairing test).
				void connectWakeStart(uint32_t hold_ms = 0);
				// own-commits bisection: powerAdvertStart/Stop, ditto - reached
				// via pressSpecial(SPECIAL_POWER) while disconnected, which the
				// auto-generated "Power" special-key button already calls.
				//
				// 2026-11-23: directed=true sends the wake burst as a directed
				// advert to the bonded TV instead of an undirected one - some
				// TV firmware only reacts to a remote it has a bond with.
				// named=true additionally puts the device name into the
				// advertising packet (the classic MiPower packet is anonymous).
				void powerAdvertStart(bool directed = false, bool named = false);
				void powerAdvertStop();

				// 2026-11-23: which wake-broadcast flavour to send.
				//   "mipower"   - the classic Mi BOX packet (company id 0x0046
				//                 + 18 bytes). This TV does NOT answer to it.
				//   "mi_rc"     - byte-for-byte what the ORIGINAL Xiaomi
				//                 remote sends when a key is pressed
				//                 (captured with the board's own sniffer):
				//                 Flags 05, UUID 1812, name "MI RC",
				//                 TX power 00, manufacturer data 00 01
				//                 (company id 0x0000).
				//   "mi_rc_own" - same, but with our own device name.
				void setPowerAdvertStyle(const std::string &style) { this->_power_advert_style = style; }

				// 2026-11-23: give the board its OWN random static BLE address.
				// The original Xiaomi remote advertises with a random static
				// address (D4:B8:FF:7D:AD:6D - top two bits of the first byte
				// are 11). A TV in standby filters the advertisements it
				// accepts, and a public address (the chip's own MAC,
				// 9C:96:D5:B0:C2:7E) is not in the same category as the
				// random static address the TV ships with. The address is
				// derived from the chip MAC - it is NOT a copy of the
				// original remote's address, because two devices sharing an
				// address would break the real remote.
				// NOTE: changing the identity address invalidates the bond,
				// so the board has to be paired with the TV again afterwards.
				// NOTE: the name has to match what ESPHome's codegen emits
				// (snake_case, like set_delay / set_state_sensor).
				void set_own_addr_random(bool v) { this->_own_addr_random = v; }

				// 2026-11-23: pin the TV's BLE address in the config.
				// The wake packet's 0xFE field carries the end of the TV's own
				// address, so the board has to know it even on a freshly
				// flashed board with no bond yet.
				void set_target_mac_address(const std::string &addr);

				// 2026-11-24: should a key press also send the WAKE
				// advertisement (the packet with the 0xFE field that carries
				// the TV's own address)?
				//
				// true  = the board can wake a TV that is in standby. This is
				//         what a real remote does: press a key in standby and
				//         the TV comes up.
				// false = the board is a plain remote: a key press while the
				//         TV is in standby does nothing at all, and the user
				//         turns the TV on by hand (with the original
				//         remote).
				//
				// Either way the TV never wakes UP ON ITS OWN: the permanent
				// advertisement is the idle packet (no 0xFE field), so the
				// TV is not being addressed at all until a key is pressed.
				void set_wake_on_press(bool v) { this->_wake_on_press = v; }

				// 2026-11-25: 哪些键在电视待机时允许把它唤醒。
				//
				// 用位掩码表示（bit N = special key N）。**0 = 不限制**，
				// 也就是任意键都能唤醒（老行为，兼容老配置）。
				//
				// 用户实测后的要求：待机时按电源键 → 开机（这是对的）；
				// 但按方向键/音量键**也会**开机，这不对 —— 导航键不该有
				// 开机的副作用。所以只有电源键被允许发唤醒广播，
				// 其余键在电视待机时**什么都不做**。
				void set_wake_keys(uint32_t mask) { this->_wake_keys_mask = mask; }
				bool wakeKeyAllowed(uint8_t k) const {
					if (this->_wake_keys_mask == 0) {
						return true;   // 没限制 = 任意键都能唤醒
					}
					return ((this->_wake_keys_mask >> k) & 1) != 0;
				}

				// 2026-11-23: wake mode - when the TV connects back after our
				// wake broadcast, automatically send the HID POWER key over
				// that link (that is how the original remote does it).
				void setWakeSendPowerOnConnect(bool v) { this->_wake_send_power_on_connect = v; }

				// Manual recovery action (2026-09-03): startReconnectAdvert()/
				// fireDirectedBurst() deliberately never fall back from
				// HD-directed-only retry to plain/discoverable on their own -
				// that protects a still-live bond from being evicted by a
				// stray pairing just because the real peer is briefly
				// unreachable (off/rebooting). But it also means a bond that
				// went stale WITHOUT a clean reason=0x213 disconnect (e.g. the
				// peer forgot/unpaired us while we were powered off) has no
				// automatic way back to discoverability. Only a human has the
				// missing context (genuinely gone vs. just asleep) to make
				// that call safely, so this exposes it as an explicit action
				// instead of guessing from elapsed time. Reconstructed from
				// (and matches) the pre-bisection esp-idf design's own manual
				// plain_advert action, deleteAllBonds() included.
				void plainAdvertStart();

				// 2026-11-23: force plain undirected advertising WITHOUT
				// dropping the bond. plainAdvertStart() above is a "start
				// over, forget everything" action (it calls deleteAllBonds),
				// which is NOT what you want when the TV simply rebooted and
				// the board is sitting in a directed burst that the TV's
				// reconnect scan missed. This one only changes the
				// advertising mode.
				void reconnectAdvertStart();

				// 2026-11-23: BLE SNIFFER. The decisive experiment for the
				// "wake the TV" problem: with the TV powered OFF, let the board
				// listen to every BLE advertisement in the air and print the
				// raw bytes. Then press the POWER button on the ORIGINAL
				// remote - whatever packet it sends is the one we have to
				// imitate.
				// NOTE: scanning stops the board's own advertising (a NimBLE
				// host can only do one GAP event at a time), so the board is
				// invisible while sniffing.
				void sniffStart(uint32_t seconds);
				void sniffStop();
				void onResult(const NimBLEAdvertisedDevice *advertisedDevice) override;

			protected:
				binary_sensor::BinarySensor *state_sensor_;

			private:
				bool is_connected();
				void update_timer();
				void delay_ms(uint64_t ms);
				// own-commits bisection: powerAdvertData1/2 (internal, timer-chained)
				void powerAdvertData1();
				void powerAdvertData2();
				// 2026-11-23: shared burst starter - sets the advertising MODE
				// explicitly every time (the reconnect path leaves the stack in
				// directed mode, and the wake burst used to inherit it).
				bool startPowerAdvert(NimBLEAdvertisementData &burstData, const char *label);

				// 2026-11-23 - builds the advertising payload that mimics the
				// packet the ORIGINAL Xiaomi remote sends, captured with the
				// board's own sniffer while the TV was in standby:
				//   Flags 05 | Service UUID 0x1812 | Short name "MI RC"
				//   | Complete local name | Manufacturer data 00 <mfgByte>
				// The manufacturer data (company id 0x0000) is the decisive
				// part: the board's old default advertisement carried NO
				// manufacturer data in the advertising packet at all, so a TV
				// in standby had nothing that identifies this device as "the
				// remote" and never connected back.
				// mfgByte 0x01 = the remote's "key pressed" packet, 0x00 = its
				// idle packet. useOwnName puts OUR bonded name into the
				// complete local name instead of the original's "MI RC".
				bool buildOrigAdvert(NimBLEAdvertisementData &data, uint8_t mfgByte, bool useOwnName);

				// 2026-11-23 - THE WAKE PACKET.
				//
				// 31 bytes, exactly the packet the original Xiaomi remote
				// sends, and the one that is known to wake a Xiaomi TV out of
				// standby (github.com/dckiller51/esphome-xiaomi-ble-wake):
				//
				//   02 01 05              Flags (LE general discoverable)
				//   03 FF 00 01           Manufacturer data, company 0x0000
				//   06 08 "MI RC"         Shortened local name
				//   03 02 12 18           16-bit service UUID 0x1812 (HID)
				//   04 0D 04 05 00        the remote's device-class field
				//   02 0A 00              TX power 0 dBm
				//   04 FE <tv5> <tv4> <tv3>
				//                         Xiaomi's wake field: the END of the
				//                         TV's OWN address, reversed. The TV
				//                         sees its own address in here and
				//                         knows this advertisement is meant
				//                         for it - that is what wakes it.
				//
				// The 31-byte budget is used up completely, so the complete
				// local name goes into the scan response instead.
				bool buildWakeAdvert(NimBLEAdvertisementData &data);

				// 2026-11-24 - THE IDLE PACKET (the fix for "the TV wakes up
				// by itself").
				//
				// The wake packet must ONLY go out when a key is pressed.
				// If it is the permanent advertisement, the TV hears its own
				// address in every single frame and wakes on its own - which
				// is exactly what the user reported.
				//
				// The original remote does the same thing: its idle
				// advertisement carries NO 0xFE field at all (captured with
				// the board's own sniffer):
				//
				//   02 01 05              Flags
				//   03 FF 00 00           Manufacturer data, company 0x0000, 0x00
				//   06 08 "MI RC"         Shortened local name
				//   03 03 12 18           16-bit service UUID 0x1812 (HID),
				//                          AD type 0x03 = COMPLETE list
				//   04 0D 04 05 00        the remote's device-class field
				//   02 0A 00              TX power 0 dBm
				//
				// Differences from the original, on purpose:
				//   · the shortened local name is OURS ("MI Remote"), because
				//     the TV's Bluetooth settings page only lists the board
				//     under that name - it never showed "MI RC".
				//   · the complete local name goes into the scan response
				//     (the ADV has no room for it: 30 of 31 bytes are used).
				bool buildIdleAdvert(NimBLEAdvertisementData &data);

				// 2026-11-23 - A KEY PRESS IS THE WAKE TRIGGER.
				//
				// The original remote advertises on EVERY key press, and that
				// advertisement is what wakes a TV that is in standby. It has
				// to go out whether or not we believe we are connected: a TV
				// in standby keeps the GATT link up, so "the link is up" does
				// NOT mean "the TV is awake" - the HID report would go into a
				// suspended stack and be lost.
				//
				// 2026-11-24 - BUT ONLY WHILE THE TV IS NOT AWAKE.
				// If the link IS up, the TV is awake and the key reaches it
				// directly. Sending the wake packet then would be actively
				// harmful for the POWER key: the TV would go into standby
				// and then immediately be woken up again by our own 0xFE
				// frames. So the burst is only started when we are NOT
				// connected.
				void startWakeAdvert();

				// 2026-11-23 - REAL BUG FIX.
				// NimBLEDevice::isBonded() compares the address TYPE first
				// (NimBLEAddress::operator==), and the type NimBLE recorded
				// in the bond store for this TV does not match the type
				// inferred from the address bits, so the comparison never
				// matched and startReconnectAdvert() always fell back to
				// plain advertising - the HD directed burst it is built
				// around has never actually run.
				// This looks the peer up by ADDRESS BYTES in the bond store
				// and remembers the address (including its type) the store
				// holds, so every later peer operation uses the same record.
				bool findBondedTarget();

				// The address to use for the TV in peer operations: the one
				// from the bond store when there is a bond, otherwise the
				// type inferred from the address bits.
				NimBLEAddress peerAddress() const;

				// own-commits bisection stage 3/5: bond-preservation/reconnect
				// dispatch, ported from esp-idf branch minus HD-burst (stage 4).
				void loadTargetMac();
				void learnTargetMac(NimBLEAddress addr);
				void startPlainAdvertising();
				void startReconnectAdvert();
				// own-commits bisection stage 4/5
				void fireDirectedBurst();

				// Feature 2026-09-04: any button press while disconnected
				// used to silently do nothing (except SPECIAL_POWER, which
				// stays separate - that's a wake-an-OFF-TV attempt, not a
				// reconnect, and HD-burst can't reach a TV whose BLE radio
				// is off anyway). Matches the industry-standard BLE HID
				// remote pattern found via research: a key press is the
				// "external event" that (re-)starts the reconnect-
				// advertising cycle, not a timer or network check. Queues
				// the command and re-arms startReconnectAdvert(); onConnect()
				// fires it once actually reconnected. Only the latest
				// press wins if pressed repeatedly while still reconnecting.
				void queuePendingCommand(uint8_t key, bool is_special);

				NimBLEServer 			*pServer;
				NimBLEHIDDevice*		hid;
				NimBLECharacteristic*	inputKeyboard;
				NimBLECharacteristic*	outputKeyboard;
				NimBLECharacteristic*	inputSpecialKeys;
				NimBLECharacteristic*	vendorReport_06;
				NimBLECharacteristic*	vendorReport_07;
				NimBLECharacteristic*	vendorReport_08;
				NimBLEAdvertising*		advertising;

				bool 				_reconnect{true};
				uint32_t 			_default_delay{100};
				uint32_t 			_release_delay{8};
				KeyReport			_keyReport;
				SpecialKeyReport	_specialKeyReport;
				std::string			deviceName;
				std::string			deviceManufacturer;
				// Optional BLE address override (original remote MAC) so a
				// standby TV that matches by address will wake for us.
				std::string			ownMac;
				// 2026-11-23: use the chip MAC as a RANDOM STATIC address
				// instead of the chip's public address - see setOwnAddrRandom().
				bool				_own_addr_random = false;
				// 2026-11-23: the peer's address as the BOND STORE holds it
				// (bytes + the address type NimBLE recorded for it).
				NimBLEAddress		_bonded_target;
				bool				_has_bonded_target = false;
				// 2026-11-23 「求同」：默认广播包用哪种风格。
				//   "mi_rc"     = 逐字节复刻原装遥控器（电视配对时才会认）
				//   "mi_remote" = 原来的默认（Appearance + 小米 0x0046 厂商数据）
				std::string			advertStyle{"mi_remote"};
				// 2026-11-24: 按键要不要顺便发唤醒广播（0xFE 那个包）。
				// 见 set_wake_on_press()。
				bool				_wake_on_press = true;
				// 2026-11-25: 待机时哪些键能唤醒电视（位掩码，0 = 不限制）。
				uint32_t			_wake_keys_mask = 0;
				uint8_t				batteryLevel;
				bool				_connected = false;
				uint32_t			_delay_ms = 7;

				// own-commits bisection stage 3/5
				bool				_should_readvertise{true};
				uint64_t			_target_mac = 0;
				bool				_has_target_mac = false;
				bool				_target_mac_from_config = false;
				ESPPreferenceObject	_target_mac_pref;
				// 2026-11-23: the TV's BLE address is a RANDOM STATIC address
				// (C8:28:32:62:77:AA -> top two bits 11). Every previous
				// directed-advert / connect attempt built NimBLEAddress with
				// BLE_ADDR_PUBLIC, so the HCI "directed advertising" command
				// carried the wrong peer address type and the TV's standby
				// scanner ignored it. Infer the type from the address bits.
				uint8_t target_addr_type() const {
					return (((this->_target_mac >> 40) & 0xC0) == 0xC0) ? BLE_ADDR_RANDOM : BLE_ADDR_PUBLIC;
				}
				// own-commits bisection stage 4/5
				uint32_t			_reconnect_retry_until_ms = 0;
				// own-commits bisection: powerAdvert*
				uint32_t			_power_advert_delay = 1000;
				uint8_t				_power_advert_cycle = 0;
				// 2026-11-23: which manufacturer byte the "mi_orig" wake burst
				// is currently sending - 0x01 (the original remote's "key
				// pressed" packet) or 0x00 (its idle packet). The burst
				// alternates between the two.
				uint8_t				_power_advert_variant = 0x01;
				// How many Data1/Data2 round trips the wake burst lasts.
				// The TV needs time to scan, connect back and receive the HID
				// POWER key, so the mi_rc style uses a much longer window.
				uint16_t			_power_advert_cycles = 5;
				// 2026-11-23: how long connectWakeStart keeps the link to the
				// (powered-off) TV open. The TV's BLE host stays alive in a
				// low-power wake state and boots the TV when a bonded remote
				// connects - but it needs the link to STAY up long enough to
				// notice. Disconnecting immediately (the old behaviour) meant
				// the connection attempt succeeded and nothing happened.
				uint32_t			_connect_wake_hold_ms = 12000;
				// 2026-11-23: whether the wake burst goes out directed (to the
				// bonded TV) or undirected (the classic MiPower broadcast).
				bool				_power_advert_directed = false;
				// 2026-11-23: whether the wake burst also carries the device
				// name (for TV firmware that matches the bonded remote by name).
				bool				_power_advert_named = false;
				// 2026-11-23: which wake-broadcast flavour ("mipower" /
				// "mi_rc" / "mi_rc_own" / "mi_orig" / "mi_wake").
				//   "mipower" - the classic Mi BOX packet (company id 0x0046
				//                + 18 bytes). This TV does NOT answer to it.
				//   "mi_wake" - the 31-byte packet the original remote sends,
				//                including the 0xFE field that carries the end
				//                of the TV's own address - DEFAULT, because
				//                that is the packet this TV answers to.
				// See setPowerAdvertStyle().
				std::string			_power_advert_style = "mi_wake";
				// 2026-11-23: wake mode - set while broadcasting the wake
				// packet; cleared as soon as the TV connects back and the
				// HID POWER key has been sent.
				bool				_wake_send_power_on_connect = false;
				// The manufacturer payload of the burst currently being sent.
				std::vector<uint8_t>	_power_advert_payload;
				// Gap fix 2026-09-03: the normal advertising payload (flags +
				// appearance + HID service UUID, set up once in setup()) sits
				// at the legacy 31-byte cap with zero bytes to spare - real,
				// measured on hardware (advData=31, scanData=31, budget 31),
				// not a guess. setManufacturerData() on the live advertising
				// object was therefore FAILING on every single call, even an
				// empty one, so the whole powerAdvertStart() burst has never
				// actually transmitted anything. Fix: swap in a fresh,
				// minimal NimBLEAdvertisementData (just the manufacturer
				// data) for the duration of the burst, saved here once in
				// setup() so powerAdvertStop() can restore the real one.
				NimBLEAdvertisementData _normal_advert_data;
				// Same for the scan response (holds the Xiaomi manufacturer
				// data) - the wake burst replaces it too and has to restore it.
				NimBLEAdvertisementData _normal_scan_data;

				// Feature 2026-09-04: queuePendingCommand() state - see its
				// doc comment above.
				bool				_has_pending_command = false;
				bool				_pending_is_special = false;
				uint8_t				_pending_key = 0;
				// 2026-11-23: set while a queued command is being delivered
				// over a link the TV just opened - that key must NOT trigger
				// another wake advertisement.
				bool				_delivering_queued = false;

				// 2026-11-23: BLE sniffer state.
				bool				_sniffing = false;


				uint16_t sid		= 0x01;
				uint16_t vid		= 0x2717;
				// 2026-11-23: the ORIGINAL Xiaomi remote reports product id
				// 0x32b8 (seen in the TV's `dumpsys input`:
				//   Device 5: 小米蓝牙语音遥控器
				//   bus=0x0005 vendor=0x2717 product=0x32b8 version=0x0111).
				// We were using 0x32b9 - close, but the TV runs a dedicated
				// BleRemoteControllerService that classifies remotes by
				// vendor/product id, and its standby wake scanner may only
				// react to a device it classifies as "the remote".
				// Use the original's exact product id.
				uint16_t pid		= 0x32b8;
				uint16_t version	= 0x4a4f;

			protected:
				virtual void onStarted(NimBLEServer *pServer) { };
				// nimble-cpp-bisect: tag 2.0.0 added NimBLEConnInfo& to every
				// callback (and a reason code to onDisconnect) - [Breaking]
				// Update callbacks to use NimBLEConnInfo (ba79a1b).
				virtual void onConnect(NimBLEServer* pServer, NimBLEConnInfo& connInfo) override;
				virtual void onDisconnect(NimBLEServer* pServer, NimBLEConnInfo& connInfo, int reason) override;
				virtual void onWrite(NimBLECharacteristic* me, NimBLEConnInfo& connInfo) override;
		};
	}  // namespace ble_mi_remote
}  // namespace esphome

#endif
