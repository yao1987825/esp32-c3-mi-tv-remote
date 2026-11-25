
#ifdef USE_ESP32

#include "ble_mi_remote.h"
#include <NimBLEServer.h>
#include <NimBLEDevice.h>
#include <NimBLEService.h>
#include <NimBLEUtils.h>
#include <NimBLEHIDDevice.h>
#include <NimBLECharacteristic.h>
#include <NimBLEAdvertising.h>
#include "HIDTypes.h"
#include "HIDKeyboardTypes.h"
#include "sdkconfig.h"
#include <string>
#include <list>
#include <string.h>
#include "esphome/core/log.h"

// 2026-11-23 诊断用：列出板子上已保存的 bond（NimBLE 的 C API）
extern "C" int ble_store_util_bonded_peers(ble_addr_t *peer_id_addrs, int *num_peers, int max_peers);

#define CONSUMER_ID 0x01
#define KEYBOARD_ID 0x02

static const uint8_t _hidReportDescriptor[] = {
		USAGE_PAGE(1),			0x0C,			// Consumer
		USAGE(1),				0x01,			// Consumer Control

		COLLECTION(1),			0x01,			// Application

		REPORT_ID(1),			CONSUMER_ID,	//
		LOGICAL_MINIMUM(1),		0x00,			//
		LOGICAL_MAXIMUM(1),		0x01,			//
		REPORT_SIZE(1),			0x01,			//
		REPORT_COUNT(1),		0x18,			// 24
		USAGE(1),				0x41,			// Menu Pick
		USAGE(1),				0x42,			// Menu Up
		USAGE(1),				0x43,			// Menu Down
		USAGE(1),				0x44,			// Menu Left
		USAGE(1),				0x45,			// Menu Right
		USAGE(1),				0x30,			// Power
		USAGE(1),				0xCF,			// Voice Command
		USAGE(1),				0xE9,			// Volume Increment
		USAGE(1),				0xEA,			// Volume Decrement
		USAGE(2),				0xA2, 0x01,		// Instance 41473 (Select Task/Application)
		USAGE(2),				0xB8, 0x01,		// Instance 47105 (Movie Browser)
		USAGE(1),				0x6A,			// Green Menu Button
		USAGE(1),				0x6B,			// Blue Menu Button
		USAGE(1),				0x6C,			// Yellow Menu Button
		USAGE(2),				0x8A, 0x01,		// Instance 35329 (Email reader??)
		USAGE(2),				0x92, 0x01,		// Instance 37377 (Calculator)
		USAGE(2),				0x94, 0x01,		// Instance 37889 (Local Machine Browser)
		USAGE(1),				0xCF,			// Voice Command
		USAGE(2),				0x23, 0x02,		// Instance 8962 (Home)
		USAGE(2),				0x24, 0x02,		// Instance 9218 (Back)
		USAGE(2),				0x25, 0x02,		// Instance 9474 (Forward)
		USAGE(2),				0x26, 0x02,		// Instance 9730 (Stop)
		USAGE(2),				0x27, 0x02,		// Instance 9986 (Refresh)
		USAGE(2),				0x2A, 0x02,		// Instance 10754 (Bookmarks)
		HIDINPUT(1),			0x02,			// In bytes

		USAGE_PAGE(2),			0x00, 0xFF,		// Vendor ??? переставить местами байты?
		USAGE(1),				0x00,			// Vendor

		COLLECTION(1),			0x01,			// Application

		REPORT_ID(1),			0x06,			//
		REPORT_SIZE(1),			0x08,			//
		REPORT_COUNT(1),		0x78,			// 120
		LOGICAL_MINIMUM(1),		0x00,			//
		LOGICAL_MAXIMUM(1),		0xFF,			// -1
		USAGE_MINIMUM(1),		0x00,			//
		USAGE_MAXIMUM(1),		0xFF,			//
		HIDINPUT(1),			0x00,			//

		REPORT_ID(1),			0x07,			//
		REPORT_SIZE(1),			0x08,			//
		REPORT_COUNT(1),		0x78,			// 120
		LOGICAL_MINIMUM(1),		0x00,			//
		LOGICAL_MAXIMUM(1),		0xFF,			// -1
		USAGE_MINIMUM(1),		0x00,			//
		USAGE_MAXIMUM(1),		0xFF,			//
		HIDINPUT(1),			0x00,			//

		REPORT_ID(1),			0x08,			//
		REPORT_SIZE(1),			0x08,			//
		REPORT_COUNT(1),		0x78,			// 120
		LOGICAL_MINIMUM(1),		0x00,			//
		LOGICAL_MAXIMUM(1),		0xFF,			// 255
		USAGE_MINIMUM(1),		0x00,			//
		USAGE_MAXIMUM(1),		0xFF,			//
		HIDINPUT(1),			0x00,			//

		END_COLLECTION(0),

		USAGE_PAGE(1),			0x01,			// Generic Desktop Controls
		USAGE(1),				0x06,			// Keyboard

		COLLECTION(1),			0x01,			// Application

		REPORT_ID(1),			KEYBOARD_ID,	//
		USAGE_PAGE(1),			0x07,			// Keyboard/Keypad
		USAGE_MINIMUM(1),		0xE0,			// Ctrl, Shift, Alt, GUI
		USAGE_MAXIMUM(1),		0xE7,			// Ctrl, Shift, Alt, GUI
		LOGICAL_MINIMUM(1),		0x00,			//
		LOGICAL_MAXIMUM(1),		0x01,			//
		REPORT_SIZE(1),			0x01,			//
		REPORT_COUNT(1),		0x08,			//
		HIDINPUT(1),			0x02,			//
		REPORT_COUNT(1),		0x01,			//
		REPORT_SIZE(1),			0x08,			//
		HIDINPUT(1),			0x01,			//

		REPORT_COUNT(1),		0x05,			//
		REPORT_SIZE(1),			0x01,			//
		USAGE_PAGE(1),			0x08,			// LED
		USAGE_MINIMUM(1),		0x01,			//
		USAGE_MAXIMUM(1),		0x05,			//
		HIDOUTPUT(1),			0x02,			//
		REPORT_COUNT(1),		0x01,			//
		REPORT_SIZE(1),			0x03,			//
		HIDOUTPUT(1),			0x01,			//

		REPORT_COUNT(1),		0x06,			//
		REPORT_SIZE(1),			0x08,			//
		LOGICAL_MINIMUM(1),		0x28,			// 40
		LOGICAL_MAXIMUM(1),		0xFE,			// 254
		USAGE_PAGE(1),			0x07,			// Keyboard/Keypad
		USAGE_MINIMUM(1),		0x28,			// 40
		USAGE_MAXIMUM(1),		0xFE,			// 254
		HIDINPUT(1),			0x00,			//

		END_COLLECTION(0),
		END_COLLECTION(0)
};

namespace esphome {
	namespace ble_mi_remote {
		static const char *const TAG = "ble_mi_remote";

		BleMiRemote::BleMiRemote(std::string name, std::string manufacturer_id, uint8_t battery_level, bool reconnect, std::string ble_name, std::string own_mac, std::string advert_style)
			:
				PollingComponent(1000),
				hid(0),
				// The advertised name is cut to 15 BYTES, so a Chinese name gets
				// sliced mid-character and the TV lists it as garbage. ble_name
				// (an explicit ASCII name) wins over the ESPHome entity name.
				deviceName(std::string(ble_name.empty() ? name : ble_name).substr(0, 15)),
			    deviceManufacturer(std::string(manufacturer_id).substr(0,15)),
			    ownMac(std::move(own_mac)),
			    advertStyle(std::move(advert_style)),
			    batteryLevel(battery_level)
		{
			_reconnect = reconnect;
		}

