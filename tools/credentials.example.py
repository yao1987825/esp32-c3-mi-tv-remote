"""本机凭据模板 —— 复制成 `credentials.py` 再改成你自己的值。

    cp credentials.example.py credentials.py

`credentials.py` 已经在 .gitignore 里，**不会**被提交到仓库。
不想建文件也可以，直接用环境变量：
    TV_REMOTE_BOARD_IP / TV_REMOTE_WEB_USER / TV_REMOTE_WEB_PASS
    TV_REMOTE_NOISE_PSK / TV_REMOTE_TV_ADB / TV_REMOTE_HA_HOST / TV_REMOTE_HA_TOKEN
"""

# --- 板子（ESPHome 固件）---------------------------------------------------
# 板子的局域网 IP（烧完固件后看串口日志的 "IP address" 行）
BOARD_IP = "192.168.6.101"

# 板子自带网页的 digest 认证账号（对应 tv-remote.yaml 的 web_server.auth）
WEB_USER = "admin"
WEB_PASS = "改成你自己的"

# ESPHome 原生 API 的加密密钥（对应 tv-remote.yaml 的 api.encryption.key）
# 32 字节 base64。生成：
#   python -c "import base64,os;print(base64.b64encode(os.urandom(32)).decode())"
NOISE_PSK = ""

# --- 电视 ------------------------------------------------------------------
# 小米电视的 ADB 地址（用来查 dumpsys input / getevent，排查按键用）
TV_ADB = "192.168.6.209:5555"

# --- Home Assistant --------------------------------------------------------
HA_HOST = "192.168.6.135:8123"
# 长期访问令牌：HA 里「你的头像 → 个人资料 → 长期访问令牌」生成
HA_TOKEN = ""
