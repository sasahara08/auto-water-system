#!/usr/bin/env python3
import time
import board
import busio
import gpiod
import os
from datetime import datetime
from pathlib import Path

import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn


# =========================
# 設定値
# =========================

DRY_THRESHOLD = 19000    # 乾燥判定しきい値
PUMP_ON_SEC = 3         # ポンプ動作時間（秒）
WAIT_AFTER_WATER = 300    # 給水後の待機時間（秒）
LOOP_INTERVAL = 600        # 通常ループ間隔（秒）
LOG_INTERVAL = 1       # ログ記録間隔（秒）

# Low Level Trigger リレー用
RELAY_GPIO = 4          # リレー制御GPIO（BCM番号）
RELAY_ON = gpiod.line.Value.INACTIVE  # 0
RELAY_OFF = gpiod.line.Value.ACTIVE   # 1

# ログディレクトリのベースパス
LOG_BASE_DIR = Path(__file__).parent / "log"


# =========================
# ログ記録関数
# =========================
def log_soil_data(message, value, voltage):
    """土壌センサーのデータをログファイルに記録"""
    now = datetime.now()
    
    # ログディレクトリパス: log/YYYY/MM/
    log_dir = LOG_BASE_DIR / now.strftime("%Y") / now.strftime("%m")
    
    # ディレクトリが存在しない場合は作成
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # ログファイル名: YYYY-MM-DD.log（日付のみ）
    log_file = log_dir / f"{now.strftime('%Y-%m-%d')}.log"
    
    # ログエントリ（日時を含む）
    log_entry = f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] {message} | raw={value}, voltage={voltage:.3f}V\n"
    
    # ファイルに追記
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(log_entry)
    
    print(f"ログ記録: {log_file}")


def log_error(error_type, error_message, traceback_str=""):
    """エラーをログファイルに記録"""
    now = datetime.now()
    
    # エラーログディレクトリパス: log/YYYY/MM/
    log_dir = LOG_BASE_DIR / now.strftime("%Y") / now.strftime("%m")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # エラーログファイル名: YYYY-MM-DD_error.log（日付のみ）
    error_log_file = log_dir / f"{now.strftime('%Y-%m-%d')}_error.log"
    
    # エラーログエントリ
    error_entry = f"""{'='*60}
    [ERROR] {now.strftime('%Y-%m-%d %H:%M:%S')}
    エラータイプ: {error_type}
    エラー内容: {error_message}
    {traceback_str}
    {'='*60}

    """
    
    # ファイルに追記
    with open(error_log_file, "a", encoding="utf-8") as f:
        f.write(error_entry)
    
    print(f"エラーログ記録: {error_log_file}")


# =========================
# GPIO 初期化（libgpiod V2）
# =========================
# V2では request_lines を使用
GPIO_CHIP = "/dev/gpiochip0"

relay_request = gpiod.request_lines(
    GPIO_CHIP,
    consumer="watering",
    config={
        RELAY_GPIO: gpiod.LineSettings(
            direction=gpiod.line.Direction.OUTPUT,
            output_value=RELAY_OFF
        )
    }
)


# =========================
# I2C / ADS1115 初期化
# =========================
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
# A0チャンネルを使う
soil = AnalogIn(ads, 0)


print("自動水やりシステム起動（ログ記録機能付き）")
print(f"ログディレクトリ: {LOG_BASE_DIR}")
print(f"ログ記録間隔: {LOG_INTERVAL // 60}分ごと")

# 最後にログを記録した時刻
last_log_time = 0

try:
    while True:
        try:
            value = soil.value
            voltage = soil.voltage
            current_time = time.time()
            has_water = 0

            print(f"土壌センサー: raw={value} voltage={voltage:.3f}V")

            # LOG_INTERVAL分ごとにログ記録==============================================
            if current_time - last_log_time >= LOG_INTERVAL:
                last_log_time = current_time
                if value > DRY_THRESHOLD:
                    print(f"ログ📙:土壌が乾燥しています------value:{value}")
                    log_soil_data(f"ログ📙:土壌が乾燥しています------value:{value}", value, voltage)
                else:
                    print(f"ログ📙:土壌が湿っています------value:{value}")
                    log_soil_data(f"ログ📙:土壌が湿っています------value:{value}", value, voltage)
            # ===========================================================================
        
        except Exception as e:
            # その他の予期しないエラー
            import traceback
            tb_str = traceback.format_exc()
            log_error(type(e).__name__, str(e), tb_str)
            print(f"エラー発生: {type(e).__name__}: {e}")
            print("エラーログに記録しました。システムを停止します。")
            raise

except KeyboardInterrupt:
    print("\nユーザーによって停止されました")

finally:
    print("クリーンアップ中...")
    try:
        relay_request.set_value(RELAY_GPIO, RELAY_OFF)
        relay_request.release()
        print("クリーンアップ完了")
    except Exception as e:
        print(f"クリーンアップ中にエラー: {e}")