		void BleMiRemote::setup() {
			ESP_LOGI(TAG, "Setting up...");

			// own-commits bisection stage 3/5
			this->loadTargetMac();

			NimBLEDevice::init (deviceName);

			// 2026-11-23 - impersonate the original remote's BLE address.
			// The TV in standby ignores our wake advert (packet bytes match the
			// original exactly, but onConnect never fires) - it appears to
			// match the BONDED DEVICE'S ADDRESS, not the payload. Set our
			// address to the original remote's so the TV's wake scanner
			// recognises us.
			// IMPORTANT: must run AFTER NimBLEDevice::init() (the NimBLE host
			// must be up) - calling it before init crashed with a Load access
			// fault (PC in ble_hs_id_set_rnd, MTVAL=0x44) and put the board
			// into a boot loop. It is still before createServer()/GATT setup.
			if (!ownMac.empty()) {
				uint8_t mac[6] = {0};
				int n = 0;
				// parse "D4:B8:FF:7D:AD:6D" -> 6 bytes
				for (const char *p = ownMac.c_str(); *p && n < 6; ) {
					mac[n++] = (uint8_t) strtoul(p, (char**) &p, 16);
					while (*p == ':' || *p == '-') p++;
				}
				// 2026-11-23: the textual MAC "D4:B8:FF:7D:AD:6D" is MSB-first,
				// but ble_hs_id_set_rnd() expects the controller's LSB-first
				// byte order and checks the TOP bits of mac[5] to decide whether
				// it is a valid random-static address. Parsing it verbatim made
				// mac[5] = 0x6D (top bits 01) -> BLE_HS_EINVAL -> setOwnAddr=FAILED.
				// Reverse the six bytes before handing them to NimBLE.
				for (int i = 0; i < n / 2; i++) {
					uint8_t tmp = mac[i];
					mac[i] = mac[n - 1 - i];
					mac[n - 1 - i] = tmp;
				}
				// setOwnAddr() writes a RANDOM address (ble_hs_id_set_rnd), so
				// force the own-address type to random to match the original
				// remote (D4:B8:FF:... has its top two bits set = random static).
				bool typeOk = NimBLEDevice::setOwnAddrType(BLE_ADDR_RANDOM);
				bool addrOk = (n == 6) && NimBLEDevice::setOwnAddr(mac);
				ESP_LOGI(TAG, "setup: own_mac=%s parsed=%d setOwnAddrType=%s setOwnAddr=%s actual=%s",
				         ownMac.c_str(), n, typeOk ? "OK" : "FAILED", addrOk ? "OK" : "FAILED",
				         NimBLEDevice::getAddress().toString().c_str());
			} else if (this->_own_addr_random) {
				// =================================================================
				// 2026-11-23 - the board's OWN random static address.
				//
				// The original Xiaomi remote advertises with a random static
				// address (D4:B8:FF:7D:AD:6D - the top two bits of the first
				// byte are 11). The board advertises with the chip's PUBLIC
				// address (9C:96:D5:B0:C2:7E). A TV in standby decides which
				// advertisements to act on, and a public address is not the
				// same category of address as the random static one the TV
				// ships with - so the board may simply not be on the list the
				// standby scanner walks.
				//
				// The address is derived from the CHIP's own MAC with the top
				// two bits forced to 11 - it is NOT a copy of the original
				// remote's address: two devices with the same address would
				// break the real remote.
				//
				// NOTE: changing the identity address invalidates the bond,
				// so the board must be paired with the TV again afterwards.
				// =================================================================
				std::string chipMac = NimBLEDevice::getAddress().toString();
				uint8_t msb[6] = {0};
				int n = 0;
				for (const char *p = chipMac.c_str(); *p && n < 6; ) {
					msb[n++] = (uint8_t) strtoul(p, (char**) &p, 16);
					while (*p == ':' || *p == '-') p++;
				}
				if (n != 6) {
					ESP_LOGW(TAG, "setup: could not parse the chip MAC '%s' - keeping the public address", chipMac.c_str());
				} else {
					// Random static address: the top two bits of the most
					// significant byte must be 11.
					msb[0] = (uint8_t) ((msb[0] & 0x3F) | 0xC0);
					// ble_hs_id_set_rnd() wants the controller's LSB-first byte
					// order and checks the TOP bits of mac[5] - so reverse the
					// six MSB-first bytes we just parsed.
					uint8_t mac[6];
					for (int i = 0; i < 6; i++) {
						mac[i] = msb[5 - i];
					}
					bool typeOk = NimBLEDevice::setOwnAddrType(BLE_ADDR_RANDOM);
					bool addrOk = NimBLEDevice::setOwnAddr(mac);
					char rndHex[24];
					snprintf(rndHex, sizeof(rndHex), "%02X:%02X:%02X:%02X:%02X:%02X",
							 msb[0], msb[1], msb[2], msb[3], msb[4], msb[5]);
					ESP_LOGI(TAG, "setup: own random static addr: chip=%s -> %s setOwnAddrType=%s setOwnAddr=%s actual=%s",
							 chipMac.c_str(), rndHex, typeOk ? "OK" : "FAILED", addrOk ? "OK" : "FAILED",
							 NimBLEDevice::getAddress().toString().c_str());
					if (addrOk) {
						// The identity address changed, so the old bond (if
						// any) no longer describes this device.
						this->_has_bonded_target = false;
					}
				}
			} else {
				ESP_LOGI(TAG, "setup: no own_mac configured, using chip MAC");
			}
			// Real bug, found 2026-09-03: this used to redeclare pServer as
			// a local ("NimBLEServer *pServer = ..."), which shadows the
			// class member of the same name for the rest of setup() - the
			// member this->pServer was therefore NEVER actually assigned
			// anywhere, staying null/garbage for the object's whole
			// lifetime. Every OTHER method that reads pServer (stop(),
			// powerAdvertData1/2/Stop, fireDirectedBurst, etc.) reads the
			// real member, not a local - some of those calls happened to
			// tolerate a null this (probably touching mostly-static NimBLE
			// internals), which is why this went unnoticed for so long;
			// pServer->getAdvertising() does not, and crashed hardware
			// (LoadProhibited) the first time powerAdvertStart() actually
			// got exercised. Assign the member directly - no local.
			pServer = NimBLEDevice::createServer();
			pServer->setCallbacks(this);

			hid = new NimBLEHIDDevice(pServer);
			// nimble-cpp-bisect: NimBLEHIDDevice renamed several methods in
			// tag 2.0.0 - [BREAKING] - Refactor NimBLEHIDDevice (6d10f2f).
			inputSpecialKeys = hid->getInputReport(CONSUMER_ID);
			inputKeyboard = hid->getInputReport(KEYBOARD_ID);
			outputKeyboard = hid->getOutputReport(KEYBOARD_ID);
			outputKeyboard->setCallbacks(this);

			vendorReport_06 = hid->getInputReport(0x06);
			vendorReport_07 = hid->getInputReport(0x07);
			vendorReport_08 = hid->getInputReport(0x08);

			hid->setManufacturer(deviceManufacturer);
			hid->setPnp(sid, vid, pid, version);
			hid->setHidInfo(0x00, 0x00);

			// 2026-11-23 修正配对：
		// 原来 setSecurityAuth(true, true, true) = mitm=true + bonding=true +
		// secure_connections=true，但 NimBLE 的 io_cap 是
		// BLE_HS_IO_NO_INPUT_OUTPUT（既不显示也不输入 PIN）。
		// 要求 MITM 却没有输入输出通道 => 电视发起的配对永远协商失败，
		// 板子��不到 bond，按键发不出去（电视连上了也不响应）。
		// ★★★ 2026-11-23 决定性 bug 修复：参数顺序搞错了 ★★★
		// NimBLE 的真实签名是 setSecurityAuth(bonding, mitm, sc)，不是
		// (mitm, bonding, sc)！之前写成 setSecurityAuth(false, true, false)
		// 实际含义 = bonding=FALSE, mitm=TRUE, sc=FALSE：
		//   - bonding=false → 配对时**根本不存 bond**（这就是 bond 一直为
		//     0、断线后无法自动重连、每次都要重新配对的真正根因！）
		//   - mitm=true 但没有 IO 能力 → 配对协商也不标准
		// 正确配置：bonding=true（存 bond）+ mitm=false（Just Works，无需 PIN）
		//           + sc=false（Legacy，兼容 Android 6 电视）。
		NimBLEDevice::setSecurityAuth(true, false, false);
		ESP_LOGI(TAG, "setup: security auth = bonding=true, mitm=false (Just Works), sc=false");

		// 2026-11-23 诊断：把板子上**已经存下的 bond** 全列出来。
		// 电视上点了配对之后如果这里是空的，说明加密握手根本没完成
		// （电视界面可能照样显示"已连接"，但 bond 没存住）。
		{
			int maxBonds = MYNEWT_VAL(BLE_STORE_MAX_BONDS);
			if (maxBonds <= 0) {
				maxBonds = 4;
			}
			ble_addr_t peerAddrs[8];
			int numPeers = maxBonds > 8 ? 8 : maxBonds;
			memset(peerAddrs, 0, sizeof(peerAddrs));
			int rc = ble_store_util_bonded_peers(peerAddrs, &numPeers, maxBonds);
			ESP_LOGI(TAG, "setup: saved bonds = %d (rc=%d)", numPeers, rc);
			for (int i = 0; i < numPeers; i++) {
				ble_addr_t a = peerAddrs[i];
				ESP_LOGI(TAG, "setup:   bond[%d] type=%d %02X:%02X:%02X:%02X:%02X:%02X",
						 i, (int) a.type,
						 a.val[5], a.val[4], a.val[3], a.val[2], a.val[1], a.val[0]);
			}
		}

			hid->setReportMap((uint8_t*) _hidReportDescriptor, sizeof(_hidReportDescriptor));
			// nimble-cpp-bisect: hid->startServices() deprecated as of 2.5.0
			// ("Services are now started by the server when start() is
			// called") - pServer->start() is the direct replacement.
			pServer->start();

			onStarted(pServer);

			advertising = pServer->getAdvertising();

			// =================================================================
			// 2026-11-23 - CRITICAL fix, found by bisecting why the TV's
			// "search device" list never showed "MI Remote" even though the
			// board was broadcasting and the TV really was scanning:
			//
			// NimBLEAdvertising::setName() puts the name in the SCAN RESPONSE
			// as soon as scan response is enabled:
			//     if (m_scanResp && m_scanData.setName(name)) { ...; return true; }
			//
			// Android 6 (the MiTV4-ANSM0 firmware) does NOT surface scan
			// response content to apps - BluetoothLeScanner.onScanResult()
			// only ever gets the ADVERTISING packet. So the TV was scanning
			// fine and DID receive the board, but every packet it got had no
			// name in it, the settings app dropped it, and "MI Remote" never
			// showed up in the device list.
			//
			// Fix: build the advertising packet BY HAND and put the device
			// name in the ADVERTISING data itself. Scan response stays
			// enabled and now carries the Xiaomi manufacturer data instead
			// of the name.
			//
			// 31-byte legacy advertising budget:
			//   Flags               3
			//   Appearance          4   (0x03F1 HID keyboard)
			//   Complete Local Name 11  ("MI Remote")
			//   Service UUID 0x1812 4   (compressed to 16-bit)
			//                         ---
			//                          22 bytes  -> fits
			// =================================================================
			NimBLEAdvertisementData advData;
			bool flagsOk = true, appearOk = true, nameOk = true, uuidOk = true;
			bool advSetOk = false;
			NimBLEAdvertisementData scanData;
			bool mfgOk = true;
			bool scanSetOk = false;

			if (this->advertStyle == "mi_idle") {
				// =================================================================
				// 2026-11-24 - THE IDLE PACKET (the default).
				//
				// This is what the board advertises PERMANENTLY. It has the
				// same structure as the original remote's packet, but
				// WITHOUT the 0xFE field:
				//
				//   02 01 05            Flags
				//   03 FF 00 00         Manufacturer data, company 0x0000, 0x00
				//   06 08 "MI Remote"   Shortened local name (ours)
				//   03 03 12 18         16-bit service UUID 0x1812 (HID),
				//                        AD type 0x03 = COMPLETE list
				//   04 0D 04 05 00      the remote's device-class field
				//   02 0A 00            TX power 0 dBm
				//
				// >>> WHY IT MUST NOT CONTAIN 0xFE <<<
				//
				// The 0xFE field carries the END of the TV's OWN address. A
				// TV in standby scans for it, sees its own address and wakes
				// itself up. So a permanent advertisement with 0xFE in it
				// means the TV is being addressed over and over - it wakes
				// up BY ITSELF, with nobody pressing anything.
				//
				// That is exactly what the user reported on 2026-11-24:
				// "为什么我没有按开机，电视自动开机".
				//
				// The original remote does not do that either: its idle
				// advertisement has no 0xFE at all (captured with the
				// board's own sniffer), and it only sends the wake packet
				// for ~3 s when a key is pressed.
				// =================================================================
				bool idleOk = this->buildIdleAdvert(advData);
				flagsOk = idleOk;
				appearOk = true;
				nameOk = idleOk;
				uuidOk = idleOk;
				mfgOk = idleOk;
				advSetOk = advertising->setAdvertisementData(advData);

				// Scan response: the complete local name, so the TV can still
				// see the board by name in its device list.
				bool scanNameOk = scanData.setName(this->deviceName);
				scanSetOk = advertising->setScanResponseData(scanData);
				if (!scanNameOk) {
					ESP_LOGW(TAG, "scanrsp[mi_idle]: setting the complete local name failed");
				}
			} else if (this->advertStyle == "mi_wake") {
				// =================================================================
				// 2026-11-23 - THE WAKE PACKET, as the PERMANENT advertisement.
				//
				//   02 01 05            Flags
				//   03 FF 00 01         Manufacturer data, company 0x0000
				//   06 08 "MI RC"       Shortened local name
				//   03 02 12 18         16-bit service UUID 0x1812 (HID)
				//   04 0D 04 05 00      the remote's device-class field
				//   02 0A 00            TX power 0 dBm
				//   04 FE <tv5><tv4><tv3>   Xiaomi's wake field: the END of
				//                            the TV's OWN address, reversed
				//
				// >>> The wake field is the missing piece. It tells the TV
				// >>> "this advertisement is addressed to ME" - the TV sees
				// >>> its own address in there and wakes up.
				// >>>
				// >>> Why we never found it earlier: the board's own sniffer
				// >>> only printed a FIXED list of AD types (0x01..0x22,
				// >>> 0xFF) - 0x0D and 0xFE were not in that list, so the
				// >>> bytes WERE in the air the whole time and simply never
				// >>> showed up in the log.
				//
				// ⚠ 2026-11-24: this style makes the TV wake UP BY ITSELF -
				//   the 0xFE field is in EVERY frame. Only keep it if that is
				//   what you want; the default is "mi_idle".
				// =================================================================
				bool wakeOk = this->buildWakeAdvert(advData);
				flagsOk = wakeOk;
				appearOk = true;
				nameOk = wakeOk;
				uuidOk = wakeOk;
				mfgOk = wakeOk;
				advSetOk = advertising->setAdvertisementData(advData);

				// Scan response: the complete local name, so the TV can still
				// see the board by name in its device list.
				bool scanNameOk = scanData.setName(this->deviceName);
				scanSetOk = advertising->setScanResponseData(scanData);
				if (!scanNameOk) {
					ESP_LOGW(TAG, "scanrsp[mi_wake]: setting the complete local name failed");
				}
			} else if (this->advertStyle == "mi_rc") {
				// =================================================================
				// 2026-11-23 「求同」模式。
				//
				// 电视在**配对**阶段看的必须是原装遥控器那个包，不能是我们自己
				// 拼的包：实测板子用自己那套广播（Flags 0x06 + Appearance +
				// 小米盒子 0x0046 厂商数据）时，电视连上后**很快就断开**，
				// 根本建不起 bond。
				//
				// 原装遥控器的包（板子自己的嗅探器抓的）：
				//   SNIFF D4:B8:FF:7D:AD:6D advType=0x00 name='MI RC'
				//     mfg=[00 01]
				//     ad=[T01:05 | T03:12 18 | T08:4D 49 20 52 43
				//         | T09:4D 49 20 52 43 | T0A:00 | TFF:00 01]
				//
				// 逐条对齐：
				//   T01:05   Flags = 0x01（LE General Discoverable）
				//            NimBLE 会自动 OR 上 BR/EDR 不支持位(0x04) -> 0x05
				//   T03:12 18  16-bit UUID 0x1812 (HID)
				//   T08 / T09   短名 + 全名 = "MI RC"
				//   T0A:00   TX Power = 0 dBm
				//   TFF:00 01  厂商数据 company id 0x0000 + 0x01
				// =================================================================
				flagsOk = advData.setFlags(0x01);
				uuidOk = advData.addServiceUUID(NimBLEUUID((uint16_t) 0x1812));
				// TX power = 0 dBm，raw AD 结构 (len, type, value)
				uint8_t txPowerAd[3] = {0x02, 0x0A, 0x00};
				advData.addData(txPowerAd, 3);
				mfgOk = advData.setManufacturerData(std::vector<uint8_t>{0x00, 0x01});
				nameOk = advData.setShortName("MI RC") && advData.setName("MI RC");
				advSetOk = advertising->setAdvertisementData(advData);
				// 原装遥控器没有 scan response 内容，扫描响应也放同一份
				scanSetOk = advertising->setScanResponseData(advData);
			} else if (this->advertStyle == "mi_orig") {
				// =================================================================
				// 2026-11-23 - the packet the ORIGINAL remote sends, with our
				// own name.
				//
				// Captured with the board's own sniffer while the TV was in
				// standby (Temp/sniff_asleep.log):
				//
				//   SNIFF D4:B8:FF:7D:AD:6D rssi=-68 advType=0x00
				//     name='小米蓝牙语音遥控器' mfg=[00 00]
				//     ad=[T01:05 | T03:12 18 | T08:4D 49 20 52 43
				//         | T09:<chinese> | T0A:00 | TFF:00 00]
				//
				//   SNIFF D4:B8:FF:7D:AD:6D rssi=-64 advType=0x00
				//     name='MI RC' mfg=[00 01]
				//     ad=[T01:05 | T03:12 18 | T08:4D 49 20 52 43
				//         | T09:4D 49 20 52 43 | T0A:00 | TFF:00 01]
				//
				// >>> THE DECISIVE ELEMENT IS THE LAST ONE: manufacturer data
				// >>> with company id 0x0000 and a single data byte (0x00
				// >>> idle / 0x01 key pressed).
				// >>>
				// >>> The board's OLD default advertisement carried NO
				// >>> manufacturer data in the advertising packet at all - the
				// >>> Xiaomi 0x0046 payload went into the SCAN RESPONSE, and
				// >>> Android 6 does not surface scan response content to the
				// >>> app that does the scanning. So a TV in standby, which
				// >>> reads the advertising packet, had nothing that says
				// >>> "this is the remote" and never connected back - even
				// >>> though the board was bonded with the TV.
				//
				// 31-byte legacy budget:
				//   Flags                3
				//   Service UUID 0x1812 4
				//   Short name "MI RC"   7
				//   Complete local name 11  ("MI Remote" - the name the TV
				//                                 bonded us under)
				//   Manufacturer data    4  (company id 0x0000 + 0x01)
				//                          ---
				//                           29 bytes -> fits
				//
				// The original also carries a TX power field (T0A:00); it does
				// not fit next to our own complete name, and it is only a
				// filler field, so it is left out.
				// =================================================================
				bool buildOk = this->buildOrigAdvert(advData, 0x01, true);
				flagsOk = buildOk;
				appearOk = true;
				nameOk = buildOk;
				uuidOk = buildOk;
				mfgOk = buildOk;
				advSetOk = advertising->setAdvertisementData(advData);

				// The scan response carries the SAME identity with the idle
				// variant of the manufacturer data (0x00 instead of 0x01), so
				// a scanner that looks at either packet finds the
				// company-0x0000 signature.
				bool scanBuildOk = this->buildOrigAdvert(scanData, 0x00, true);
				scanSetOk = advertising->setScanResponseData(scanData);
				if (!scanBuildOk) {
					ESP_LOGW(TAG, "scanrsp[mi_orig]: building the idle variant failed");
				}
			} else {
				flagsOk = advData.setFlags(0x06);
				appearOk = advData.setAppearance(HID_KEYBOARD);
				nameOk = advData.setName(deviceName);
				uuidOk = advData.addServiceUUID(hid->getHidService()->getUUID());
				advSetOk = advertising->setAdvertisementData(advData);

				// Scan response: the Xiaomi manufacturer data (company id 0x0046).
				// This is what the original Xiaomi remote's packet carries, and
				// what a TV in standby is expected to be listening for.
				advertising->enableScanResponse(true);
				mfgOk = scanData.setManufacturerData(std::vector<uint8_t>{0x46, 0x00, 0xe7, 0x12, 0x97, 0x30, 0x35, 0xf2, 0x78, 0xff, 0xff, 0xff, 0x30, 0x43, 0x52, 0x4b, 0x54, 0x4d});
				scanSetOk = advertising->setScanResponseData(scanData);
			}
			advertising->enableScanResponse(true);

			// Dump both packets so the real bytes can be checked against a
			// sniffer / the TV's scanner instead of guessing.
			std::string advHex, scanHex;
			for (uint8_t b : advData.getPayload()) {
				char tmp[4];
				snprintf(tmp, sizeof(tmp), "%02X ", b);
				advHex += tmp;
			}
			for (uint8_t b : (this->advertStyle == "mi_rc" ? advData : scanData).getPayload()) {
				char tmp[4];
				snprintf(tmp, sizeof(tmp), "%02X ", b);
				scanHex += tmp;
			}
			ESP_LOGI(TAG, "advert[%s]: flags=%s appearance=%s name=%s uuid=%s mfg=%s set=%s len=%u [%s]",
					this->advertStyle.c_str(),
					flagsOk ? "OK" : "FAIL", appearOk ? "OK" : "FAIL", nameOk ? "OK" : "FAIL",
					uuidOk ? "OK" : "FAIL", mfgOk ? "OK" : "FAIL", advSetOk ? "OK" : "FAIL",
					(unsigned) advData.getPayload().size(), advHex.c_str());
			ESP_LOGI(TAG, "scanrsp[%s]: mfg=%s set=%s len=%u [%s]",
					this->advertStyle.c_str(),
					mfgOk ? "OK" : "FAIL", scanSetOk ? "OK" : "FAIL",
					(unsigned) (this->advertStyle == "mi_rc" ? advData : scanData).getPayload().size(),
					scanHex.c_str());

			// Gap fix 2026-09-03: save the real advertising payload now,
			// while it's still whatever setup() above just built, so
			// powerAdvertStop() can restore it later - see the doc comment
			// on _normal_advert_data in the header.
			this->_normal_advert_data = advertising->getAdvertisementData();
			this->_normal_scan_data = advertising->getScanData();

			// 2026-11-23: fast advertising from the very first moment. A TV
			// in standby scans at a low duty cycle and needs to see us
			// several times in a row to act on the wake packet.
			advertising->setMinInterval(32);   // 20 ms
			advertising->setMaxInterval(48);   // 30 ms
			advertising->start();

			hid->setBatteryLevel(batteryLevel);

			ESP_LOGI(TAG, "Advertising started (undirected)");

			pServer = NimBLEDevice::getServer();

			// Gap fix, belongs to stage 4 (082953f, same commit that introduced
			// HD-burst itself): NimBLE's own advertiseOnDisconnect auto-restart
			// only knows plain undirected advertising and would race right after
			// our own onDisconnect() dispatcher, undoing a directed HD-burst it
			// just started. Always off - onDisconnect() is the sole place
			// deciding whether/how to re-advertise (already gated on
			// _should_readvertise there since stage 3).
			pServer->advertiseOnDisconnect(false);

			release();
		}

