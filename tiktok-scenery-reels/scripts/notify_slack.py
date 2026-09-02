#!/usr/bin/env python3
"""
output/manifest.json を元に、生成された動画のGitHub Raw URLをSlackへ通知する。

環境変数:
  SLACK_WEBHOOK_URL   必須
  GITHUB_REPOSITORY   例: your-name/tiktok-scenery-reels (Actions内で自動セット)
  GITHUB_REF_NAME     例: main (Actions内で自動セット)
"""

import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "output" / "manifest.json"

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
REPO = os.environ.get("GITHUB_REPOSITORY", "")
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")


def raw_url(filename: str) -> str:
    return f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/output/{filename}"


def main():
    if not SLACK_WEBHOOK_URL:
        print("ERROR: SLACK_WEBHOOK_URL が設定されていません", file=sys.stderr)
        sys.exit(1)
    if not MANIFEST_PATH.exists():
        print("manifest.json が見つかりません。通知をスキップします。")
        return

    with open(MANIFEST_PATH, encoding="utf-8") as f:
        results = json.load(f)

    if not results:
        text = "本日のリール生成: 0本(素材取得に失敗した可能性があります)"
    else:
        lines = [f"*本日の絶景リールが{len(results)}本できました。TikTokへの投稿をお願いします。*", ""]
        for r in results:
            lines.append(f"・{r['place']}({r['country']})\n  {raw_url(r['file'])}")
        text = "\n".join(lines)

    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        SLACK_WEBHOOK_URL, data=payload, headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req, timeout=15)
    print("Slack通知を送信しました。")


if __name__ == "__main__":
    main()
