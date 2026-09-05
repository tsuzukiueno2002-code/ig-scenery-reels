#!/usr/bin/env python3
"""
TikTok用 世界の都市ガイドリール 自動生成スクリプト(1分・都市ごとに複数スポット合成版)

流れ:
  1. data/cities.json からランダムに都市を選ぶ
  2. その都市の各スポットについて、Pexels APIで縦動画(portrait)素材を検索・ダウンロード
  3. スポットごとに ffmpeg で 1080x1920 / 15秒 に整形し、スポット名+ナレーション字幕を焼き込み
  4. 全スポットの動画をつなげて1本の約60秒動画にする
  5. assets/bgm 内のBGMをランダムに1曲、動画全体にミックス
  6. output/ に mp4 として書き出す

環境変数:
  PEXELS_API_KEY   必須
  CITIES_PER_RUN   1回の実行で生成する都市数(デフォルト1)
"""

import json
import os
import random
import subprocess
import sys
import textwrap
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CITIES_FILE = ROOT / "data" / "cities.json"
BGM_DIR = ROOT / "assets" / "bgm"
FONT_PATH = ROOT / "assets" / "fonts" / "NotoSansJP-Bold.ttf"
OUTPUT_DIR = ROOT / "output"
HISTORY_FILE = ROOT / "data" / "history.json"

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
CITIES_PER_RUN = int(os.environ.get("CITIES_PER_RUN", "1"))
SPOT_SECONDS = 15  # スポット1つあたりの秒数
TARGET_W, TARGET_H = 1080, 1920

COMMON_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def load_cities():
    with open(CITIES_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_history():
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history[-200:], f, ensure_ascii=False, indent=2)


def pick_cities(n):
    """直近使った都市を避けつつランダムにn件選ぶ"""
    cities = load_cities()
    history = load_history()
    recent_cities = {h["city"] for h in history[-10:]}
    candidates = [c for c in cities if c["city"] not in recent_cities]
    if len(candidates) < n:
        candidates = cities
    random.shuffle(candidates)
    return candidates[:n]


def search_pexels_video(query):
    url = (
        "https://api.pexels.com/videos/search"
        f"?query={urllib.parse.quote(query)}&orientation=portrait&size=medium&per_page=5"
    )
    headers = dict(COMMON_HEADERS)
    headers["Authorization"] = PEXELS_API_KEY
    req = urllib.request.Request(url, headers=headers)
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
    req = urllib.request.Request(url, headers=COMMON_HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as f:
        f.write(resp.read())


def pick_bgm():
    tracks = list(BGM_DIR.glob("*.mp3"))
    if not tracks:
        return None
    return random.choice(tracks)


def wrap_lines(text, width=14):
    return textwrap.wrap(text, width=width)


def _escape_drawtext(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\u2019")
        .replace("%", "\\%")
    )


def build_segment(raw_video: Path, spot_label: str, narration: str, out_path: Path):
    """1スポットぶんの動画セグメントを作る(音声なし・SPOT_SECONDS秒)"""
    label_escaped = _escape_drawtext(spot_label)

    vf_parts = [
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase",
        f"crop={TARGET_W}:{TARGET_H}",
        f"drawtext=fontfile='{FONT_PATH}':text='{label_escaped}':"
        f"fontcolor=white:fontsize=54:borderw=3:bordercolor=black@0.7:"
        f"x=(w-text_w)/2:y=h-260",
    ]

    if narration:
        lines = wrap_lines(narration, width=14)
        line_height = 58
        top_y = 130
        band_height = 70 + line_height * len(lines)
        vf_parts.append(f"drawbox=x=0:y=100:w={TARGET_W}:h={band_height}:color=black@0.45:t=fill")
        for i, line in enumerate(lines):
            line_escaped = _escape_drawtext(line)
            y = top_y + i * line_height
            vf_parts.append(
                f"drawtext=fontfile='{FONT_PATH}':text='{line_escaped}':"
                f"fontcolor=white:fontsize=42:"
                f"x=(w-text_w)/2:y={y}"
            )

    vf_parts += [
        "fade=t=in:st=0:d=0.3",
        f"fade=t=out:st={SPOT_SECONDS - 0.4}:d=0.4",
    ]
    vf = ",".join(vf_parts)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(raw_video),
        "-t", str(SPOT_SECONDS),
        "-vf", vf,
        "-an",
        "-r", "30",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)


