# 🌙 夜間部的音樂機器人 / Night Owl Music Bot 🎵


> 本專案由littlecommandcat協助LavaLyra的版本貢獻。
> 若想參考簡易版的Discord.py音樂機器人，歡迎至[MusicBot](https://github.com/littlecommandcat?tab=repositories)瀏覽。
>
> This project includes version contributions to LavaLyra by littlecommandcat.
> For a simplified Discord music bot, feel free to check out the [MusicBot](https://github.com/littlecommandcat?tab=repositories) Repository List.

[繁體中文](#繁體中文) | [English](#english)

---

## 繁體中文

輕量的 Discord 音樂機器人，支援 YouTube / Spotify，內建播放清單、插播、循環、自動推薦等功能。

### 🚀 快速部署
1. **安裝 Python 3.11**
2. **建立並啟動虛擬環境（建議）**
   - Windows:
     ```
     python -m venv .venv
     .venv\Scripts\activate
     ```
   - Linux/Mac:
     ```
     python3 -m venv .venv
     source .venv/bin/activate
     ```
3. **安裝相依套件**
   ```
   pip install -r requirements.txt
   ```
4. **複製範例環境變數檔案**
   將專案中的 example.env 複製一份並重命名為 .env。
5. **編輯 .env**，填入你的資訊（請參考下方設定說明）。
6. **啟動機器人**
   ```
   python main.py
   ```

### ⚙️ 設定說明（範例）
請在 .env 填入對應的值（**切勿公開此檔案或將真實 Token 上傳**）：

   ```
   DISCORD_USER_NAME="請填入你的 Discord 名稱"
   DISCORD_USER_ID="請填入你的 Discord 使用者 ID"
   DISCORD_GUILD_ID="請填入伺服器 ID（機器人掛著使用的群組）"
   DISCORD_VOICE_CHANNEL_ID="請填入語音頻道 ID（機器人掛著使用的頻道）"

   SPOTIFY_CLIENT_ID="請填入你的 Spotify Client ID"
   SPOTIFY_CLIENT_SECRET="請填入你的 Spotify Client Secret"

   NODE_HOST="請填入你的 Lavalink 網址（例如：freelavalink.com）"
   NODE_PORT=443
   NODE_SSL="true"
   NODE_PW="請填入你的 Lavalink 密碼"

   DISCORD_BOT_TOKEN="請填入你的 Discord Bot Token"
   ```

### 🔧 進階功能
- **自動留守與離開**：自動偵測空頻道並倒數離開（透過 on_voice_state_update 即時啟動）。
- **動態狀態顯示**：自動更新機器人狀態（Presence）顯示目前播放的歌曲標題。
- **獨立伺服器設定**：支援每個伺服器個別設定（如：是否顯示下一首提示、循環模式、是否自動推薦）。
- **開發者專用命令**：需在環境變數中正確設定 DISCORD_USER_ID。

### ⚠️ 注意事項
- 請勿將 DISCORD_BOT_TOKEN、SPOTIFY_CLIENT_SECRET 等敏感資訊公開。
- 若使用 Lavalink，請確認 Lavalink 版本與 wavelink 相容，並確保節點資訊正確且可連線。
- 若遇到 cache、token 或 Webhook 過期錯誤，請檢查權限並嘗試重啟或清除本地 .cache。

### 支援
不想自行架設？可以使用作者提供的機器人（不保證長期上線）：  
👉 點我邀請機器人：[https://discord.com/oauth2/authorize?client_id=1269984207501787177](https://discord.com/oauth2/authorize?client_id=1269984207501787177)

---

## English

A lightweight Discord music bot supporting YouTube and Spotify, featuring playlists, song skipping/interruption, looping, and automatic recommendations.

### 🚀 Quick Deployment
1. **Install Python 3.11**
2. **Create and Activate Virtual Environment (Recommended)**
   - Windows:
      ```
     python -m venv .venv
     .venv\Scripts\activate
     ```
   - Linux/Mac:
     ```
     python3 -m venv .venv
     source .venv/bin/activate
     ```
3. **Install Dependencies**
   ```
   pip install -r requirements.txt
   ```
4. **Copy Environment Variables Template**
   Copy example.env and rename it to .env.
5. **Edit .env** and fill in your information (see configuration guide below).
6. **Start the Bot**
   ```
   python main.py
   ```

### ⚙️ Configuration Guide (Example)
Fill in the corresponding values in .env (**NEVER publicly share this file or your real token**):

   ```
   DISCORD_USER_NAME="Your Discord username"
   DISCORD_USER_ID="Your Discord User ID"
   DISCORD_GUILD_ID="Your Discord Server ID (where the bot will stay)"
   DISCORD_VOICE_CHANNEL_ID="Your Voice Channel ID (where the bot will stay)"
   
   SPOTIFY_CLIENT_ID="Your Spotify Client ID"
   SPOTIFY_CLIENT_SECRET="Your Spotify Client Secret"
   
   NODE_HOST="Your Lavalink host (e.g., freelavalink.com)"
   NODE_PORT=443
   NODE_SSL="true"
   NODE_PW="Your Lavalink password"
   
   DISCORD_BOT_TOKEN="Your Discord Bot Token"
   ```

### 🔧 Advanced Features
- **Auto Leave**: Automatically detects empty voice channels and starts a countdown to leave (triggered via on_voice_state_update).
- **Dynamic Status**: Automatically updates the bot's presence to display the currently playing song title.
- **Per-Server Customization**: Supports individual settings for each guild (e.g., toggle next-song notifications, loop modes, and auto-recommendations).
- **Developer Commands**: Requires DISCORD_USER_ID to be configured correctly in the environment variables.

### ⚠️ Important Notes
- Never expose sensitive data like DISCORD_BOT_TOKEN or SPOTIFY_CLIENT_SECRET.
- If using Lavalink, ensure the version is compatible with your wavelink library, and double-check your node credentials and connection.
- If you encounter cache, token, or Webhook documentation errors, verify channel permissions, restart the bot, or clear the local .cache folder.

### 🙋 Support
Don't want to host it yourself? You can use the bot hosted by the author (24/7 uptime not guaranteed):  
👉 Click here to invite the Bot: [https://discord.com/oauth2/authorize?client_id=1269984207501787177](https://discord.com/oauth2/authorize?client_id=1269984207501787177)