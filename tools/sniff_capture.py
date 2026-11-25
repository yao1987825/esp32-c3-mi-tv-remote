#!/usr/bin/env python3
"""启动 BLE 嗅探并把板子串口日志存到文件。

用法: python tools/sniff_capture.py <秒数> <输出文件>
"""
import subprocess
import sys
import threading
import time

PY = r"C:\Users\Administrator\AppData\Local\esphome\Cache\idf\penvs\5.5.6\Scripts\python.EXE"
CAP = r"D:\esp32-c3开发版\tools\capture_boot.py"
REM = r"D:\esp32-c3开发版\tools\tv_remote.py"


def main():
    seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    outfile = sys.argv[2] if len(sys.argv) > 2 else r"C:\Users\Administrator\AppData\Local\Temp\sniff.txt"

    lines = []

    def reader():
        proc = subprocess.Popen(
            [PY, CAP, "COM6", str(seconds + 15), "--no-reset"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        for raw in proc.stdout:
            lines.append((time.time(), raw.rstrip("\n")))
        proc.wait()

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    time.sleep(3)
    print(f">>> 启动嗅探（{seconds} 秒）", flush=True)
    subprocess.run([sys.executable, REM, "--sniff"])
    t.join(timeout=seconds + 40)
    with open(outfile, "w", encoding="utf-8") as fh:
        for ts, line in lines:
            fh.write(line + "\n")
    print(f">>> 日志已写入 {outfile}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