def concat_segments(segment_paths, city_label: str, bgm: Path, out_path: Path):
    """複数セグメントをつなげ、BGMを1本乗せて最終動画にする"""
    list_file = OUTPUT_DIR / "_concat_list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for p in segment_paths:
            f.write(f"file '{p.resolve()}'\n")

    silent_path = OUTPUT_DIR / "_silent_concat.mp4"
    cmd_concat = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(silent_path),
    ]
    subprocess.run(cmd_concat, check=True)

    total_seconds = SPOT_SECONDS * len(segment_paths)
    cmd = ["ffmpeg", "-y", "-i", str(silent_path)]
    if bgm:
        cmd += ["-stream_loop", "-1", "-i", str(bgm)]
        cmd += [
            "-filter_complex",
            f"[1:a]afade=t=out:st={total_seconds - 1.5}:d=1.5,volume=0.35[a]",
            "-map", "0:v", "-map", "[a]",
            "-shortest",
        ]
    else:
        cmd += ["-an"]
    cmd += [
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)

    list_file.unlink(missing_ok=True)
    silent_path.unlink(missing_ok=True)


def main():
    if not PEXELS_API_KEY:
        print("ERROR: PEXELS_API_KEY が設定されていません", file=sys.stderr)
        sys.exit(1)

    OUTPUT_DIR.mkdir(exist_ok=True)
    history = load_history()
    cities = pick_cities(CITIES_PER_RUN)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    results = []

    for ci, city_entry in enumerate(cities, start=1):
        city, country, spots = city_entry["city"], city_entry["country"], city_entry["spots"]
        print(f"[都市 {ci}/{len(cities)}] {city}({country}) を生成中...")
        segment_paths = []
        try:
            for si, spot in enumerate(spots, start=1):
                name, query = spot["name"], spot["query"]
                narration = spot.get("narration", "")
                print(f"  [スポット {si}/{len(spots)}] {name} を検索中...")
                video_url = search_pexels_video(query)
                if not video_url:
                    print(f"    素材が見つからずスキップ: {query}")
                    continue
                raw_path = OUTPUT_DIR / f"_raw_{ci}_{si}.mp4"
                download(video_url, raw_path)

                spot_label = f"{name}・{city}"
                seg_path = OUTPUT_DIR / f"_seg_{ci}_{si}.mp4"
                build_segment(raw_path, spot_label, narration, seg_path)
                raw_path.unlink(missing_ok=True)
                segment_paths.append(seg_path)

            if not segment_paths:
                print(f"  すべてのスポットで素材取得に失敗、{city}はスキップ")
                continue

            bgm = pick_bgm()
            out_name = f"{today}_{ci:02d}_{city}.mp4".replace(" ", "")
            out_path = OUTPUT_DIR / out_name
            concat_segments(segment_paths, city, bgm, out_path)

            for seg in segment_paths:
                seg.unlink(missing_ok=True)

            results.append({
                "city": city,
                "country": country,
                "spots": [s["name"] for s in spots],
                "file": out_name,
            })
            history.append({"city": city, "country": country, "date": today})
            print(f"  -> {out_name} 生成完了")
        except Exception as e:
            print(f"  ERROR: {city} の生成に失敗: {e}", file=sys.stderr)
            for seg in segment_paths:
                seg.unlink(missing_ok=True)

    save_history(history)

    manifest_path = OUTPUT_DIR / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"完了: {len(results)}都市ぶん生成")


if __name__ == "__main__":
    main()
