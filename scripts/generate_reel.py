#!/usr/bin/env python3
"""
TikTok用 世界の絶景リール 自動生成スクリプト

流れ:
  1. data/locations.json からランダムに地点を選ぶ
  2. Pexels API で縦動画(portrait)素材を検索・ダウンロード
  3. ffmpeg で 1080x1920 / 15秒 に整形し、地名+国名のテロップを焼き込み
  4. assets/bgm 内のBGMをランダムに1曲ミックス
  5. output/ に mp4 として書き出す

環境変数:
  PEXELS_API_KEY  必須
  DAILY_COUNT     1回の実行で生成する本数(デフォルト5)
  VIDEO_SECONDS   1本あたりの秒数(デフォルト15)
"""

import json
import os
import random
import subprocess
import sys
import textwrap
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCATIONS_FILE = ROOT / "data" / "locations.json"
BGM_DIR = ROOT / "assets" / "bgm"
FONT_PATH = ROOT / "assets" / "fonts" / "NotoSansJP-Bold.ttf"
OUTPUT_DIR = ROOT / "output"
HISTORY_FILE = ROOT / "data" / "history.json"

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
DAILY_COUNT = int(os.environ.get("DAILY_COUNT", "5"))
VIDEO_SECONDS = int(os.environ.get("VIDEO_SECONDS", "15"))
TARGET_W, TARGET_H = 1080, 1920


def load_locations():
    with open(LOCATIONS_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_history():
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history[-200:], f, ensure_ascii=False, indent=2)


def pick_locations(n):
    """直近使った地点を避けつつランダムにn件選ぶ"""
    locations = load_locations()
    history = load_history()
    recent_places = {h["place"] for h in history[-10:]}
    candidates = [loc for loc in locations if loc["place"] not in recent_places]
    if len(candidates) < n:
        candidates = locations
    random.shuffle(candidates)
    return candidates[:n]


def search_pexels_video(query):
    url = (
        "https://api.pexels.com/videos/search"
        f"?query={urllib.parse.quote(query)}&orientation=portrait&size=medium&per_page=5"
    )
    req = urllib.request.Request(url, headers={"Authorization": PEXELS_API_KEY})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    videos = data.get("videos", [])
    if not videos:
        return None
    video = random.choice(videos)
    files = [f for f in video["video_files"] if f.get("width") and f["width"] <= 1920]
    files.sort(key=lambda f: f.get("width", 0), reverse=True)
    return files[0]["link"] if files else video["video_files"][0]["link"]


def download(url, dest: Path):
    urllib.request.urlretrieve(url, dest)


def pick_bgm():
    tracks = list(BGM_DIR.glob("*.mp3"))
    if not tracks:
        return None
    return random.choice(tracks)


def wrap_text_for_drawtext(text, width=16):
    return "\\n".join(textwrap.wrap(text, width=width))


def build_reel(raw_video: Path, place: str, country: str, bgm: Path, out_path: Path):
    label = f"{place}  {country}".strip()
    label_escaped = label.replace(":", "\\:").replace("'", "\u2019")

    vf_parts = [
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase",
        f"crop={TARGET_W}:{TARGET_H}",
        f"drawtext=fontfile='{FONT_PATH}':text='{label_escaped}':"
        f"fontcolor=white:fontsize=54:borderw=3:bordercolor=black@0.7:"
        f"x=(w-text_w)/2:y=h-260",
        "fade=t=in:st=0:d=0.5",
        f"fade=t=out:st={VIDEO_SECONDS - 0.7}:d=0.7",
    ]
    vf = ",".join(vf_parts)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(raw_video),
    ]
    if bgm:
        cmd += ["-stream_loop", "-1", "-i", str(bgm)]
    cmd += [
        "-t", str(VIDEO_SECONDS),
        "-vf", vf,
    ]
    if bgm:
        cmd += [
            "-filter_complex", f"[1:a]afade=t=out:st={VIDEO_SECONDS - 1}:d=1,volume=0.35[a]",
            "-map", "0:v", "-map", "[a]",
        ]
    else:
        cmd += ["-an"]
    cmd += [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)


def main():
    if not PEXELS_API_KEY:
        print("ERROR: PEXELS_API_KEY が設定されていません", file=sys.stderr)
        sys.exit(1)

    OUTPUT_DIR.mkdir(exist_ok=True)
    history = load_history()
    locations = pick_locations(DAILY_COUNT)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    results = []

    for i, loc in enumerate(locations, start=1):
        place, country, query = loc["place"], loc["country"], loc["query"]
        print(f"[{i}/{len(locations)}] {place}({country}) を検索中...")
        try:
            video_url = search_pexels_video(query)
            if not video_url:
                print(f"  素材が見つからずスキップ: {query}")
                continue
            raw_path = OUTPUT_DIR / f"_raw_{i}.mp4"
            download(video_url, raw_path)

            bgm = pick_bgm()
            out_name = f"{today}_{i:02d}_{place}.mp4".replace(" ", "")
            out_path = OUTPUT_DIR / out_name
            build_reel(raw_path, place, country, bgm, out_path)
            raw_path.unlink(missing_ok=True)

            results.append({"place": place, "country": country, "file": out_name})
            history.append({"place": place, "country": country, "date": today})
            print(f"  -> {out_name} 生成完了")
        except Exception as e:
            print(f"  ERROR: {place} の生成に失敗: {e}", file=sys.stderr)

    save_history(history)

    manifest_path = OUTPUT_DIR / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"完了: {len(results)}本生成")


if __name__ == "__main__":
    import urllib.parse
    main()
