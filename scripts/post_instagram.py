import os
import time
import requests

IG_USER_ID = os.environ["IG_USER_ID"]
IG_ACCESS_TOKEN = os.environ["IG_ACCESS_TOKEN"]
GRAPH_BASE = "https://graph.facebook.com/v19.0"


def publish_reel(video_url: str, caption: str) -> str:
    # 1. コンテナ作成
    create_url = f"{GRAPH_BASE}/{IG_USER_ID}/media"
    payload = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": IG_ACCESS_TOKEN,
    }
    r = requests.post(create_url, data=payload, timeout=30)
    r.raise_for_status()
    creation_id = r.json()["id"]

    # 2. 処理完了を待つ(動画変換に少し時間がかかる)
    status_url = f"{GRAPH_BASE}/{creation_id}"
    for _ in range(30):
        r = requests.get(status_url, params={
            "fields": "status_code",
            "access_token": IG_ACCESS_TOKEN,
        }, timeout=30)
        status = r.json().get("status_code")
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise RuntimeError("Instagram側の動画処理に失敗しました")
        time.sleep(10)
    else:
        raise RuntimeError("タイムアウト: 動画処理が完了しませんでした")

    # 3. 公開
    publish_url = f"{GRAPH_BASE}/{IG_USER_ID}/media_publish"
    r = requests.post(publish_url, data={
        "creation_id": creation_id,
        "access_token": IG_ACCESS_TOKEN,
    }, timeout=30)
    r.raise_for_status()
    return r.json()["id"]
