import unittest

from monitor import (
    fetch_video_details,
    is_live,
    send_discord_notification,
    uploads_playlist_id,
)


class FakeClient:
    def __init__(self):
        self.url = None
        self.payload = None

    def post_json(self, url, payload):
        self.url = url
        self.payload = payload


class FakeYouTubeClient:
    def __init__(self):
        self.batch_sizes = []

    def get_json(self, _url, params):
        ids = params["id"].split(",")
        self.batch_sizes.append(len(ids))
        return {"items": [{"id": video_id} for video_id in ids]}


class MonitorTests(unittest.TestCase):
    def test_uploads_playlist_id(self):
        self.assertEqual(
            uploads_playlist_id("UCR7sl-Im8bJZAABhvY7KGhg"),
            "UUR7sl-Im8bJZAABhvY7KGhg",
        )

    def test_live_video(self):
        video = {
            "snippet": {"liveBroadcastContent": "live"},
            "liveStreamingDetails": {"actualStartTime": "2026-09-03T01:00:00Z"},
            "status": {"privacyStatus": "public"},
        }
        self.assertTrue(is_live(video))

    def test_ended_video_is_not_live(self):
        video = {
            "snippet": {"liveBroadcastContent": "none"},
            "liveStreamingDetails": {
                "actualStartTime": "2026-09-03T01:00:00Z",
                "actualEndTime": "2026-09-03T03:00:00Z",
            },
            "status": {"privacyStatus": "public"},
        }
        self.assertFalse(is_live(video))

    def test_custom_webhook_identity(self):
        client = FakeClient()
        video = {
            "id": "abcdefghijk",
            "snippet": {
                "title": "測試直播",
                "thumbnails": {"high": {"url": "https://example.com/live.jpg"}},
            },
            "liveStreamingDetails": {"actualStartTime": "2026-09-03T01:00:00Z"},
        }
        channel = {"name": "BIZzzz", "handle": "@bbbbiz"}

        send_discord_notification(
            client,
            "https://discord.example/webhook",
            channel,
            video,
            "直播小幫手",
            "https://example.com/avatar.png",
        )

        self.assertEqual(client.payload["username"], "直播小幫手")
        self.assertEqual(
            client.payload["avatar_url"],
            "https://example.com/avatar.png",
        )

    def test_video_details_are_split_into_api_sized_batches(self):
        client = FakeYouTubeClient()
        video_ids = [f"video-{number}" for number in range(60)]

        videos = fetch_video_details(client, video_ids, "test-key")

        self.assertEqual(client.batch_sizes, [50, 10])
        self.assertEqual(len(videos), 60)


if __name__ == "__main__":
    unittest.main()
