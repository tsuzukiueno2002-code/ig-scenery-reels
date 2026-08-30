import os
import random
import requests

PEXELS_KEY = os.environ["PEXELS_API_KEY"]
PIXABAY_KEY = os.environ["PIXABAY_API_KEY"]


def fetch_from_pexels(query: str) -> str | None:
    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": PEXELS_KEY}
    params = {"query": query, "orientation": "portrait", "per_page": 5}
    r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    videos = r.json().get("videos", [])
    if not videos:
        return None
    video = random.choice(videos)
    # 一番高画質に近いファイルを選ぶ
    files = sorted(video["video_files"], key=lambda f: f.get("width", 0), reverse=True)
    return files[0]["link"] if files else None


def fetch_from_pixabay(query: str) -> str | None:
    url = "https://pixabay.com/api/videos/"
    params = {"key": PIXABAY_KEY, "q": query, "per_page": 5}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    hits = r.json().get("hits", [])
    if not hits:
        return None
    video = random.choice(hits)
    return video["videos"]["large"]["url"]


def download_video(query: str, out_path: str) -> None:
    link = fetch_from_pexels(query) or fetch_from_pixabay(query)
    if not link:
        raise RuntimeError(f"動画が見つかりませんでした: {query}")
    r = requests.get(link, stream=True, timeout=60)
    r.raise_for_status()
    with open(out_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
