# 🌙 夜間部的音樂機器人 🎵

輕量的 Discord 音樂機器人，支援 YouTube / Spotify，內建播放清單、插播、循環、自動推薦等功能。

---

## 🚀 快速部署
1. 安裝 Python 3.11  
2. 建立並啟動虛擬環境（建議）  
   - python -m venv .venv  
   - .venv\Scripts\activate
3. 安裝相依套件（請依專案 requirements.txt 安裝）  
   - pip install -r requirements.txt
4. 執行一次 main.py 產生 config.txt  
   - python main.py
5. 編輯 `config.txt`，填入你的資訊（請勿上傳 token/secret 到公開倉庫）
   - discord_user_name=
   - discord_user_id=
   - spotify_client_id=
   - spotify_client_secret=
   - node_url=（Lavalink）
   - node_pw=
   - discord_bot_token=

啟動機器人：
- python main.py

---

## ⚙️ 設定說明（範例）
請在 config.txt 填入對應的值（範例，不要放真實 token）：
```
discord_user_name=yourname
discord_user_id=123456789012345678
spotify_client_id=xxxxxxxxxxxxxxxxxxxx
spotify_client_secret=xxxxxxxxxxxxxxxxxxxx
node_url=http://your-lavalink:2333
node_pw=youshallnotpass
discord_bot_token=YOUR_BOT_TOKEN
```

---

## 📜 常用指令（斜線命令）
- /play <query> — 播放（支援 YouTube、Spotify、Apple）  
- /playnext <query> — 插播為下一首  
- /pause — 暫停  
- /resume — 繼續  
- /skip — 跳過  
- /stop — 停止並清空清單  
- /queue — 顯示播放清單  
- /shuffle — 打亂清單  
- /loop — 切換循環模式  
- /autorecommend — 自動推薦開關  
- /np — 顯示目前播放歌曲  
- /volume <0-150> — 調整音量  
- /nowplaymsg — 開關播放前提示訊息  
- /隨機圖 — 取得一張隨機圖片（有重新取得按鈕）  
- /leave — 讓機器人離開語音頻道  
- /reload — 重連並嘗試恢復播放狀態

---

## 🔧 進階功能
- 自動偵測空頻道並倒數離開（被動或 on_voice_state_update 即時啟動）
- 自動更新機器人狀態（status）顯示目前播放的歌曲標題
- 支援每個伺服器個別設定（例如是否顯示下一首提示、循環模式、是否自動推薦）
- 開發者專用命令（需在 config 裡設定開發者 discord_user_id）

---

## ⚠️ 注意事項
- 請勿將 `discord_bot_token`、`spotify_client_secret` 等敏感資訊公開。  
- 若使用 Lavalink，請確認 Lavalink 版本與 wavelink 相容，並確保 node_url/node_pw 正確且可連線。  
- 若遇到 cache、token 或 Webhook 過期錯誤，請檢查權限並嘗試重啟或清除本地 .cache。

---

## 🙋 支援
不想自行架設？可以使用作者提供的機器人（不保證長期上線）：  
https://discord.com/oauth2/authorize?client_id=1269984207501787177

---