		// Gap fix, functional (not stage 5): esp-idf's stop()/start() moved off
		// the old advertiseOnDisconnect toggle (no longer meaningful now that
		// it's permanently false, set once in setup()) onto _should_readvertise
		// + the reconnect dispatcher directly - start() now actually goes
		// through startReconnectAdvert() (HD-burst if bonded) instead of a
		// bare advertising->start().
		void BleMiRemote::stop() {
			this->_should_readvertise = false;
			// A pending reconnect-burst fallback (startReconnectAdvert()) would
			// otherwise fire later and re-start advertising, undoing this stop().
			this->cancel_timeout("ble_mi_remote_reconnect_burst");

			std::vector<uint16_t> ids = pServer->getPeerDevices();

			if (ids.size() > 0) {
				for (uint16_t &id : ids) {
					pServer->disconnect(id);
				}
			} else {
				pServer->stopAdvertising();
			}
		}

		void BleMiRemote::start() {
			this->_should_readvertise = true;
			this->startReconnectAdvert();
		}

		void BleMiRemote::on_shutdown() {
			this->stop();
		}

		void BleMiRemote::on_safe_shutdown() {
			this->stop();
		}

		void BleMiRemote::update() { state_sensor_->publish_state(this->_connected); }

		bool BleMiRemote::is_connected() {
			if (!this->_connected) {
				// 2026-11-23: 这行以前无条件打 "Disconnected"，每次按键都会打印，
				// 看起来像 BLE 真的断开了，其实只是「当前没连着」的状态查询。
				// 真正的连接事件在 onConnect()/onDisconnect() 里带地址打印。
				// 降为 DEBUG，避免误导排障。
				ESP_LOGD(TAG, "is_connected: not connected");
				return false;
			}

			return true;
		}

		void BleMiRemote::set_battery_level(uint8_t level) {
			this->batteryLevel = level;
			if (hid != 0)
				this->hid->setBatteryLevel(this->batteryLevel);
		}

		void BleMiRemote::update_timer() {
			this->cancel_timeout(TAG);
			this->set_timeout(TAG, _release_delay, [this]() { this->release(); });
		}


		void BleMiRemote::sendReport(KeyReport *keys) {
			if (this->is_connected()) {
				this->inputKeyboard->setValue((uint8_t*) keys, sizeof(KeyReport));
				this->inputKeyboard->notify();
				this->delay_ms(_delay_ms);
			}
		}

		void BleMiRemote::sendReport(SpecialKeyReport *keys) {
			if (this->is_connected()) {
				this->inputSpecialKeys->setValue((uint8_t*) keys, sizeof(SpecialKeyReport));
				this->inputSpecialKeys->notify();
				this->delay_ms(_delay_ms);
			}
		}

		extern
		const uint8_t _asciimap[128] PROGMEM;

		#define SHIFT 0x80
		const uint8_t _asciimap[128] = {
				0x00,             // NUL
				0x00,             // SOH
				0x00,             // STX
				0x00,             // ETX
				0x00,             // EOT
				0x00,             // ENQ
				0x00,             // ACK
				0x00,             // BEL
				0x2a,			// BS	Backspace
				0x2b,			// TAB	Tab
				0x28,			// LF	Enter
				0x00,             // VT
				0x00,             // FF
				0x00,             // CR
				0x00,             // SO
				0x00,             // SI
				0x00,             // DEL
				0x00,             // DC1
				0x00,             // DC2
				0x00,             // DC3
				0x00,             // DC4
				0x00,             // NAK
				0x00,             // SYN
				0x00,             // ETB
				0x00,             // CAN
				0x00,             // EM
				0x00,             // SUB
				0x00,             // ESC
				0x00,             // FS
				0x00,             // GS
				0x00,             // RS
				0x00,             // US

				0x2c,		   //  ' '
				0x1e | SHIFT,	   // !
				0x34 | SHIFT,	   // "
				0x20 | SHIFT,    // #
				0x21 | SHIFT,    // $
				0x22 | SHIFT,    // %
				0x24 | SHIFT,    // &
				0x34,          // '
				0x26 | SHIFT,    // (
				0x27 | SHIFT,    // )
				0x25 | SHIFT,    // *
				0x2e | SHIFT,    // +
				0x36,          // ,
				0x2d,          // -
				0x37,          // .
				0x38,          // /
				0x27,          // 0
				0x1e,          // 1
				0x1f,          // 2
				0x20,          // 3
				0x21,          // 4
				0x22,          // 5
				0x23,          // 6
				0x24,          // 7
				0x25,          // 8
				0x26,          // 9
				0x33 | SHIFT,      // :
				0x33,          // ;
				0x36 | SHIFT,      // <
				0x2e,          // =
				0x37 | SHIFT,      // >
				0x38 | SHIFT,      // ?
				0x1f | SHIFT,      // @
				0x04 | SHIFT,      // A
				0x05 | SHIFT,      // B
				0x06 | SHIFT,      // C
				0x07 | SHIFT,      // D
				0x08 | SHIFT,      // E
				0x09 | SHIFT,      // F
				0x0a | SHIFT,      // G
				0x0b | SHIFT,      // H
				0x0c | SHIFT,      // I
				0x0d | SHIFT,      // J
				0x0e | SHIFT,      // K
				0x0f | SHIFT,      // L
				0x10 | SHIFT,      // M
				0x11 | SHIFT,      // N
				0x12 | SHIFT,      // O
				0x13 | SHIFT,      // P
				0x14 | SHIFT,      // Q
				0x15 | SHIFT,      // R
				0x16 | SHIFT,      // S
				0x17 | SHIFT,      // T
				0x18 | SHIFT,      // U
				0x19 | SHIFT,      // V
				0x1a | SHIFT,      // W
				0x1b | SHIFT,      // X
				0x1c | SHIFT,      // Y
				0x1d | SHIFT,      // Z
				0x2f,          // [
				0x31,          // bslash
				0x30,          // ]
				0x23 | SHIFT,    // ^
				0x2d | SHIFT,    // _
				0x35,          // `
				0x04,          // a
				0x05,          // b
				0x06,          // c
				0x07,          // d
				0x08,          // e
				0x09,          // f
				0x0a,          // g
				0x0b,          // h
				0x0c,          // i
				0x0d,          // j
				0x0e,          // k
				0x0f,          // l
				0x10,          // m
				0x11,          // n
				0x12,          // o
				0x13,          // p
				0x14,          // q
				0x15,          // r
				0x16,          // s
				0x17,          // t
				0x18,          // u
				0x19,          // v
				0x1a,          // w
				0x1b,          // x
				0x1c,          // y
				0x1d,          // z
				0x2f | SHIFT,    // {
				0x31 | SHIFT,    // |
				0x30 | SHIFT,    // }
				0x35 | SHIFT,    // ~
				0				// DEL
		};

