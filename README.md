# youtube-live-notify

獨立於 Streamcord 的 YouTube 開播通知備援。每 5 分鐘檢查以下四個頻道，偵測到新的公開直播後，透過 Discord Webhook 發送一次通知：

- BIZzzz（`@bbbbiz`）
- emfa（`@emfa1213`）
- Solchan（`@chan_19241`）
- 有為想吃餅（`@iuwaximcbim`）

固定 Channel ID 收錄於 `channels.json`，不會因頻道改名或更換 handle 而失效。

## 運作方式

GitHub Actions 每 5 分鐘執行 `monitor.py`。程式透過 YouTube Data API 讀取各頻道最近 15 部影片，再判斷其中是否有正在進行的公開直播。成功送出 Discord 通知後，影片 ID 會記錄在 `state.json`，避免下一輪重複通知。

程式只使用 Python 內建套件，不需要安裝額外依賴。

每輪只使用約 5 個 YouTube API quota units，預估每日約 1,440 units，低於新專案常見的每日 10,000 units 配額。

## GitHub Secrets

在 repository 的 **Settings → Secrets and variables → Actions** 新增：

- `YOUTUBE_API_KEY`：已啟用 YouTube Data API v3 的 Google API key。
- `DISCORD_WEBHOOK_URL`：「🔴威威直播通知」頻道的 Discord Webhook URL。

Webhook 的建立位置：Discord 頻道設定 → 整合 → Webhooks → 新 Webhook。可以直接在 Discord 設定 Webhook 的名稱與頭像，再複製 Webhook URL。

## 選用 GitHub Variables

在 repository 的 **Settings → Secrets and variables → Actions → Variables** 可新增：

- `DISCORD_WEBHOOK_USERNAME`：通知顯示名稱；未設定時使用「YouTube 直播通知」。
- `DISCORD_WEBHOOK_AVATAR_URL`：通知頭像的公開 HTTPS 圖片網址。

這兩個值會覆寫 Discord Webhook 本身的名稱與頭像。若希望直接使用 Discord 內設定的樣式，不必新增這兩個 Variables。

Secrets 設定完成後，到 **Actions → Check YouTube Live → Run workflow** 手動執行一次。若當時已有直播且尚未記錄，第一次執行會立即補送通知。

## 本機執行

PowerShell：

```powershell
$env:YOUTUBE_API_KEY = "你的 API key"
$env:DISCORD_WEBHOOK_URL = "你的 Discord Webhook URL"
python monitor.py
```

## 調整頻道

修改 `channels.json` 即可。每個項目包含顯示名稱、handle 與固定 Channel ID。
