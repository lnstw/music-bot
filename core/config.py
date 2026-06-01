import os
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials


CONFIG_PATH = ".env"
CONFIG_KEYS = [
    "discord_user_name",
    "discord_user_id",
    "discord_guild_id",
    "discord_voice_channel_id",
    "spotify_client_id",
    "spotify_client_secret",
    "node_host",
    "node_port",
    "node_ssl",
    "node_pw",
    "discord_bot_token"
]
CONFIG_TEMPLATE = """# 請填寫以下值，注意不要公開此檔案
discord_user_name="請填入你的discord名稱"
discord_user_id=請填入你的discord_id
discord_guild_id=請填入你的伺服器ID(建議是單獨機器人的群組,機器人掛著使用)
discord_voice_channel_id=請填入你的語音頻道ID(機器人掛著使用)
spotify_client_id=請填入你的client_id
spotify_client_secret="請填入你的client_secret"
node_host="請填入你的lavalink" host
node_port=請填入你的lavalink port
node_ssl=請填入是否啟用ssl(0/1)
node_pw="請填入你的lavalink密碼"
discord_bot_token="請填入你的discord token"
"""

def check_and_create_config():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(CONFIG_TEMPLATE)
        print("已自動建立 .env，請填入相關資訊後重新啟動程式。")
        exit(0)

    load_dotenv(CONFIG_PATH)

    config = {}
    missing = []
    for k in CONFIG_KEYS:
        v = os.getenv(k)
        if v is None:
            missing.append(k)
        else:
            config[k] = v

    if missing:
        with open(CONFIG_PATH, "a", encoding="utf-8") as f:
            for k in missing:
                f.write(f"{k}=請填入你的資料\n")
        print(f".env 缺少欄位，已自動補上：{', '.join(missing)}，請補齊後重新啟動。")
        exit(0)

    for k in CONFIG_KEYS:
        if config[k].startswith("請填入"):
            print(f"請在 .env 裡填入 {k} 的正確值後再啟動。")
            exit(0)

    return config

config = check_and_create_config()
spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(
    client_id=config["spotify_client_id"],
    client_secret=config["spotify_client_secret"],
))