		uint8_t USBPutChar(uint8_t c);

		void BleMiRemote::press(uint8_t k, bool with_timer) {
			// 2026-11-24: the wake advertisement is NOT sent unconditionally
			// any more. It carries the TV's own address in its 0xFE field,
			// and a TV in standby wakes up on that - so blasting it while the
			// TV is AWAKE would (for the POWER key) switch the TV off and
			// then immediately wake it up again.
			//
			// If the link is up, the TV is awake and the key reaches it
			// directly - no wake packet needed. If the link is down, the TV
			// is in standby and the wake packet is exactly what is needed.
			ESP_LOGI(TAG, "press: key=%d connected=%s", (int) k, this->_connected ? "YES" : "NO");

			if (this->is_connected()) {
				if (with_timer) {
					this->update_timer();
				}

				uint8_t i;
				if (k >= 136) {			// it's a non-printing key (not a modifier)
					k = k - 136;
				} else if (k >= 128) {	// it's a modifier key
					_keyReport.modifiers |= (1 << (k - 128));
					k = 0;
				} else {				// it's a printing key
					k = progmem_read_byte(_asciimap + k);
					if (!k) {

						return;
					}
					if (k & 0x80) {						// it's a capital letter or other character reached with shift
						_keyReport.modifiers |= 0x02;	// the left shift modifier
						k &= 0x7F;
					}
				}

				// Add k to the key report only if it's not already present
				// and if there is an empty slot.
				if (_keyReport.keys[0] != k && _keyReport.keys[1] != k && _keyReport.keys[2] != k && _keyReport.keys[3] != k && _keyReport.keys[4] != k && _keyReport.keys[5] != k) {

					for (i = 0; i < 6; i++) {
						if (_keyReport.keys[i] == 0x00) {
							_keyReport.keys[i] = k;
							break;
						}
					}
					if (i == 6) {
						return;
					}
				}
				sendReport (&_keyReport);
			} else {
				// The TV is not reachable over GATT -> it is in standby.
				// This is the moment the wake packet has to go out - but
				// only when the user wants the board to be able to wake the
				// TV (wake_on_press, default true). With it off, a key
				// press in standby does nothing at all and the user turns
				// the TV on by hand.
				//
				// ★ 2026-11-25: 同 pressSpecial() —— 只有 `wake_keys:` 里
				// 的键才能唤醒电视，其余键在待机时什么都不做。
				if (!this->wakeKeyAllowed(k)) {
					ESP_LOGI(TAG, "press: key=%d is not allowed to wake the TV (wake_keys) - ignored while the TV is in standby",
							 (int) k);
					return;
				}
				if (this->_wake_on_press) {
					this->startWakeAdvert();
				}
				this->queuePendingCommand(k, false);
			}
		}

		// Mirrors the wake trick used by github.com/DenizOner/MiPower: instead of
		// this device advertising, act as a BLE central and directly attempt a
		// connection to the (already-bonded) target's MAC address, the same
		// effect as `bluetoothctl pair <mac>`. One-shot, blocking, short timeout.
		void BleMiRemote::connectWakeStart(uint32_t hold_ms) {
			if (hold_ms > 0) {
				this->_connect_wake_hold_ms = hold_ms;
			}
			if (!_has_target_mac) {
				ESP_LOGW(TAG, "connectWakeStart: no target_mac_address configured, skipping");
				return;
			}

			// 2026-11-23: this used to log at DEBUG level, and the board runs
			// the logger at INFO - so the whole wake attempt was SILENT. The
			// only reason "connect_wake" appeared to do nothing was that
			// nothing was ever printed. Everything here is INFO now.
			if (this->is_connected()) {
				ESP_LOGI(TAG, "connectWakeStart: already connected to the TV - nothing to wake");
				return;
			}

			// 2026-11-23: use the bond store's record of the TV when there is
			// one - the address TYPE NimBLE recorded for the peer is the one
			// the HCI command has to carry.
			this->findBondedTarget();
			NimBLEAddress targetAddress = this->peerAddress();
			ESP_LOGI(TAG, "connectWakeStart: connecting to %s (this blocks the loop for up to 3s)", targetAddress.toString().c_str());
			NimBLEClient* pClient = NimBLEDevice::createClient(targetAddress);
			pClient->setSelfDelete(true, true);
			pClient->setConnectTimeout(3000);

			if (!pClient->connect(targetAddress, false, false, false)) {
				ESP_LOGW(TAG, "connectWakeStart: connect attempt failed or timed out");
				return;
			}

			// 2026-11-23 - THE ACTUAL FIX, found by measuring on the real TV:
			// the connection SUCCEEDS even while the TV is powered off (its
			// BLE host stays alive in a low-power wake state - that is exactly
			// how the original remote can switch it on). But the old code
			// disconnected IMMEDIATELY after connecting, so the TV's host
			// never got the chance to notice "a bonded remote just connected"
			// and start the boot sequence. Hold the link open for a while
			// instead - that is the whole mechanism.
			ESP_LOGI(TAG, "connectWakeStart: connected, holding the link for %u ms so the TV can wake up", (unsigned) this->_connect_wake_hold_ms);
			NimBLEClient *client = pClient;
			this->set_timeout("ble_mi_remote_connect_wake", this->_connect_wake_hold_ms, [client]() {
				ESP_LOGI(TAG, "connectWakeStart: hold finished, disconnecting");
				if (client->isConnected()) {
					client->disconnect();
				}
			});
		}

		// 2026-11-23 - A KEY PRESS IS THE WAKE TRIGGER.
		// See the header for why this has to happen even when we think we are
		// connected.
		void BleMiRemote::startWakeAdvert() {
			if (this->_delivering_queued) {
				// The key is being delivered over a link the TV just opened -
				// no need to advertise again.
				return;
			}
			NimBLEAdvertising *adv = pServer->getAdvertising();
			NimBLEAdvertisementData wakeData;
			bool ok = this->buildWakeAdvert(wakeData);
			// 2026-11-23: a pending reconnect burst would fight the wake
			// advertisement - cancel it, the wake burst is the one that
			// matters right now.
			this->cancel_timeout("ble_mi_remote_reconnect_burst");
			adv->setConnectableMode(BLE_GAP_CONN_MODE_UND);
			adv->setHighDutyCycleDirected(false);
			// 20 ms / 30 ms - fast enough for a standby scanner with a narrow
			// window. Never below 0x20: NimBLE's ble_gap_adv_validate()
			// rejects it (rc=3) and the burst would never go out.
			adv->setMinInterval(32);
			adv->setMaxInterval(48);
			bool stopOk = adv->stop();
			bool setOk = adv->setAdvertisementData(wakeData);
			NimBLEAdvertisementData wakeScan;
			wakeScan.setName(this->deviceName);
			bool scanOk = adv->setScanResponseData(wakeScan);
			// NimBLE's ble_gap_adv_validate() rejects a start() that comes
			// too soon after a stop() ("duplicate advertising", rc=3).
			this->delay_ms(20);
			bool startOk = adv->start();

			std::string wakeHex;
			for (uint8_t b : wakeData.getPayload()) {
				char tmp[4];
				snprintf(tmp, sizeof(tmp), "%02X ", b);
				wakeHex += tmp;
			}
			ESP_LOGI(TAG, "startWakeAdvert: wake packet (%u bytes) [%s] stop=%s set=%s scan=%s start=%s",
					 (unsigned) wakeData.getPayload().size(), wakeHex.c_str(),
					 stopOk ? "OK" : "FAILED", setOk ? "OK" : "FAILED",
					 scanOk ? "OK" : "FAILED", startOk ? "OK" : "FAILED");

			// Put the normal advertising back later - the wake burst only has
			// to outlast the TV's scan window.
			//
			// 2026-11-24: 10 s -> 30 s. The TV's standby scanner is
			// PERIODIC, and now that the permanent advertisement no longer
			// carries the 0xFE field, the wake packet is the ONLY thing
			// that can wake it. A short burst can simply miss the window
			// (which is what made waking unreliable before). 30 s covers a
			// full scan period with margin.
			//
			// The burst is also cut short as soon as the TV connects back
			// (see onConnect) - there is no reason to keep sending 0xFE
			// once the TV is awake and talking to us.
			this->cancel_timeout("ble_mi_remote_wake_advert");
			this->set_timeout("ble_mi_remote_wake_advert", 30000, [this]() {
				this->cancel_timeout("ble_mi_remote_power_advert");
				this->powerAdvertStop();
			});
		}

		void BleMiRemote::pressSpecial(uint8_t k, bool with_timer) {
			// 2026-11-24: same rule as press() - the wake advertisement
			// (the packet that carries the TV's own address in its 0xFE field)
			// is only sent when the TV is NOT reachable over GATT, i.e. when
			// it is in standby and needs to be woken.
			//
			// If the link IS up, the TV is awake, the key reaches it
			// directly, and a wake burst would be harmful for POWER: the TV
			// would go to standby and our own 0xFE frames would wake it
			// right back up.
			ESP_LOGI(TAG, "pressSpecial: key=%d connected=%s", (int) k, this->_connected ? "YES" : "NO");

			if (this->is_connected()) {
				if (with_timer) {
					this->update_timer();
				}

				// 2026-11-25: the OK / confirm key does NOT go through the
				// Consumer Control bitmap. See pressEnter() for the details.
				if (k == SPECIAL_MENU_PICK) {
					this->pressEnter();
					return;
				}

			    uint8_t bit = k % 8;
			    uint8_t byte = int(k / 8);

			    _specialKeyReport.keys[byte] |= (1 << bit);

			    ESP_LOGD(TAG, "Send: %d, %d, %d", _specialKeyReport.keys[0], _specialKeyReport.keys[1], _specialKeyReport.keys[2]);

			    sendReport (&_specialKeyReport);
			} else {
				// The TV is in standby (or out of range) -> the wake
				// ADVERTISEMENT is what wakes it: the packet carries the TV's
				// own address in its 0xFE field, the TV's standby scanner
				// recognises it and connects back.
				//
				// Measured on this TV: a fresh wake burst makes the TV boot
				// (the board's advertising is fast and continuous while it
				// is in standby - a 1.28 s on / 1.3 s off duty cycle is NOT
				// enough, the standby scanner misses it).
				//
				// 2026-11-24: only when the user wants the board to be able
				// to wake the TV (wake_on_press, default true).
				//
				// ★ 2026-11-25: 只有 `wake_keys:` 里列出来的键才能唤醒电视 ★
				//
				// 用户实测后的要求：待机时按电源键 → 开机（这是对的）；
				// 但按方向键/音量键**也会**把电视开机，这不对 ——
				// 方向键和音量键是导航键，不该有开机的副作用。
				// 所以现在只有电源键被允许发唤醒广播，其余键在待机时
				// **什么都不做**（连唤醒包都不发，也不排队）。
				// wake_keys 没配置时 = 任意键都能唤醒（老行为）。
				if (!this->wakeKeyAllowed(k)) {
					ESP_LOGI(TAG, "pressSpecial: key=%d is not allowed to wake the TV (wake_keys) - ignored while the TV is in standby",
							 (int) k);
					return;
				}

				if (this->_wake_on_press) {
					this->startWakeAdvert();
				}

				if (k == SPECIAL_POWER) {
					// The key itself is NOT sent again: by the time the TV
					// has connected back it is already awake, and a POWER key
					// at that point would switch it straight back off.
					ESP_LOGI(TAG, "pressSpecial: POWER while disconnected - waking the TV");
				} else {
					this->queuePendingCommand(k, true);
				}
			}
		}

