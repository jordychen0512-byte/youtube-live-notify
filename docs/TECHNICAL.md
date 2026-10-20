# 技術細節與監測名單

[回到 README](../README.md) · [部署與交接指南](OPERATIONS.md)

以下依本專案目前程式說明；名單與程式參數若有修改，請同步更新本文件。

## 目前監測名單

| 頻道 | Handle | 通知顯示名稱 |
| --- | --- | --- |
| BIZzzz | @bbbbiz | 台港澳威威｜Biz |
| emfa | @emfa1213 | 韓國威威｜emfa |
| Solchan | @chan_19241 | 韓國威威｜Solchan |
| 有為想吃餅 | @iuwaximcbim | 台港澳威威｜有為想吃餅 |

名單來自 `channels.json`。實際查詢使用固定 `channel_id`；`handle` 不參與查詢。`notification_name` 是通知名稱，未填時使用 `name`。

## 開播與通知規則

1. 讀取各頻道 uploads 播放清單最近 15 筆影片，再將去重後的影片 ID 每 50 筆一批查詢詳細狀態。
2. 必須同時符合：`liveBroadcastContent == "live"`、有 `actualStartTime`、沒有 `actualEndTime`、`privacyStatus == "public"`，才視為直播中。預告、已結束與非公開影片不通知；不在最近 15 筆清單中的直播也不會被檢查。
3. 新影片 ID 會發送含 `@everyone`、通知名稱、影片標題與連結的文字通知。
4. 只有 Webhook 成功後才將 ID 寫入 `state.json`，每個頻道保留最近 100 個已通知 ID。同一 ID 在記錄內不重複通知；第一次執行若已有未記錄的公開直播，會立即補送。超出保留範圍、刪除狀態或保存失敗後，可能再次通知。

## API 請求量與錯誤處理

四個頻道正常查詢時，先發出 4 次播放清單請求，再依去重後的影片數發出 0～2 次影片詳細資料請求；若四個清單皆滿且影片互不重複，共為 6 次請求。因此不能固定估算成每輪 5 次。實際每日用量也取決於額外排程、手動執行及重試。

HTTP 429、500、502、503、504 與連線錯誤最多嘗試 3 次。單一頻道清單或 Discord 通知失敗會繼續處理其他頻道，最後回傳失敗；影片詳細資料查詢失敗則立即結束。Webhook 重試與狀態保存並非原子操作，無法保證任何故障情況下都只送一次。

## 手動執行與測試

在 **Actions → Check YouTube Live → Run workflow** 執行。勾選 `test_notification` 只傳送一則不標註任何人的測試訊息，不查詢 YouTube、不更新直播狀態；只需 Webhook。

本機使用 Python 3.12，程式只使用內建套件：

```powershell
$env:YOUTUBE_API_KEY = "你的 API key"
$env:DISCORD_WEBHOOK_URL = "你的 Discord Webhook URL"
python monitor.py
# 會實際送出 Discord 測試訊息
python monitor.py --test-notification
# 離線單元測試
python -m unittest discover -s tests
```

## 調整頻道

修改 `channels.json` 的 `name`、`handle`、`channel_id` 與選用 `notification_name`。新頻道的通知狀態由程式自動建立。

