#pragma once

#ifdef USE_ESP32

#include "esphome/core/component.h"
#include "esphome/core/automation.h"
#include "ble_mi_remote.h"
#include <string>

namespace esphome {
	namespace ble_mi_remote {
		template<typename... Ts> class BleMiRemotePressAction : public Action<Ts...> {
			public:
				explicit BleMiRemotePressAction(BleMiRemote *ble_mi_remote) : ble_mi_remote_(ble_mi_remote) {}
				TEMPLATABLE_VALUE(uint8_t, key)
				TEMPLATABLE_VALUE(uint8_t, special)

				// 2026-11-23 - REAL BUG.
				// TemplatableValue::has_value() cannot be used to tell "the
				// YAML set this one" from "nothing was set here": a
				// default-constructed TemplatableValue still reports a
				// value. The old play() therefore took the `key_` branch
				// even when only `special_` had been set, and called
				// press(0) - key 0 is a PRINTING key whose table entry is 0,
				// so press() returned silently and NOTHING happened.
				// That is why every press through this action (and through
				// the template buttons built on it) produced no log and no
				// effect at all.
				// The YAML now says explicitly which of the two to use.
				void set_use_special(bool v) { this->use_special_ = v; }

				// with_timer=false -> do NOT arm the auto-release timer, so the key
				// stays held until an explicit ble_mi_remote.release action runs.
				// That is what makes a real HID long-press possible (the TV's
				// long-press power to shut down). Default true keeps the
				// original press-and-auto-release behaviour.
				void set_with_timer(bool with_timer) { this->with_timer_ = with_timer; }

				void play(const Ts&... x) override {
					if (this->use_special_) {
						this->ble_mi_remote_->pressSpecial(this->special_.value(x...), this->with_timer_);
					} else {
						this->ble_mi_remote_->press(this->key_.value(x...), this->with_timer_);
					}
				}
			protected:
				BleMiRemote *ble_mi_remote_;
				bool with_timer_{true};
				bool use_special_{false};
		};

		template<typename... Ts> class BleMiRemoteReleaseAction : public Action<Ts...> {
			public:
				explicit BleMiRemoteReleaseAction(BleMiRemote *ble_mi_remote) : ble_mi_remote_(ble_mi_remote) {}

				void play(const Ts&... x) override { this->ble_mi_remote_->release(); }

			protected:
				BleMiRemote *ble_mi_remote_;
		};

		template<typename... Ts> class BleMiRemoteStartAction : public Action<Ts...> {
			public:
				explicit BleMiRemoteStartAction(BleMiRemote *ble_mi_remote) : ble_mi_remote_(ble_mi_remote) {}

				void play(const Ts&... x) override { this->ble_mi_remote_->start(); }

			protected:
				BleMiRemote *ble_mi_remote_;
		};

		template<typename... Ts> class BleMiRemoteConnectWakeAction : public Action<Ts...> {
			public:
				explicit BleMiRemoteConnectWakeAction(BleMiRemote *ble_mi_remote) : ble_mi_remote_(ble_mi_remote) {}

				// How long to keep the link to the (powered-off) TV open.
				// The TV's BLE host needs the connection to STAY up to notice
				// it and start booting.
				void set_hold_ms(uint32_t hold_ms) { this->hold_ms_ = hold_ms; }

				void play(const Ts&... x) override { this->ble_mi_remote_->connectWakeStart(this->hold_ms_); }

			protected:
				BleMiRemote *ble_mi_remote_;
				uint32_t hold_ms_{12000};
		};

		template<typename... Ts> class BleMiRemotePlainAdvertAction : public Action<Ts...> {
			public:
				explicit BleMiRemotePlainAdvertAction(BleMiRemote *ble_mi_remote) : ble_mi_remote_(ble_mi_remote) {}

				void play(const Ts&... x) override { this->ble_mi_remote_->plainAdvertStart(); }

			protected:
				BleMiRemote *ble_mi_remote_;
		};

		// 2026-11-23: force plain undirected advertising, keeping the bond.
		// (plain_advert drops the bond - different, much heavier action.)
		template<typename... Ts> class BleMiRemoteReconnectAdvertAction : public Action<Ts...> {
			public:
				explicit BleMiRemoteReconnectAdvertAction(BleMiRemote *ble_mi_remote) : ble_mi_remote_(ble_mi_remote) {}

				void play(const Ts&... x) override { this->ble_mi_remote_->reconnectAdvertStart(); }

			protected:
				BleMiRemote *ble_mi_remote_;
		};

		// 2026-11-23: BLE sniffer - dump every advertisement in the air.
		// Used to capture the ORIGINAL remote's wake packet while the TV is
		// powered off.
		template<typename... Ts> class BleMiRemoteSniffAction : public Action<Ts...> {
			public:
				explicit BleMiRemoteSniffAction(BleMiRemote *ble_mi_remote) : ble_mi_remote_(ble_mi_remote) {}

				void set_seconds(uint32_t seconds) { this->seconds_ = seconds; }

				void play(const Ts&... x) override { this->ble_mi_remote_->sniffStart(this->seconds_); }

			protected:
				BleMiRemote *ble_mi_remote_;
				uint32_t seconds_{30};
		};

		// 2026-11-23: the wake broadcast, exposed as its own action so the
		// undirected (classic MiPower) and the directed (bonded peer) variant
		// can both be triggered - and tried - independently from YAML.
		template<typename... Ts> class BleMiRemotePowerWakeAction : public Action<Ts...> {
			public:
				explicit BleMiRemotePowerWakeAction(BleMiRemote *ble_mi_remote) : ble_mi_remote_(ble_mi_remote) {}

				void set_directed(bool directed) { this->directed_ = directed; }
				void set_named(bool named) { this->named_ = named; }
				void set_style(const std::string &style) { this->style_ = style; }

				void play(const Ts&... x) override {
					this->ble_mi_remote_->setPowerAdvertStyle(this->style_);
					this->ble_mi_remote_->powerAdvertStart(this->directed_, this->named_);
				}

			protected:
				BleMiRemote *ble_mi_remote_;
				bool directed_{false};
				bool named_{false};
				std::string style_{"mipower"};
		};

		template<typename... Ts> class BleMiRemoteStopAction : public Action<Ts...> {
			public:
				explicit BleMiRemoteStopAction(BleMiRemote *ble_mi_remote) : ble_mi_remote_(ble_mi_remote) {}

				void play(const Ts&... x) override { this->ble_mi_remote_->stop(); }

			protected:
				BleMiRemote *ble_mi_remote_;
		};
	}  // namespace ble_mi_remote
}  // namespace esphome

#endif