		// 2026-11-25 - THE OK / CONFIRM KEY.
		//
		// ★ 为什么它不能走消费页（Consumer Control）★
		//
		// 我们的报告描述符里，消费页位图的第 0 位是 usage 0x41（Menu Pick）。
		// 在这台电视上实测（adb shell getevent -lt）：
		//
		//   消费页 usage 0x41 → Linux KEY_SELECT (353)
		//
		// 而电视给遥控器用的 keylayout 文件
		// （/system/usr/keylayout/Vendor_2717_Product_32b8.kl —— 原装遥控器
		// 和我们的板子共用同一个）里**没有 353 这一行**，所以这个键被内核
		// 丢掉了：板子日志显示按键正常发出、电视毫无反应。
		//
		// ★ 原装遥控器是怎么做的 ★
		//
		// 电视上能直接读到原装的 HID 报告描述符
		// （/sys/class/hidraw/hidraw1/device/report_descriptor），它的键盘报告
		// 数组第一个 usage 就是 0x28（Enter）：
		//
		//   95 06 75 08 15 28 25 fe 05 07 19 28 29 fe 81 00
		//
		// 电视 dumpsys input 的 RecentQueue 里，原装遥控器按下中间键时记的是：
		//
		//   KeyEvent(deviceId=6, keyCode=23, scanCode=28)
		//                  ↑ DPAD_CENTER   ↑ KEY_ENTER
		//
		// 也就是说：中间键走**键盘页 usage 0x28**，电视把它翻译成
		// DPAD_CENTER（界面里的「确认」；在播放界面就是播放/暂停）。
		//
		// ★ 我们的报告描述符里已经有这个键盘数组 ★
		//
		// 描述符的键盘段和原装**逐字节相同**，只是 Report ID 不同（我们 0x02，
		// 原装 0x01），Report ID 不影响按键翻译。所以这里**不用改描述符**，
		// 也就**不用重新配对**：直接把 0x28 放进键盘报告的第一个槽位即可。
		void BleMiRemote::pressEnter() {
			// 键盘页（0x07）的 usage 0x28 = Enter。
			// 描述符里键盘数组是 6 字节、usage 从 0x28 开始连续排列，
			// 所以 keys[0] 就是 0x28 这一位。
			_keyReport.keys[0] = HID_USAGE_ENTER;
			ESP_LOGI(TAG, "pressEnter: sending keyboard usage 0x%02X (ENTER) - the TV turns this into DPAD_CENTER",
					 HID_USAGE_ENTER);
			sendReport(&_keyReport);
		}

		// own-commits bisection: powerAdvertStart/Data1/Data2/Stop, ported verbatim.
		//
		// 2026-11-23 - two functional fixes on top of the port:
		//
		// (1) BROADCAST MODE IS NOW SET EXPLICITLY. The burst used to call a
		//     bare adv->start(), which resumes whatever advertising mode was
		//     last configured. The reconnect path (fireDirectedBurst) leaves
		//     the stack in BLE_GAP_CONN_MODE_DIR (directed) + high-duty-cycle,
		//     so a "wake broadcast" issued right after a disconnect was
		//     silently transmitted as a DIRECTED advert - and a TV sitting in
		//     standby with a low-power wake scanner is very unlikely to act
		//     on a directed advert it did not initiate. The wake burst now
		//     declares its mode every single time.
		//
		// (2) DIRECTED MODE IS NOW AVAILABLE ON PURPOSE. Some TV firmware
		//     only wakes for a remote it has a bond with, addressed directly.
		//     powerAdvertStart(directed=true) targets the bonded peer.
		//
		// (3) "NAMED" MODE IS NOW AVAILABLE TOO. The classic MiPower packet is
		//     ANONYMOUS. A TV that only wakes for a remote it has bonded with
		//     may instead match on the device name (and/or the HID service
		//     UUID). powerAdvertStart(named=true) builds an advertising
		//     packet that carries the name as well.
		void BleMiRemote::powerAdvertStart(bool directed, bool named) {
			_power_advert_directed = directed && this->_has_target_mac;
			if (directed && !this->_has_target_mac) {
				ESP_LOGW(TAG, "powerAdvertStart: directed requested but no bonded TV MAC known - falling back to undirected");
			}
			_power_advert_named = named;
			// The wake packet is what the original remote sends when a key is
			// pressed, and it is CONNECTABLE - the TV's standby scanner
			// answers by connecting back. Arm the wake mode so we send the
			// HID POWER key over that link.
			//
			// 2026-11-23: NOT when a command is already queued - that command
			// is fired by onConnect() instead, and sending the POWER key as
			// well would be a second, unwanted key press.
			if (!this->_has_pending_command &&
				(this->_power_advert_style == "mi_rc" || this->_power_advert_style == "mi_rc_own" ||
				 this->_power_advert_style == "mi_orig" || this->_power_advert_style == "mi_wake")) {
				this->_wake_send_power_on_connect = true;
				// The TV has to scan, connect back and receive the HID POWER
				// key - give it a real window instead of the 5 second default.
				if (this->_power_advert_cycles < 60) {
					this->_power_advert_cycles = 60;
				}
			}
			ESP_LOGI(TAG, "powerAdvertStart: entered (directed=%s, named=%s, style=%s, known_mac=%s)", this->_power_advert_directed ? "YES" : "NO", this->_power_advert_named ? "YES" : "NO", this->_power_advert_style.c_str(), this->_has_target_mac ? "YES" : "NO");
			_power_advert_cycle = 0;
			this->powerAdvertData1();
		}

		// Starts the advertising burst with the given manufacturer payload.
		// Mode is always set explicitly - see the note in powerAdvertStart().
		bool BleMiRemote::startPowerAdvert(NimBLEAdvertisementData &burstData, const char *label) {
			NimBLEAdvertising *adv = pServer->getAdvertising();
			bool stopOk = adv->stop();

			// Mode first, then data, then start: NimBLE validates the
			// advertising parameters against the mode at start() time.
			adv->setConnectableMode(this->_power_advert_directed ? BLE_GAP_CONN_MODE_DIR : BLE_GAP_CONN_MODE_UND);
			adv->setHighDutyCycleDirected(false);

			bool setOk = burstData.setManufacturerData(this->_power_advert_payload);
			bool applyOk = adv->setAdvertisementData(burstData);
			// Put the same manufacturer data in the scan response too - a
			// standby wake scanner may look at either packet.
			bool scanOk = adv->setScanResponseData(burstData);

			if (this->_power_advert_named) {
				// "Named" variant: the classic MiPower packet is ANONYMOUS.
				// A TV that only wakes for a remote it has bonded with may
				// instead match on the device name (and/or the HID service
				// UUID) - so build an advertising packet that carries all of
				// it. The full 18-byte manufacturer payload does not fit
				// alongside the name inside the 31-byte legacy budget, so
				// the short company-id-only payload goes in the advertising
				// packet and the full payload stays in the scan response.
				//
				//   Flags               3
				//   Complete Local Name 11  ("MI Remote")
				//   manufacturer data    4   (company id 0x0046 only)
				//   Appearance           4
				//   Service UUID 0x1812 4
				//                         ---
				//                          26 bytes  -> fits
				NimBLEAdvertisementData namedData;
				namedData.setFlags(0x06);
				namedData.setName(this->deviceName);
				namedData.setManufacturerData(std::vector<uint8_t>{0x46, 0x00});
				namedData.setAppearance(HID_KEYBOARD);
				namedData.addServiceUUID(hid->getHidService()->getUUID());
				applyOk = adv->setAdvertisementData(namedData) && applyOk;
			}

			if (this->_power_advert_style == "mi_rc" || this->_power_advert_style == "mi_rc_own") {
				// =================================================================
				// 2026-11-23 - THE PACKET, captured from the REAL remote.
				//
				// The board's own BLE sniffer caught the original Xiaomi remote
				// pressing POWER on the (powered-off) TV:
				//
				//   SNIFF D4:B8:FF:7D:AD:6D rssi=-79 advType=0x00 name='MI RC'
				//     mfg=[00 01]
				//     ad=[T01:05 | T03:12 18 | T08:4D 49 20 52 43
				//         | T09:4D 49 20 52 43 | T0A:00 | TFF:00 01]
				//
				// decoded:
				//   Flags                 0x05   (LE General Discoverable +
				//                                  BR/EDR Not Supported)
				//   16-bit Service UUID   0x1812 (HID)
				//   Shortened Local Name  "MI RC"
				//   Complete Local Name   "MI RC"
				//   TX Power              0x00   (0 dBm)
				//   Manufacturer Data     00 01  <-- company id 0x0000, data 0x01
				//
				// >>> THE KEY FACT: the manufacturer data is NOT the MiPower
				// >>> packet (company id 0x0046 + 18 bytes of Mi Box data).
				// >>> That packet is for Mi BOX and this TV never answers to it
				// >>> - which is exactly why every wake attempt failed.
				// >>> The real remote uses company id 0x0000 with a single
				// >>> 0x01 byte. It only advertises when a key is pressed.
				//
				// 29 bytes total - just fits the 31-byte legacy budget.
				// =================================================================
				NimBLEAdvertisementData rcData;
				// setFlags(0x01) -> NimBLE ORs in BR/EDR_NOT_SUPPORTED (0x04)
				// -> 0x05, exactly like the original.
				rcData.setFlags(0x01);
				rcData.addServiceUUID(NimBLEUUID((uint16_t) 0x1812));
				// TX power = 0 dBm, raw AD structure (len, type, value).
				uint8_t txPowerAd[3] = {0x02, 0x0A, 0x00};
				rcData.addData(txPowerAd, 3);
				rcData.setManufacturerData(std::vector<uint8_t>{0x00, 0x01});

				if (this->_power_advert_style == "mi_rc_own") {
					// Same packet but with OUR device name, for TV firmware
					// that matches the bonded remote by name (the TV bonded
					// us as "MI Remote", not "MI RC").
					// NOTE: only the COMPLETE name fits - short + complete
					// would be 36 bytes and blow the 31-byte budget.
					rcData.setName(this->deviceName);
				} else {
					rcData.setShortName("MI RC");
					rcData.setName("MI RC");
				}

				// A TV in standby scans with a narrow window and at a low duty
				// cycle - advertise fast so it cannot miss us.
				// 2026-11-23 FIX: the old values were 20 / 40. NimBLE's
				// ble_gap_adv_validate() rejects itvl_min < 0x20 (32) with
				// BLE_HS_EINVAL (rc=3) because BLE_HIGH_DUTY_ADV_ITVL is off:
				//   E NimBLE: ble_gap_adv_validate rc=3
				//   powerAdvertData*: ... start=FAILED
				// => the wake packet was NEVER actually broadcast, so the TV
				// had nothing to react to. And because setMinInterval() sticks
				// globally on the advertising object, this one bad value also
				// poisoned every later advertise (mipower/mi_rc_own/...).
				// 32 = 20 ms, 48 = 30 ms - legal AND fast enough for a standby
				// scanner. Never go below 0x20 here.
				adv->setMinInterval(32);
				adv->setMaxInterval(48);

				applyOk = adv->setAdvertisementData(rcData) && applyOk;
				scanOk = adv->setScanResponseData(rcData) && scanOk;
				setOk = true;   // payload is built above, not from _power_advert_payload

				// Dump the bytes we are ACTUALLY putting on the air, so they
				// can be compared byte-for-byte with the captured original:
				//   original: T01:05 | T03:12 18 | T08:"MI RC" | T09:"MI RC"
				//             | T0A:00 | TFF:00 01
				std::string rcHex;
				for (uint8_t b : rcData.getPayload()) {
					char tmp[4];
					snprintf(tmp, sizeof(tmp), "%02X ", b);
					rcHex += tmp;
				}
				ESP_LOGI(TAG, "mi_rc wake packet (%u bytes): [%s]", (unsigned) rcData.getPayload().size(), rcHex.c_str());
			}

			if (this->_power_advert_style == "mi_orig") {
				// 2026-11-23 - the same identity the board advertises all the
				// time (see the "mi_orig" branch in setup()), sent as a wake
				// burst. powerAdvertData1/Data2 alternate the manufacturer byte
				// between 0x01 (the original's "key pressed" packet) and 0x00
				// (its idle packet), so a standby scanner that looks for
				// either one finds us within a second.
				NimBLEAdvertisementData origData;
				bool origOk = this->buildOrigAdvert(origData, this->_power_advert_variant, true);
				applyOk = adv->setAdvertisementData(origData) && applyOk;
				// The scan response carries the OTHER variant, so both
				// manufacturer bytes are on the air at the same time.
				NimBLEAdvertisementData origScan;
				bool origScanOk = this->buildOrigAdvert(origScan, (uint8_t) (this->_power_advert_variant ? 0x00 : 0x01), true);
				scanOk = adv->setScanResponseData(origScan) && scanOk;
				setOk = origOk && origScanOk;

				std::string origHex;
				for (uint8_t b : origData.getPayload()) {
					char tmp[4];
					snprintf(tmp, sizeof(tmp), "%02X ", b);
					origHex += tmp;
				}
				ESP_LOGI(TAG, "mi_orig wake packet (%u bytes, mfg byte 0x%02X): [%s]",
						 (unsigned) origData.getPayload().size(), (unsigned) this->_power_advert_variant, origHex.c_str());
			}

			if (this->_power_advert_style == "mi_wake") {
				// 2026-11-23 - the wake packet, see buildWakeAdvert().
				// This is the packet that is known to wake a Xiaomi TV out of
				// standby: the 0xFE field carries the end of the TV's OWN
				// address, so the TV knows the advertisement is meant for it.
				NimBLEAdvertisementData wakeData;
				bool wakeOk = this->buildWakeAdvert(wakeData);
				applyOk = adv->setAdvertisementData(wakeData) && applyOk;
				// Scan response: the complete local name.
				NimBLEAdvertisementData wakeScan;
				bool wakeScanOk = wakeScan.setName(this->deviceName);
				scanOk = adv->setScanResponseData(wakeScan) && scanOk;
				setOk = wakeOk && wakeScanOk;

				std::string wakeHex;
				for (uint8_t b : wakeData.getPayload()) {
					char tmp[4];
					snprintf(tmp, sizeof(tmp), "%02X ", b);
					wakeHex += tmp;
				}
				ESP_LOGI(TAG, "mi_wake packet (%u bytes): [%s]",
						 (unsigned) wakeData.getPayload().size(), wakeHex.c_str());
			}

			bool startOk = false;
			if (this->_power_advert_directed) {
				this->findBondedTarget();
				NimBLEAddress dirAddr = this->peerAddress();
				this->delay_ms(20);
				startOk = adv->start(0, &dirAddr);
			} else {
				startOk = adv->start();
			}
			ESP_LOGI(TAG, "%s: stop=%s setManufacturerData=%s applyOk=%s scanRsp=%s start=%s directed=%s named=%s style=%s", label, stopOk ? "OK" : "FAILED", setOk ? "OK" : "FAILED", applyOk ? "OK" : "FAILED", scanOk ? "OK" : "FAILED", startOk ? "OK" : "FAILED", this->_power_advert_directed ? "YES" : "NO", this->_power_advert_named ? "YES" : "NO", this->_power_advert_style.c_str());
			return startOk;
		}

