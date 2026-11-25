# 小米电视蓝牙遥控器（ESP32-C3 SuperMini）

这块板子现在只做一件事：**当电视的蓝牙遥控器**。

---

## 为什么是蓝牙，不是 ADB

客厅那台是 `MiTV4-ANSM0`（Android 6.0.1）。它自己的遥控器**就是蓝牙设备**：

```
$ adb shell dumpsys input | grep -A2 "小米蓝牙语音遥控器"
    5: 小米蓝牙语音遥控器
      Identifier: bus=0x0005, vendor=0x2717, product=0x32b8
```

`bus=0x0005` 就是 `BUS_BLUETOOTH` —— 电视把遥控器当成 HID 键盘（主机侧），
所以只要板子伪装成同样的 HID 设备，音量、电源这些键就都能按。

音量在 HID 里是 Consumer Control 的两个 usage：

| 键 | usage | 在报告里的位 |
|----|-------|--------------|
| 音量 + | `0xE9` | 7 |
| 音量 − | `0xEA` | 8 |
| 电源 | `0x30` | 5 |

`ble_mi_remote` 组件用的 HID 身份是 `vid=0x2717 / pid=0x32b9` —— 和小米
原装遥控器同一个厂商号，电视才会认它是"自己人"。

---

## 烧录

```powershell
cd D:\esp32-c3开发版\esp32-adb-remote\esphome
.\build.ps1            # 只编译
.\build.ps1 -Run       # 编译 + 烧录 + 看日志（板子要用 USB-C 连着电脑）
```

> 板子必须用**数据线**（不是只供电的线）插到这台 PC 的 USB 口上。
> ESP32-C3 的 USB-C 是芯片原生 USB，烧录和日志都走它。

