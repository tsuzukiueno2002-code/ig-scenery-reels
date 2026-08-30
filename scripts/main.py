import os
import random
import subprocess

from locations import LOCATIONS
from fetch_video import download_video
from process_video import process
from post_instagram import publish_reel

RAW_PATH = "reel.mp4"


def push_to_media_branch(local_file: str) -> str:
    repo = os.environ["GITHUB_REPOSITORY"]
    subprocess.run(["git", "config", "user.name", "reel-bot"], check=True)
    subprocess.run(["git", "config", "user.email", "reel-bot@users.noreply.github.com"], check=True)
    subprocess.run(["git", "checkout", "--orphan", "media-temp"], check=True)
    subprocess.run(["git", "reset", "--hard"], check=True)
    subprocess.run(["cp", local_file, RAW_PATH], check=True)
    subprocess.run(["git", "add", RAW_PATH], check=True)
    subprocess.run(["git", "commit", "-m", "reel"], check=True)
    subprocess.run(["git", "branch", "-D", "media"], check=False)
    subprocess.run(["git", "branch", "-m", "media"], check=True)
    subprocess.run(["git", "push", "-f", "origin", "media"], check=True)
    return f"https://raw.githubusercontent.com/{repo}/media/{RAW_PATH}"


def main():
    spot = random.choice(LOCATIONS)
    print(f"選ばれた場所: {spot['caption']}")

    download_video(spot["query"], "raw_input.mp4")
    process("raw_input.mp4", "processed.mp4", spot["caption"])

    video_url = push_to_media_branch("processed.mp4")
    print(f"公開URL: {video_url}")

    caption = f"{spot['caption']}\n\n#絶景 #travel #scenery #reels"
    media_id = publish_reel(video_url, caption)
    print(f"投稿完了: {media_id}")


if __name__ == "__main__":
    main()