		void BleMiRemote::powerAdvertData1() {
			// Gap fix 2026-09-03: the normal payload (set in setup()) is
			// already at the 31-byte legacy cap with nothing free, so
			// setManufacturerData() on it was failing on every call,
			// including an empty one - measured on hardware, not a guess
			// (see _normal_advert_data doc comment in the header). Build a
			// fresh, minimal payload instead and swap the whole thing in.
			// Gap fix, second round: stop advertising BEFORE touching the
			// data this time, not after - setAdvertisementData() goes
			// straight to the raw ble_gap_adv_set_data() HCI call with no
			// stopped-first check of its own, and calling it while actively
			// advertising crashed hardware (LoadProhibited) in the first
			// attempt at this fix, which kept the original mutate-then-stop
			// order.
			this->_power_advert_payload = std::vector<uint8_t>{0x46, 0x00, 0xe7, 0x12, 0x97, 0x30, 0x35, 0xf2, 0x78, 0xff, 0xff, 0xff, 0x30, 0x43, 0x52, 0x4b, 0x54, 0x4d};
			// 2026-11-23: the mi_orig style alternates between the original
			// remote's "key pressed" manufacturer byte (0x01) and its idle
			// one (0x00).
			if (this->_power_advert_style == "mi_orig") {
				this->_power_advert_variant = 0x01;
			}
			NimBLEAdvertisementData burstData;
			this->startPowerAdvert(burstData, "powerAdvertData1");
			this->set_timeout("ble_mi_remote_power_advert", _power_advert_delay, [this]() { this->powerAdvertData2(); });
		}

		void BleMiRemote::powerAdvertData2() {
			this->_power_advert_payload = std::vector<uint8_t>{0x46, 0x00};
			// 2026-11-23: the idle half of the mi_orig alternation.
			if (this->_power_advert_style == "mi_orig") {
				this->_power_advert_variant = 0x00;
			}
			NimBLEAdvertisementData burstData;
			this->startPowerAdvert(burstData, "powerAdvertData2");
			if (_power_advert_cycle + 1 >= _power_advert_cycles) {
				this->powerAdvertStop();
			} else {
				_power_advert_cycle++;
				this->set_timeout("ble_mi_remote_power_advert", _power_advert_delay, [this]() { this->powerAdvertData1(); });
			}
		}

		void BleMiRemote::powerAdvertStop() {
			// Restore the real advertising payload (HID appearance/service
			// UUID) that burstData temporarily replaced, instead of trying
			// to clear manufacturer data on it in place.
			// The mode has to be reset too: the burst may have left the stack
			// in directed mode, and a later plain reconnect must not inherit it.
			NimBLEAdvertising *adv = pServer->getAdvertising();
			bool stopOk = adv->stop();
			bool setOk = adv->setAdvertisementData(this->_normal_advert_data);
			bool scanOk = adv->setScanResponseData(this->_normal_scan_data);
			adv->setConnectableMode(BLE_GAP_CONN_MODE_UND);
			adv->setHighDutyCycleDirected(false);
			// Restore the normal advertising interval too. setMinInterval()/
			// setMaxInterval() stick on the advertising object; the wake burst
			// sets a fast interval (32/48), so without this a later reconnect
			// keeps the burst cadence forever.
			// 2026-11-23: 32/48 (20/30 ms) everywhere - the standby scanner
			// needs the fast, continuous advertising.
			adv->setMinInterval(32);   // 32 = 20 ms - legal minimum
			adv->setMaxInterval(48);   // 48 = 30 ms
			bool startOk = adv->start();
			ESP_LOGI(TAG, "powerAdvertStop: stop=%s restoreNormalAdvertData=%s restoreScanData=%s start=%s", stopOk ? "OK" : "FAILED", setOk ? "OK" : "FAILED", scanOk ? "OK" : "FAILED", startOk ? "OK" : "FAILED");
		}

		// Feature 2026-09-04 - see doc comment on the declaration in the
		// header. Only remembers the latest press; a repeated press while
		// still reconnecting overwrites rather than queues multiple.
		void BleMiRemote::queuePendingCommand(uint8_t key, bool is_special) {
			this->_has_pending_command = true;
			this->_pending_is_special = is_special;
			this->_pending_key = key;
			ESP_LOGI(TAG, "queuePendingCommand: key=%d is_special=%s, waiting for the TV to connect back", key, is_special ? "true" : "false");
			// 2026-11-23: the wake advertisement was already sent by
			// press()/pressSpecial() - everything a key press does.
			// The key itself goes out over the link the TV opens (onConnect).
		}

		// Manual recovery action - see the doc comment on the declaration in
		// ble_mi_remote.h. Cancel any still-scheduled HD-burst retry first:
		// if one were still pending (mid its own 30s window), it would fire
		// later and call fireDirectedBurst(), silently undoing this and
		// reverting advertising back to directed-only.
		//
		// Also deleteAllBonds() before opening up - matches the pre-bisection
		// esp-idf design (2026-08-25 bond-preservation redesign) that this
		// action was reconstructed from: a human pressing this button is
		// explicit intent to force a totally fresh pairing, so don't rely on
		// a new pairing merely superseding a stale local bond entry on its
		// own - clear it up front instead.
		// 2026-11-23 - THE SNIFFER.
		// The decisive experiment for "wake the TV": with the TV powered OFF,
		// listen to every BLE advertisement in the air and dump the raw
		// bytes. Then press POWER on the ORIGINAL remote - whatever packet it
		// sends is the one we have to imitate. The MiPower packet we have
		// been firing is the Mi BOX one and this TV does not answer to it.
		void BleMiRemote::sniffStart(uint32_t seconds) {
			if (seconds == 0) {
				seconds = 30;
			}
			NimBLEScan *scan = NimBLEDevice::getScan();
			scan->setScanCallbacks(this, true);   // wantDuplicates = true
			scan->setActiveScan(true);            // also collect scan responses
			scan->setInterval(100);
			scan->setWindow(99);
			scan->clearResults();

			uint32_t ms = seconds * 1000;
			bool ok = scan->start(ms, false, false);
			this->_sniffing = ok;
			ESP_LOGI(TAG, "sniffStart: scanning for %u s, started=%s (our own advertising is suspended while scanning)", (unsigned) seconds, ok ? "OK" : "FAILED");
			if (!ok) {
				return;
			}
			this->cancel_timeout("ble_mi_remote_sniff");
			this->set_timeout("ble_mi_remote_sniff", ms + 1500, [this]() { this->sniffStop(); });
		}

		void BleMiRemote::sniffStop() {
			this->cancel_timeout("ble_mi_remote_sniff");
			if (!this->_sniffing) {
				ESP_LOGI(TAG, "sniffStop: was not scanning");
				return;
			}
			NimBLEScan *scan = NimBLEDevice::getScan();
			scan->stop();
			this->_sniffing = false;
			ESP_LOGI(TAG, "sniffStop: stopped, restoring normal advertising");
			// Put the board back on the air so the TV can find it again.
			this->startPlainAdvertising();
		}

		void BleMiRemote::onResult(const NimBLEAdvertisedDevice *device) {
			if (device == nullptr) {
				return;
			}

			std::string name = device->getName();

			std::string mfgHex;
			std::string mfg = device->getManufacturerData();
			for (unsigned char c : mfg) {
				char tmp[4];
				snprintf(tmp, sizeof(tmp), "%02X ", (unsigned char) c);
				mfgHex += tmp;
			}

			// Dump the raw bytes of every AD structure we know about, so the
			// exact on-air packet can be reconstructed from the log.
			static const uint16_t kAdTypes[] = {
				0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
				0x09, 0x0A, 0x0D, 0x16, 0x20, 0x21, 0x22, 0xFE, 0xFF
			};
			std::string ad;
			for (uint16_t t : kAdTypes) {
				std::string d = device->getPayloadByType(t);
				if (d.empty()) {
					continue;
				}
				char head[8];
				snprintf(head, sizeof(head), "T%02X:", (unsigned) t);
				ad += head;
				for (unsigned char c : d) {
					char h[4];
					snprintf(h, sizeof(h), "%02X ", (unsigned char) c);
					ad += h;
				}
				ad += "| ";
			}

			// 2026-11-23 - dump the COMPLETE raw payload, not just the AD
			// types we happen to know about. This is what hid the wake field
			// (AD type 0xFE) and the device-class field (0x0D) from us for
			// hours: both were in the air the whole time, but the fixed type
			// list below did not contain them, so they never showed up in
			// the log.
			std::string raw;
			for (uint8_t b : device->getPayload()) {
				char tmp[4];
				snprintf(tmp, sizeof(tmp), "%02X", b);
				raw += tmp;
			}

			ESP_LOGI(TAG, "SNIFF %s rssi=%d advType=0x%02X name='%s' mfg=[%s] ad=[%s] raw=[%s]",
					device->getAddress().toString().c_str(),
					(int) device->getRSSI(),
					(unsigned) device->getAdvType(),
					name.c_str(),
					mfgHex.c_str(),
					ad.c_str(),
					raw.c_str());
		}