编译会自动把配置和组件复制到 `C:\esp32c3\esphome\`（纯 ASCII 路径，
因为 MinGW 的链接器读不了中文路径），然后调用 `esphome compile`。

---

## 电视端配对（关键一步）

烧完固件、板子在电视旁边开机后：

1. 电视遥控器打开 **设置**
2. 找到 **「遥控器和配件」**（有的固件叫「蓝牙设备」/「外设」）
3. 点 **「添加遥控器」** 或 **「搜索设备」**
4. 列表里会出现 **`MI Remote`** —— 这就是板子
5. 点它，**电视屏幕上会弹出一个配对码（4～6 位数字）**
6. 在电视上把配对码输进去 → 配对完成

> 配对码是**电视**给的，要用电视遥控器在电视上输入，不是板子要什么码。

配对成功的标志：

- 电视的设备列表里多了一条 `MI Remote`
- HA 里出现 `binary_sensor.connected`（连接状态）

---

## 验证音量

- **在 HA 面板上**点「音量 +」，电视上的音量条应该跳一格。
- 或者在串口日志里（`.\build.ps1 -Run`）看板子有没有发出报告。
- 也可以直接用电视遥控器按一下音量键，确认遥控器本身是好的。

---

## 开关机

- **关机**：发电源键（`0x30`）。电视会像收到原装遥控器一样关机。
  面板上的「电源」按钮设成了**长按才触发**，手滑点一下不会关。
- **长按关机**：有些电视的电源键是「短按=开关机切换，长按=只关机」。
  组件的 `press` 动作原本固定 8ms 自动松手，做不到长按，所以给它加了
  `with_timer: false` 选项：按下后一直保持，直到显式 `release`。
  `button.tv_power_hold` 就是这么配的（按住 2 秒再松开）。
  短按/长按分别是什么行为要对着真电视实测才知道，两个按钮都留着。
- **开机**：电视关掉之后 BLE 无线电就停了，普通广播叫不醒它。组件为此
  做了一套「唤醒广播」（小米遥控器专用的 manufacturer data + 定向广播），
  发电源键时会自动触发；另外还有一个 `button.tv_wake`，让板子临时当一次
  BLE central 主动去连电视把它唤醒（MiPower 用的就是这招）。
  **这一项在电视上还没实测过** —— 开机属于「把正在用的电视关掉」这种
  不可逆操作，等你方便的时候再验。

  2026-11-23 实测结果：两条唤醒路子**都没成功**，同时暴露出三个代码缺陷，
  已全部修掉（见下面的「三个参考项目到底行不行」）：

  | 缺陷 | 现象 | 修复 |
  |------|------|------|
  | 重连窗口耗尽后板子**彻底停止广播** | 断连 30 秒后板子彻底隐身，电视重启后永远扫不到它，所有按键失效 | 改成回落到普通广播，板子始终可被发现 |
  | 唤醒广播**没显式设置广播模式** | 重连路径会把 BLE 栈留在「定向广播」模式，唤醒广播继承了这个模式，被电视待机扫描忽略 | 每次广播都显式设置模式；并新增「定向唤醒」变体 |
  | `connect_wake` 的日志是 **DEBUG 级** | 板子日志级别是 INFO，整条唤醒链路**一行日志都没有**，看起来像「什么都没发生」 | 全部改成 INFO |

  修完新增三个按钮：`tv_wake_advert`（非定向唤醒广播）、
  `tv_wake_directed`（定向发给已绑定的电视）、
  `tv_reconnect`（强制回到可被发现状态，**保留**配对记录）。
  注意 `plain_advert` 那个老动作会 `deleteAllBonds()` 删掉配对，别拿它当
  「重连」用。

  ### 电视扫不到 `MI Remote` —— 根因在广播结构

  2026-11-23 实测电视「搜索设备」扫不到板子，最终定位到
  **NimBLE 的一个坑**：

  ```cpp
  // NimBLEAdvertising.cpp
  bool NimBLEAdvertising::setName(const std::string& name) {
      if (m_scanResp && m_scanData.setName(name)) {   // ← 开了 scan response 就只进 scan data
          m_advDataSet = false;
          return true;
      }
      ...
  }
  ```

  组件原来写的是 `enableScanResponse(true)` 然后 `setName(deviceName)`，
  于是**设备名只出现在 scan response 里，advertising packet 里没有名字**。
  而 **Android 6（MiTV4 的固件）的 `BluetoothLeScanner` 根本不把 scan
  response 的内容交给应用** —— 电视每次收到的都是「一个没有名字的设备」，
  设置页直接把它过滤掉，于是列表里永远看不到 MI Remote。

  修法：**手工拼 advertising packet，把名字放进 ADV 包本身**。

  ```
  ADV packet (22B): 02 01 06 | 03 19 C1 03 | 0A 09 "MI Remote" | 03 03 12 18
                     Flags     Appearance     Complete Local Name    UUID 0x1812
  SCAN RSP  (20B): 13 FF 46 00 E7 12 97 30 35 F2 78 FF FF FF 30 43 52 4B 54 4D
                     小米厂商数据 (company id 0x0046)
  ```

  固件启动时会把这���个包打成 hex 打到串口日志里（`advert:` / `scanrsp:` 两行），
  可以直接对着抓包工具核对，不用猜。

  另外新增 `tv_wake_named`：经典 MiPower 唤醒包是**匿名**的，但有些电视固件
  是按「已配对遥控器的名字」唤醒的，这个变体把名字也塞进唤醒广播。

  ### 修好之后的完整验证（2026-11-23 17:1x）

  | 步骤 | 结果 |
  |------|------|
  | 电视「搜索设备」扫到板子 | ✅ `MitvBluetoothView: onDeviceAdded, device is MI Remote State:10 adds:9C:96:D5:B0:C2:7E` |
  | 配对 | ✅ `bondState:12` (BOND_BONDED)，`BleRemoteControllerService: doHogpConnect` |
  | HID 输入设备注册 | ✅ `dumpsys input` → `Device 5: MI Remote` |
  | 音量 + | ✅ 电视 `STREAM_MUSIC` 音量 16 → 19（按 3 次） |
  | **电视重启后自动回连板子** | ✅ 重启后 `Device 7: MI Remote`，按键依然生效（音量 20 → 23） |

  最后一条是关键：**之前「电视重启后不回连」的死结，根因就是缺陷 1**
  （板子在断连 30 秒后彻底停止广播 → 电视重启时扫不到它）。修好后电视
  开机自动重连，音量键直接可用。

  ### 开机唤醒：四种方式都试过了

  | 方式 | 结果 | 板子日志 |
  |------|------|----------|
  | `connect_wake`（板子当 central 连电视） | ❌ 电视**开着**时能连上；电视**待机**时 `connect attempt failed or timed out`（3 秒超时） | 说明待机时蓝牙主机根本不响应连接请求 |
  | `power_advert`（非定向广播） | ❌ | `stop=OK setManufacturerData=OK applyOk=OK start=OK`（广播确实发出去了） |
  | `power_wake` 定向 | ❌ | 同上 |
  | `power_wake` 带名字 | ❌ | 同上 |

  结论：**「开」这条路目前只有原理，没有实证**。原装遥控器能唤醒这台电视，
  说明 MiTV4 的待机唤醒是可行的，但我们的广播包没被认领。下一步的突破口
  应该是**抓原装遥控器在待机时发出的那个包**，照抄它的字节。

  ### 2026-11-23 17:2x 又挖到一条关键线索

  用板子的 HID 电源键把电视**真正关机**之后（ping 不通、adb offline），
  再跑 `connect_wake`，板子日志显示：

  ```
  connectWakeStart: connecting to C8:28:32:62:77:AA
  connectWakeStart: connected, disconnecting        <-- 连上了！
  ```

  **电视关机状态下，它的 BLE 主机居然是活的，还能接受 GATT 连接请求。**
  这和「待机时超时失败」是两种不同的电源状态：
  - `adb keyevent 26` → Android 挂起 → 蓝牙主机不响应（超时）
  - HID 电源键关机 → 电视真关机 → 蓝牙主机保持低功耗唤醒态（**能连**）

  而这正是原装遥控器能开机的原理：MiTV4 的蓝牙主机一直在跑，遥控器一
  连上来它就启动 Android。

  旧代码连上就立刻 `disconnect()` —— 电视的主机刚收到连接请求就被断开，
  根本来不及触发开机流程。**改成连上后保持 15 秒**（`hold_ms` 可配，
  yaml 里 `TV Wake` = 15 秒，`TV Wake Connect Long` = 45 秒）。

  ### 板子内置 BLE 嗅探器 —— 开机问题的决定性实验

  既然原装遥控器能开机，而 MiPower 那套包（小米**盒子**的协议）电视不认，
  那就**直接把原装遥控器发的包抓下来照抄**。

  固件里加了 `ble_mi_remote.sniff` 动作：板子临时当一次 BLE 扫描器，把
  空气里所有广播的**原始字节**打到串口：

  ```
  SNIFF <MAC> rssi=.. advType=0x.. name='..' mfg=[..] ad=[T01:..|T03:..|TFF:..|]
  ```

  已知原装遥控器（「小米蓝牙语音遥控器」）的 BLE 地址是
  `0A:22:4A:35:05:11` 和 `D4:B8:FF:7D:AD:6D`，抓包时按这两个 MAC 找即可。

  用法：
  1. 电视关机
  2. `python tools/tv_remote.py --sniff`（板子开始监听 90 秒）
  3. 用**原装遥控器**按一下电源键
  4. 看串口日志里那个 MAC 发出的包的原始字节

  ⚠ 扫描期间板子自己不能广播（NimBLE 一个时刻只能做一件 GAP 事件），
  所以嗅探时电视扫不到板子 —— 这是正常的，嗅探完会自动恢复广播。

  另一个待验证的假设：**电视关机后蓝牙主机会主动重连已绑定的 HID 外设**。
  如果成立，那根本不需要任何唤醒包 —— 板子只要保持广播 + 配对记录还在，
  电视自己会连上来，收到 HID 电源键就开机。
  （已验证：电视**重启后**确实会自动连回板子；关机状态下的重连还没测。）

  ### 抓包结果 —— 找到真正的唤醒包了 🎯

  板子的嗅探器在电视**关机**状态下抓到了两个设备：

  ```
  # 电视自己，一直在广播（advType 0x03 = 不可连接非定向）
  SNIFF C8:28:32:62:77:AA rssi=-89 advType=0x03 name=''
        mfg=[8F 03 0A 10 1C 00 00 27 6D C1 1D 41 B0 EC]

  # 原装遥控器，只在按电源键的那一瞬间广播了一次（advType 0x00 = 可连接）
  SNIFF D4:B8:FF:7D:AD:6D rssi=-79 advType=0x00 name='MI RC' mfg=[00 01]
        ad=[T01:05 | T03:12 18 | T08:4D 49 20 52 43
            | T09:4D 49 20 52 43 | T0A:00 | TFF:00 01]
  ```

  逐字节解出来：

  | AD 结构 | 值 | 含义 |
  |---------|-----|------|
  | T01 Flags | `05` | LE General Discoverable + BR/EDR Not Supported |
  | T03 UUID | `12 18` | 16-bit Service UUID **0x1812**（HID） |
  | T08 | `4D 49 20 52 43` | Shortened Local Name **"MI RC"** |
  | T09 | `4D 49 20 52 43` | Complete Local Name **"MI RC"** |
  | T0A | `00` | TX Power = 0 dBm |
  | **TFF** | **`00 01`** | **Manufacturer Data：company id `0x0000`，数据 `0x01`** |

  **两个致命发现：**

  1. **manufacturer data 完全不是 MiPower 那套。** 原装遥控器用的是
     company id `0x0000` + 一个字节 `0x01`；我们一直发的
     `46 00 E7 12 97 30 35 F2 78 FF FF FF 30 43 52 4B 54 4D`
     是 **小米盒子（Mi Box）** 的协议，这台小米电视根本不理它 ——
     这就是所有唤醒尝试全部失败的直接原因。
  2. **这个包是「可连接」的**（advType 0x00）。所以真正的唤醒流程是：
     遥控器按键 → 发这个包 → **电视的待机扫描器主动连上来** →
     遥控器通过 HID 发电源键 → 电视开机。

  据此新增两个唤醒样式（yaml 里 `TV Wake MI RC` / `TV Wake MI RC Own`），
  逐字节照抄原包（29 字节，刚好塞进 31 字节预算），并且**板子被电视连回来
  时自动补发 HID 电源键**（wake mode）。

  ### 照抄原包之后 —— 还是不行，于是有了确定结论

  固件会把自己实际发出的 mi_rc 包打成 hex 打到串口，和抓到的原包逐字节对比：

  ```
  我们的: 02 01 05 | 03 03 12 18 | 06 08 4D 49 20 52 43
          | 06 09 4D 49 20 52 43 | 02 0A 00 | 03 FF 00 01        (28 字节)
  原包的: T01:05   | T03:12 18     | T08:"MI RC"
          | T09:"MI RC"            | T0A:00   | TFF:00 01
  ```

  **完全一致**，但电视在完全关机状态下依然不醒。另外还试过：

  | 尝试 | 结果 |
  |------|------|
  | mi_rc 包（原封不动照抄） | ❌ |
  | mi_rc 包 + 用我们自己的名字 "MI Remote" | ❌ |
  | pid 从 `0x32b9` 改成原装的 `0x32b8` | ❌ |
  | 广播间隔压到 20–40ms、持续 60 秒 | ❌ |
  | 板子当 central 反连电视（保持 15 秒 / 45 秒） | ❌ 电视不响应连接请求 |
  | **用户用原装遥控器按电源键** | ❌ **电视也没醒**（ping 不通） |

  最后一条是关键：**原装遥控器在「完全关机」状态下也唤不醒这台电视。**
  所以这条路不是「我们没做对」，而是 **MiTV4 的「完全关机」态根本不接受
  BLE 唤醒**。之前「用遥控器能打开」那次，电视其实并不在完全关机态。

  → 真正可用的「开机」是另一条路：**关屏（待机）态下的唤醒**。MiTV 的
  电源菜单里有「关屏」，那个状态下 Android 还活着、BLE 连接保持，
  电源键就能把屏幕点亮。这是 HA 面板该用的「开/关」语义。

---

## 三个参考项目到底行不行

工作区里三个项目，**只有一个是真的「小米遥控器」**：

| 项目 | 是什么 | 能不能发电源键 | 有没有唤醒机制 |
|------|--------|----------------|----------------|
| `ESP32-BLE-Keyboard-master` | T-vK 的**通用** Arduino BLE 键盘库 | ❌ 媒体键列表里根本没有 power（`BleKeyboard.h:105-120`） | ❌ 全仓库没有一行小米/唤醒代码 |
| `esphome-blekeyboard-main` | dmamontov 的**通用** ESPHome BLE 键盘组件 | ❌ MEDIA 列表同样没有 power（`const.py:607-714`） | ❌ 而且所有动作都先判 `is_connected()`，没连上就什么都不会发生 |
| `esphome-ble-mi-remote-main` | **真正的小米遥控器** | ✅ 小米厂商号 vid `0x2717`/pid `0x32b9` + 小米专用 3 字节特殊键报告（`ble_mi_remote.cpp:534-552`） | ✅ 唤醒广播 `powerAdvertStart`（`ble_mi_remote.cpp:555-610`）+ `connectWakeStart` 当 central 反连 |

所以「开关电视」这个能力，**前两个项目从来就不具备** —— 它们只能发标准
HID 按键，电视没连上时什么也发不出去，能做的只有「连着的时候调音量、
按方向键」。真正能开关电视的只有第三个项目。

而且「开」和「关」的难度完全不一样：

- **关**成立，是因为链路还在，HID 报告送得出去（而且必须用第三个项目的
  小米身份 + 小米特殊键报告，电视才认）。→ 实测 ✅
- **开**在原理上**不可能靠 HID 报告**：电视待机时蓝牙主机断电或进入低功耗，
  HID 报告无处可送。开机只能靠「电视被唤醒」——唤醒广播或反向连接，
  这两招只有第三个项目有。→ 实测 ❌（修了三个缺陷后再验）

关键线索：**原装遥控器能开机**，说明原理是成立的，是我们的实现没对上图。

---

## 接 Home Assistant

板子开了 ESPHome 的**原生 API**，HA 里会自动出现一个设备
**「小米电视遥控器」**，带着 24 个按键实体：

| 实体 | 作用 |
|------|------|
| `button.ble_mi_remote_volume_up` | 音量 + |
| `button.ble_mi_remote_volume_down` | 音量 − |
| `button.ble_mi_remote_power` | 电源（短按） |
| `button.ble_mi_remote_android_tv` | 主页 |
| `button.ble_mi_remote_back` | 返回 |
| `button.ble_mi_remote_enter` | 确认 |
| `button.vol_up_x5` / `button.vol_down_x5` | 一次调 5 格 |
| `button.tv_home` | 回主页 |
| `button.tv_power_hold` | 长按电源（真·HID 长按 2 秒） |
| `button.tv_wake` | 唤醒电视（待机时用） |
| `binary_sensor.connected` | 是否连着电视 |

> 这些 id 是对着 ESPHome 生成的 `main.cpp` 核过的：
> `App.register_button(key_volumeup, "ble-mi-remote-Volume Up", ...)`
> → object_id 就是 `ble_mi_remote_volume_up`。
> 大写、空格、连字符在转 object_id 时都会变成下划线。

API 用的是加密连接（ESPHome 2026.1 起不再支持密码认证），
密钥在 `tv-remote.yaml` 的 `api.encryption.key` 里。

面板 YAML 在 `../ha-package/dashboard.yaml` 的「电视」那一页。

---

## 常见问题

**电视搜不到 `MI Remote`**
- 板子刷上去了吗？插着 USB 看串口日志，应该有「启动中，等待与电视配对」。
- 电视的蓝牙是不是被关了？（设置 → 蓝牙）
- 板子离电视太远？BLE 有效距离大概 10 米，客厅里没问题。

**搜到了但配不上**
- 电视上要**输入配对码**，光点「确定」没用。
- 电视里已经有一次同名的记录？先在「遥控器和配件」里把旧的删掉。

**配对成功但按键没反应**
- 看 `binary_sensor.connected` 是不是 on。
- 电视有没有被别的设备占着遥控器（比如另一个蓝牙遥控器）。

**板子重启后连不上电视**
- 配对信息存在 NVS 里（`CONFIG_BT_NIMBLE_NVS_PERSIST=y`），正常不会丢。
- 万一丢了，在电视上把 `MI Remote` 删掉，重新配一次。

**编译报 `bits/c++config.h: No such file or directory`**
这是 **Windows 的 MAX_PATH（260 字符）** 问题，不是文件缺失。
ESP-IDF 的工具链藏得很深，gcc 探测多编译单元的头文件时用的是
`bin/../lib/gcc/<target>/<ver>/../../../../<target>/include/...`
这种**没化简的相对路径**，拼起来能到 269 字符，超过 260 就被系统拒了。

开长路径即可（管理员 PowerShell）：

```powershell
Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' LongPathsEnabled 1
```

**不需要重启**，新起的进程立刻生效。ESPHome 自己的源码里也写了这个坑
（`esphome/espidf/framework.py` 的 `_check_windows_path_length`），
它给的另一个办法是把 IDF 目录挪到短路径（`ESPHOME_ESP_IDF_PREFIX`），
但那要重下 3.2 GB，不如开注册表。

**编译报 `invalid new-expression of abstract class type`**
组件里的 action 类写的是 `void play(Ts... x)`，而 ESPHome 2026.11 的基类
是 `virtual void play(const Ts &...x) = 0;` —— 签名对不上就变成抽象类。
组件里的 6 个 action 都要改成 `void play(const Ts&... x) override`。
