
#ifdef USE_ESP32

#include "button.h"
#include "esphome/core/log.h"
#include <string>

namespace esphome {
	namespace ble_mi_remote {
		static const char *const TAG = "ble_mi_remote";

		void BleMiRemoteButton::press_action() {
			// 2026-11-23: log every press at INFO. The press path used to be
			// completely silent, which made "the button returns 200 OK but
			// nothing happens" impossible to tell apart from "the key was
			// sent and the TV ignored it".
			ESP_LOGI(TAG, "button press: value=%d", (int) value_);
			if (value_ > -1) {
				parent_->pressSpecial((uint8_t) value_);
			} else {
				parent_->release();
			}
		}
	}  // namespace ble_mi_remote
}  // namespace esphome

#endif
