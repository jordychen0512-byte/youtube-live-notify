import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
CHANNELS_FILE = ROOT / "channels.json"
STATE_FILE = ROOT / "state.json"
YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3"
MAX_RECENT_UPLOADS = 15
MAX_NOTIFIED_IDS = 100


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback


def save_state(state: dict[str, Any]) -> None:
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


class HttpClient:
    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> bytes:
        if params:
            url = f"{url}?{urlencode(params)}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"User-Agent": "youtube-live-notify/1.0"}
        if data is not None:
            headers["Content-Type"] = "application/json"

        for attempt in range(3):
            try:
                request = Request(url, data=data, headers=headers, method=method)
                with urlopen(request, timeout=20) as response:
                    return response.read()
            except HTTPError as error:
                if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise
            except URLError:
                if attempt == 2:
                    raise
            time.sleep(2**attempt)
        raise RuntimeError("HTTP request failed")

    def get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        return json.loads(self.request("GET", url, params=params).decode("utf-8"))

    def post_json(self, url: str, payload: dict[str, Any]) -> None:
        self.request("POST", url, payload=payload)


def uploads_playlist_id(channel_id: str) -> str:
    if not channel_id.startswith("UC"):
        raise ValueError(f"無效的 YouTube Channel ID：{channel_id}")
    return "UU" + channel_id[2:]


def youtube_get(
    client: HttpClient,
    resource: str,
    api_key: str,
    **params: Any,
) -> dict[str, Any]:
    return client.get_json(
        f"{YOUTUBE_API_URL}/{resource}",
        {"key": api_key, **params},
    )


def fetch_recent_video_ids(
    client: HttpClient,
    channel_id: str,
    api_key: str,
) -> list[str]:
    data = youtube_get(
        client,
        "playlistItems",
        api_key,
        part="contentDetails",
        playlistId=uploads_playlist_id(channel_id),
        maxResults=MAX_RECENT_UPLOADS,
    )
    return [
        item["contentDetails"]["videoId"]
        for item in data.get("items", [])
        if item.get("contentDetails", {}).get("videoId")
    ]


def fetch_video_details(
    client: HttpClient,
    video_ids: list[str],
    api_key: str,
) -> dict[str, dict[str, Any]]:
    if not video_ids:
        return {}

    data = youtube_get(
        client,
        "videos",
        api_key,
        part="snippet,liveStreamingDetails,status",
        id=",".join(dict.fromkeys(video_ids)),
        maxResults=50,
    )
    return {item["id"]: item for item in data.get("items", [])}


def is_live(video: dict[str, Any]) -> bool:
    snippet = video.get("snippet", {})
    details = video.get("liveStreamingDetails", {})
    return (
        snippet.get("liveBroadcastContent") == "live"
        and bool(details.get("actualStartTime"))
        and not details.get("actualEndTime")
        and video.get("status", {}).get("privacyStatus") == "public"
    )


def send_discord_notification(
    client: HttpClient,
    webhook_url: str,
    channel: dict[str, str],
    video: dict[str, Any],
    webhook_username: str = "YouTube 直播通知",
    webhook_avatar_url: str = "",
) -> None:
    snippet = video.get("snippet", {})
    video_id = video["id"]
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    thumbnails = snippet.get("thumbnails", {})
    thumbnail = (
        thumbnails.get("maxres")
        or thumbnails.get("standard")
        or thumbnails.get("high")
        or {}
    ).get("url")

    embed: dict[str, Any] = {
        "title": snippet.get("title") or f"{channel['name']} 正在直播",
        "url": video_url,
        "description": f"[{channel['name']} 的 YouTube 頻道](https://www.youtube.com/{channel['handle']})",
        "color": 0xFF0000,
        "fields": [
            {
                "name": "開始時間",
                "value": f"<t:{iso_to_unix(video['liveStreamingDetails']['actualStartTime'])}:R>",
                "inline": True,
            }
        ],
    }
    if thumbnail:
        embed["image"] = {"url": thumbnail}

    payload = {
        "username": webhook_username,
        "content": f"@everyone\n🔴 **{channel['name']} 開始直播了！**\n{video_url}",
        "embeds": [embed],
        "allowed_mentions": {"parse": ["everyone"]},
    }
    if webhook_avatar_url:
        payload["avatar_url"] = webhook_avatar_url
    client.post_json(webhook_url, payload)


def iso_to_unix(value: str) -> int:
    from datetime import datetime

    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def main() -> int:
    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    webhook_username = (
        os.environ.get("DISCORD_WEBHOOK_USERNAME", "YouTube 直播通知").strip()
        or "YouTube 直播通知"
    )
    webhook_avatar_url = os.environ.get("DISCORD_WEBHOOK_AVATAR_URL", "").strip()
    if not api_key or not webhook_url:
        missing = [
            name
            for name, value in (
                ("YOUTUBE_API_KEY", api_key),
                ("DISCORD_WEBHOOK_URL", webhook_url),
            )
            if not value
        ]
        print(f"缺少環境變數：{', '.join(missing)}", file=sys.stderr)
        return 2

    channels = load_json(CHANNELS_FILE, [])
    state = load_json(STATE_FILE, {"channels": {}})
    state.setdefault("channels", {})
    client = HttpClient()

    recent_by_channel: dict[str, list[str]] = {}
    errors: list[str] = []
    for channel in channels:
        try:
            recent_by_channel[channel["channel_id"]] = fetch_recent_video_ids(
                client, channel["channel_id"], api_key
            )
        except Exception as error:
            errors.append(f"{channel['name']} 影片清單讀取失敗：{error}")

    all_video_ids = [
        video_id
        for video_ids in recent_by_channel.values()
        for video_id in video_ids
    ]
    try:
        videos = fetch_video_details(client, all_video_ids, api_key)
    except Exception as error:
        print(f"YouTube 影片狀態讀取失敗：{error}", file=sys.stderr)
        return 1

    for channel in channels:
        channel_id = channel["channel_id"]
        if channel_id not in recent_by_channel:
            continue

        channel_state = state["channels"].setdefault(
            channel_id,
            {"notified_video_ids": []},
        )
        notified = list(channel_state.get("notified_video_ids", []))
        live_videos = [
            videos[video_id]
            for video_id in recent_by_channel[channel_id]
            if video_id in videos and is_live(videos[video_id])
        ]

        if not live_videos:
            print(f"⚪ {channel['name']}：目前未直播")
            continue

        for video in live_videos:
            video_id = video["id"]
            if video_id in notified:
                print(f"🟢 {channel['name']}：直播中，已通知")
                continue

            try:
                send_discord_notification(
                    client,
                    webhook_url,
                    channel,
                    video,
                    webhook_username,
                    webhook_avatar_url,
                )
            except Exception as error:
                errors.append(f"{channel['name']} Discord 通知失敗：{error}")
                continue

            notified.append(video_id)
            channel_state["notified_video_ids"] = notified[-MAX_NOTIFIED_IDS:]
            print(f"🔴 {channel['name']}：已送出開播通知")

    save_state(state)

    if errors:
        for error in errors:
            print(f"⚠️ {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