		void BleMiRemote::plainAdvertStart() {
			this->cancel_timeout("ble_mi_remote_reconnect_burst");
			bool deleteOk = NimBLEDevice::deleteAllBonds();
			ESP_LOGI(TAG, "plainAdvertStart: manual override, deleteAllBonds()=%s, forcing plain/discoverable advertising", deleteOk ? "OK" : "FAILED");
			this->startPlainAdvertising();
		}

		// 2026-11-23: same as plainAdvertStart() but keeps the bond - the
		// TV rebooted, the bond is still valid, we only need to make sure the
		// board is broadcasting in a way the TV's reconnect scan will find.
		void BleMiRemote::reconnectAdvertStart() {
			this->cancel_timeout("ble_mi_remote_reconnect_burst");
			ESP_LOGI(TAG, "reconnectAdvertStart: forcing plain undirected advertising (bond kept)");
			this->startPlainAdvertising();
		}

		void BleMiRemote::release() {
			if (this->is_connected()) {
				this->cancel_timeout(TAG);

				_keyReport.keys[0] = 0;
				_keyReport.keys[1] = 0;
				_keyReport.keys[2] = 0;
				_keyReport.keys[3] = 0;
				_keyReport.keys[4] = 0;
				_keyReport.keys[5] = 0;
				_keyReport.modifiers = 0;
				_specialKeyReport.keys[0] = 0;
				_specialKeyReport.keys[1] = 0;
				_specialKeyReport.keys[2] = 0;
				sendReport (&_keyReport);
				sendReport (&_specialKeyReport);
			}
		}

		void BleMiRemote::onConnect(NimBLEServer *pServer, NimBLEConnInfo& connInfo) {
			this->_connected = true;

			// 2026-11-23 诊断：连接建立时无条件打印对端地址和加密状态。
			// 之前这条路径完全没有日志，导致「电视连上了但按键没反应」时
			// 根本看不出到底连没连上。
			ESP_LOGI(TAG, "onConnect: peer=%s bonded=%s authenticated=%s",
					 connInfo.getAddress().toString().c_str(),
					 connInfo.isBonded() ? "YES" : "NO",
					 connInfo.isAuthenticated() ? "YES" : "NO");

			// 2026-11-24: the TV connected back - the wake burst has done its
			// job, so stop sending the 0xFE packet and go back to the idle
			// advertisement. Otherwise we would keep pointing at the TV's own
			// address for the rest of the burst window, and a TV that goes
			// back to standby in that window would wake itself up again.
			//
			// Deferred by a few hundred ms: this runs inside a NimBLE host
			// callback, and adv->stop()/start() must not be called from
			// there.
			this->set_timeout("ble_mi_remote_wake_stop", 300, [this]() {
				if (this->cancel_timeout("ble_mi_remote_wake_advert")) {
					ESP_LOGI(TAG, "onConnect: TV is back - stopping the wake burst");
					this->cancel_timeout("ble_mi_remote_power_advert");
					this->powerAdvertStop();
				}
			});

			// own-commits bisection stage 2/5: peripheral-initiated pairing.
			// Ported from esp-idf branch's onConnect() (4e3dd6e) - request
			// security ourselves on an unbonded connect rather than waiting
			// for the peer, since NimBLEHIDDevice's NOTIFY property isn't
			// ENC-gated so a central is never forced to bond on its own.
			if (!connInfo.isBonded()) {
				int rc = 0;
				bool startOk = NimBLEDevice::startSecurity(connInfo.getConnHandle(), &rc);
				ESP_LOGI(TAG, "onConnect: not bonded, requesting security: startSecurity()=%s rc=%d", startOk ? "OK" : "FAILED", rc);
			}

			// own-commits bisection stage 3/5
			this->learnTargetMac(connInfo.getAddress());

			// Feature 2026-09-04: fire a command that was queued while
			// disconnected (see queuePendingCommand()) now that we're
			// actually reconnected. Gated on isBonded() - only fire for a
			// RESUMED connection to an already-known peer, not a fresh
			// pairing that still needs its own security handshake first
			// (startSecurity() above, async) - NOTIFY isn't ENC-gated, so
			// sending this too early could get silently dropped by the
			// peer the same way the original onConnect()/HID-NOTIFY bug
			// this whole project started from did. The trailing release()
			// below cleans it up either way (also gated on is_connected(),
			// so harmless if nothing fired here).
			// NOT yet verified on real hardware whether isBonded() here is
			// actually early enough to guarantee delivery - needs a real
			// disconnect/reconnect/press test, not just reasoning.
			if (this->_has_pending_command && connInfo.isBonded()) {
				this->_has_pending_command = false;
				ESP_LOGI(TAG, "onConnect: firing queued command key=%d is_special=%s", this->_pending_key, this->_pending_is_special ? "true" : "false");
				// 2026-11-23: this key goes out over the link the TV just
				// opened - it must not trigger another wake advertisement.
				this->_delivering_queued = true;
				if (this->_pending_is_special) {
					this->pressSpecial(this->_pending_key);
				} else {
					this->press(this->_pending_key);
				}
				this->_delivering_queued = false;
			}

			// 2026-11-23 - WAKE MODE.
			// The captured original remote sends a CONNECTABLE advertising
			// packet (advType 0x00) when a key is pressed, and the TV's
			// standby scanner answers by connecting back. So the wake sequence
			// is: advertise that packet -> the TV connects -> we send the HID
			// POWER key over the freshly established link -> the TV boots.
			if (this->_wake_send_power_on_connect) {
				this->_wake_send_power_on_connect = false;
				ESP_LOGI(TAG, "onConnect: wake mode - the TV connected back, sending the HID POWER key in 800 ms");
				this->set_timeout("ble_mi_remote_wake_power", 800, [this]() {
					ESP_LOGI(TAG, "wake mode: sending POWER key to the TV");
					this->_delivering_queued = true;
					this->pressSpecial(SPECIAL_POWER, false);
					this->_delivering_queued = false;
					this->set_timeout("ble_mi_remote_wake_release", 1200, [this]() {
						this->release();
					});
				});
			}

			release();
		}

		// own-commits bisection stage 3/5: ported from esp-idf branch
		// (loadTargetMac/learnTargetMac/startPlainAdvertising/startReconnectAdvert),
		// minus the HD-burst call in startReconnectAdvert (stage 4) - falls back
		// to plain advertising even when bonded, for now.
		void BleMiRemote::loadTargetMac() {
			this->_target_mac_pref = global_preferences->make_preference<uint64_t>(fnv1_hash("ble_mi_remote_target_mac"));

			if (this->_target_mac_from_config) {
				ESP_LOGI(TAG, "loadTargetMac: using target_mac_address from config: %s", NimBLEAddress(this->_target_mac, target_addr_type()).toString().c_str());
				return;
			}

			uint64_t stored = 0;
			if (this->_target_mac_pref.load(&stored) && stored != 0) {
				this->_target_mac = stored;
				this->_has_target_mac = true;
				ESP_LOGI(TAG, "loadTargetMac: loaded learned target %s from flash", NimBLEAddress(stored, (((stored >> 40) & 0xC0) == 0xC0) ? BLE_ADDR_RANDOM : BLE_ADDR_PUBLIC).toString().c_str());
			} else {
				ESP_LOGI(TAG, "loadTargetMac: no target_mac_address configured and nothing learned yet");
			}
		}

		void BleMiRemote::learnTargetMac(NimBLEAddress addr) {
			if (this->_target_mac_from_config) {
				return;
			}

			uint64_t mac = (uint64_t) addr;
			if (mac == 0 || mac == this->_target_mac) {
				return;
			}

			this->_target_mac = mac;
			this->_has_target_mac = true;

			bool ok = this->_target_mac_pref.save(&mac);
			ESP_LOGI(TAG, "learnTargetMac: learned peer %s, saved to flash=%s", addr.toString().c_str(), ok ? "OK" : "FAILED");
		}

		// 2026-11-23 - build the advertising payload that mimics the packet the
		// ORIGINAL Xiaomi remote sends. See the header for the captured bytes
		// and for why the manufacturer data is the decisive part.
		bool BleMiRemote::buildOrigAdvert(NimBLEAdvertisementData &data, uint8_t mfgByte, bool useOwnName) {
			bool ok = true;
			// setFlags(0x01) -> NimBLE ORs in BR/EDR_NOT_SUPPORTED (0x04)
			// -> 0x05, exactly like the original.
			ok = data.setFlags(0x01) && ok;
			ok = data.addServiceUUID(NimBLEUUID((uint16_t) 0x1812)) && ok;
			ok = data.setShortName("MI RC") && ok;
			if (useOwnName) {
				// The complete local name has to be the name the TV bonded us
				// under, otherwise a scanner that matches by name misses us.
				ok = data.setName(this->deviceName) && ok;
			} else {
				ok = data.setName("MI RC") && ok;
			}
			// Manufacturer data: company id 0x0000 + one data byte.
			ok = data.setManufacturerData(std::vector<uint8_t>{0x00, mfgByte}) && ok;
			return ok;
		}

		void BleMiRemote::set_target_mac_address(const std::string &addr) {
			uint64_t mac = 0;
			int n = 0;
			for (const char *p = addr.c_str(); *p && n < 6; ) {
				mac = (mac << 8) | (uint64_t) (uint8_t) strtoul(p, (char**) &p, 16);
				n++;
				while (*p == ':' || *p == '-') {
					p++;
				}
			}
			if (n != 6) {
				ESP_LOGW(TAG, "set_target_mac_address: '%s' is not a BLE address - ignoring", addr.c_str());
				return;
			}
			this->_target_mac = mac;
			this->_has_target_mac = true;
			this->_target_mac_from_config = true;
		}

		// 2026-11-23 - THE WAKE PACKET. See the header for the full byte
		// layout and for why the 0xFE field (the end of the TV's own address)
		// is the part that actually wakes the TV.
		bool BleMiRemote::buildWakeAdvert(NimBLEAdvertisementData &data) {
			bool ok = true;
			// 02 01 05 - Flags: LE general discoverable + BR/EDR not
			// supported (NimBLE ORs the 0x04 bit in, like the original).
			ok = data.setFlags(0x01) && ok;
			// 03 FF 00 01 - Manufacturer data, company id 0x0000, data 0x01.
			ok = data.setManufacturerData(std::vector<uint8_t>{0x00, 0x01}) && ok;
			// 06 08 "MI RC" - Shortened local name.
			ok = data.setShortName("MI RC") && ok;
			// 03 02 12 18 - 16-bit service UUID 0x1812 (HID), as the
			// INCOMPLETE 16-bit UUID list (AD type 0x02).
			// The original remote uses type 0x02, NOT the 0x03 "complete
			// list" that NimBLE's addServiceUUID() would emit - the two
			// differ by one byte, and the whole point here is to be
			// byte-identical to the packet that is known to work.
			static const uint8_t uuidAd[4] = {0x03, 0x02, 0x12, 0x18};
			ok = data.addData(uuidAd, 4) && ok;
			// 04 0D 04 05 00 - the remote's device-class field (raw AD
			// structure: length, type, value).
			static const uint8_t classAd[5] = {0x04, 0x0D, 0x04, 0x05, 0x00};
			ok = data.addData(classAd, 5) && ok;
			// 02 0A 00 - TX power 0 dBm (raw AD structure).
			static const uint8_t txPowerAd[3] = {0x02, 0x0A, 0x00};
			ok = data.addData(txPowerAd, 3) && ok;
			// 04 FE <tv5> <tv4> <tv3> - Xiaomi's wake field.
			if (this->_has_target_mac) {
				// _target_mac is the TV's address as an integer, most
				// significant byte first. The wake field carries the LAST
				// three bytes of the address, reversed:
				//   TV C8:28:32:62:77:AA  ->  AA 77 62
				uint8_t wakeAd[5] = {
					0x04, 0xFE,
					(uint8_t) (this->_target_mac & 0xFF),
					(uint8_t) ((this->_target_mac >> 8) & 0xFF),
					(uint8_t) ((this->_target_mac >> 16) & 0xFF)
				};
				ok = data.addData(wakeAd, 5) && ok;
			} else {
				ESP_LOGW(TAG, "buildWakeAdvert: no TV address known yet - the wake field (0xFE) is missing");
			}
			return ok;
		}

		// 2026-11-24 - THE IDLE PACKET. See the header for why the wake
		// packet (0xFE) must NOT be the permanent advertisement.
		bool BleMiRemote::buildIdleAdvert(NimBLEAdvertisementData &data) {
			bool ok = true;
			// 02 01 05 - Flags (NimBLE ORs in BR/EDR_NOT_SUPPORTED).
			ok = data.setFlags(0x01) && ok;
			// 03 FF 00 00 - Manufacturer data, company id 0x0000, data 0x00.
			// The 0x00 is what the original remote sends when it is NOT
			// pressing a key (0x01 = "key pressed").
			ok = data.setManufacturerData(std::vector<uint8_t>{0x00, 0x00}) && ok;
			// 06 08 "MI Remote" - our shortened local name. The TV's device
			// list only ever showed the board under this name, never "MI RC".
			ok = data.setShortName(this->deviceName) && ok;
			// 03 03 12 18 - 16-bit service UUID 0x1812 (HID) as the
			// COMPLETE list (AD type 0x03) - that is what the original's
			// idle packet uses (its key-pressed packet uses 0x02).
			static const uint8_t uuidAd[4] = {0x03, 0x03, 0x12, 0x18};
			ok = data.addData(uuidAd, 4) && ok;
			// 04 0D 04 05 00 - the remote's device-class field.
			static const uint8_t classAd[5] = {0x04, 0x0D, 0x04, 0x05, 0x00};
			ok = data.addData(classAd, 5) && ok;
			// 02 0A 00 - TX power 0 dBm.
			static const uint8_t txPowerAd[3] = {0x02, 0x0A, 0x00};
			ok = data.addData(txPowerAd, 3) && ok;
			// ★ NO 0xFE FIELD. That is the whole point of this packet:
			// without the TV's own address in there, the TV does not wake.
			return ok;
		}

		// 2026-11-23 - REAL BUG FIX, see the header.
		// NimBLEDevice::isBonded() compares the address TYPE first
		// (NimBLEAddress::operator==), and the type the bond store recorded
		// for this TV (0 = public) does not match the type inferred from the
		// address bits (C8:... -> top two bits 11 = random static). The
		// comparison therefore NEVER matched, and startReconnectAdvert()
		// always fell back to plain advertising - the HD directed burst it is
		// built around has never actually run in this project.
		// Look the peer up by ADDRESS BYTES instead and keep the record the
		// store holds, so every later peer operation uses the same one.
		bool BleMiRemote::findBondedTarget() {
			this->_has_bonded_target = false;
			if (!this->_has_target_mac) {
				return false;
			}
			int maxBonds = MYNEWT_VAL(BLE_STORE_MAX_BONDS);
			if (maxBonds <= 0) {
				maxBonds = 4;
			}
			NimBLEAddress wanted(this->_target_mac, target_addr_type());
			const uint8_t *wantVal = wanted.getVal();

			for (int i = 0; i < maxBonds; i++) {
				NimBLEAddress stored = NimBLEDevice::getBondedAddress(i);
				if (stored.isNull()) {
					continue;
				}
				if (memcmp(stored.getVal(), wantVal, 6) == 0) {
					this->_bonded_target = stored;
					this->_has_bonded_target = true;
					ESP_LOGI(TAG, "findBondedTarget: %s is bonded (store type=%d, address bits say=%d)",
							 stored.toString().c_str(), (int) stored.getType(),
							 (int) target_addr_type());
					return true;
				}
			}
			ESP_LOGI(TAG, "findBondedTarget: no bond for %s", wanted.toString().c_str());
			return false;
		}

		NimBLEAddress BleMiRemote::peerAddress() const {
			if (this->_has_bonded_target) {
				return this->_bonded_target;
			}
			return NimBLEAddress(this->_target_mac, target_addr_type());
		}

		void BleMiRemote::startPlainAdvertising() {
			NimBLEAdvertising *adv = pServer->getAdvertising();
			adv->setConnectableMode(BLE_GAP_CONN_MODE_UND);
			// own-commits bisection stage 4/5: reset the sticky HD flag now
			// that fireDirectedBurst() below can set it.
			adv->setHighDutyCycleDirected(false);
			// 2026-11-23: FAST and CONTINUOUS.
			//
			// The board is mains-powered, so there is no reason to save
			// advertising energy - and it matters a lot: a TV in standby
			// scans at a low duty cycle, and with the old on/off pattern
			// (1.28 s on, 1.3 s off) it regularly missed us.
			//
			// 2026-11-24: this no longer advertises the wake packet - it
			// keeps whatever advertisement data is current, which is the
			// IDLE packet (no 0xFE field) unless a wake burst is running.
			adv->setMinInterval(32);   // 20 ms
			adv->setMaxInterval(48);   // 30 ms
			bool stopOk = adv->stop();
			bool startOk = adv->start();
			ESP_LOGI(TAG, "startPlainAdvertising: stop=%s start=%s (undirected, ADV_IND, 20/30 ms, continuous)", stopOk ? "OK" : "FAILED", startOk ? "OK" : "FAILED");
		}

		// own-commits bisection stage 4/5: now uses real HD-burst when bonded,
		// ported from esp-idf branch's startReconnectAdvert()/fireDirectedBurst().
		void BleMiRemote::startReconnectAdvert() {
			if (!this->_has_target_mac) {
				ESP_LOGI(TAG, "startReconnectAdvert: no target_mac_address learned yet, falling back to plain advertising");
				this->startPlainAdvertising();
				return;
			}

			// 2026-11-23: the bond lookup has to come FIRST - peerAddress()
			// returns the bond store's record once the bond is known.
			if (!this->findBondedTarget()) {
				ESP_LOGI(TAG, "startReconnectAdvert: no saved bond for %s, falling back to plain advertising", this->peerAddress().toString().c_str());
				this->startPlainAdvertising();
				return;
			}
			NimBLEAddress dirAddr = this->peerAddress();

			this->_reconnect_retry_until_ms = millis() + 30000;
			ESP_LOGI(TAG, "startReconnectAdvert: bonded to %s -> starting HD-burst retry (30s window)", dirAddr.toString().c_str());
			this->fireDirectedBurst();
		}

		void BleMiRemote::fireDirectedBurst() {
			NimBLEAdvertising *adv = pServer->getAdvertising();
			NimBLEAddress dirAddr = this->peerAddress();
			// 2026-11-23 - THE ADVERTISING EVENT TYPE MATTERS.
			//
			// A DIRECTED connectable advertisement is a different advertising
			// event type on the air: ADV_DIRECT_IND (0x04), not ADV_IND
			// (0x00). The original remote sends ADV_IND (that is what the
			// board's own sniffer recorded: advType=0x00), and a TV in
			// standby is looking for exactly that event type - a directed
			// burst is simply ignored by it.
			//
			// So the reconnect burst stays UNDIRECTED, like the original
			// remote. The address is still learned and logged (it is what
			// the wake packet's 0xFE field is built from), it is just not
			// used to aim the advertising.
			adv->setConnectableMode(BLE_GAP_CONN_MODE_UND);
			adv->setHighDutyCycleDirected(false);
			bool stopOk = adv->stop();
			// Real bug, found 2026-09-04 on real hardware against the real
			// Mi TV (a bisect-test round had never caught this - it needs
			// an actual disconnect/reconnect cycle to surface, which the
			// queued-command feature's own test finally exercised): NimBLE
			// host logs "E NimBLE: ble_gap_adv_validate rc=3" (BLE_HS_EINVAL)
			// periodically here - per the actual NimBLE source, the most
			// likely cause is ble_gap_adv_validate seeing the PREVIOUS
			// advertising op not yet cleared ("duplicate advertising") -
			// stop()'s host-side call returning OK doesn't guarantee the
			// controller has already settled that state before the very
			// next start() call fires. A real reconnect test with the TV
			// confirmed genuinely reachable failed end to end (two full 30s
			// windows, zero successful connects) while this was recurring.
			// Small settle delay as a first pragmatic mitigation - exact
			// value not verified, just a starting guess.
			this->delay_ms(20);
			// 2026-11-23: CONTINUOUS, not a 1.28 s burst. See
			// startPlainAdvertising() for why the duty cycle matters.
			bool startOk = adv->start();
			ESP_LOGI(TAG, "fireDirectedBurst: continuous undirected burst (ADV_IND, 20/30 ms) for %s, stop=%s start=%s, retry_remaining_ms=%d", dirAddr.toString().c_str(), stopOk ? "OK" : "FAILED", startOk ? "OK" : "FAILED", (int) (this->_reconnect_retry_until_ms - millis()));

			this->set_timeout("ble_mi_remote_reconnect_burst", 10000, [this]() {
				if (this->_connected) {
					ESP_LOGI(TAG, "fireDirectedBurst: already connected - nothing to do");
					return;
				}

				if ((int32_t) (millis() - this->_reconnect_retry_until_ms) < 0) {
					this->fireDirectedBurst();
					return;
				}

				// Real regression, fixed 2026-11-23: the old code stopped
				// advertising completely here ("manual plain_advert needed
				// to resume"). In practice that made the board INVISIBLE
				// to the TV forever:
				//   * the TV's own reconnect scan only runs for a short
				//     window after boot,
				//   * and if the board had already burned its 30s
				//     directed-burst window before the TV was back up, the
				//     TV found nothing to connect to -> the bond was never
				//     re-established -> every key press went nowhere.
				// Falling back to plain undirected advertising keeps the
				// board discoverable at all times. The original fear
				// (a stray pairing stealing the bond) is a much smaller
				// risk than never reconnecting at all.
				ESP_LOGI(TAG, "fireDirectedBurst: retry window exhausted - falling back to plain undirected advertising (stay discoverable)");
				this->startPlainAdvertising();
			});
		}

		void BleMiRemote::onDisconnect(NimBLEServer *pServer, NimBLEConnInfo& connInfo, int reason) {
			this->_connected = false;

			ESP_LOGI(TAG, "onDisconnect: %s reason=0x%02x bonded=%s authenticated=%s",
					 connInfo.getAddress().toString().c_str(), (unsigned) reason,
					 connInfo.isBonded() ? "YES" : "NO",
					 connInfo.isAuthenticated() ? "YES" : "NO");

			// own-commits bisection stage 4/5: cancel any still-pending
			// HD-burst retry from a sequence that hadn't finished its own 30s
			// window yet.
			this->cancel_timeout("ble_mi_remote_reconnect_burst");

			if (!this->_reconnect || !this->_should_readvertise) {
				return;
			}

			// 2026-11-23 关键 bug 修复：
			// 旧代码在这里判断「对端主动断开」(REM_USER_CONN_TERM) 就调用
			// deleteBond() 删掉配对。但 BLE HID 设备休眠时，电视**正常**就会
			// 主动断开连接（这是标准省电行为，原装遥控器也一样）。
			// 结果：每次电视休眠 → 板子删 bond → 再也无法自动重连 →
			// 用户每次都要重新配对。这就是「断联」的真正根因！
			// 修复：任何原因断开都保留 bond，走 startReconnectAdvert()
			// 用定向广播/快速广播让电视重连。
			if (reason == BLE_HS_ERR_HCI_BASE + BLE_ERR_REM_USER_CONN_TERM) {
				ESP_LOGI(TAG, "onDisconnect: peer terminated link normally (reason=0x%02x), KEEP bond and re-advertise for reconnect", (unsigned) reason);
			}

			this->startReconnectAdvert();
		}

		void BleMiRemote::onWrite(NimBLECharacteristic *me, NimBLEConnInfo& connInfo) {
			uint8_t *value = (uint8_t*) (me->getValue().c_str());
			(void) value;
			ESP_LOGD(TAG, "special keys: %d", *value);
		}

		void BleMiRemote::delay_ms(uint64_t ms) {
			uint64_t m = esp_timer_get_time();
			if (ms) {
				uint64_t e = (m + (ms * 1000));
				if (m > e) { //overflow
					while (esp_timer_get_time() > e) {
					}
				}
				while (esp_timer_get_time() < e) {
				}
			}
		}
	}  // namespace ble_mi_remote
}  // namespace esphome

#endif
