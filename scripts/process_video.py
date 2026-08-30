import glob
import random
import subprocess


def process(input_path: str, output_path: str, caption: str, duration: int = 15) -> None:
    bgm_files = glob.glob("assets/bgm/*.mp3")
    if not bgm_files:
        raise RuntimeError("assets/bgm/ にmp3ファイルを1つ以上置いてください")
    bgm = random.choice(bgm_files)

    # テロップ位置(下から15%あたり)。フォントは環境にあるものを使用。
    drawtext = (
        f"drawtext=text='{caption}':fontcolor=white:fontsize=54:"
        f"box=1:boxcolor=black@0.4:boxborderw=20:"
        f"x=(w-text_w)/2:y=h-h*0.15"
    )

    vf = f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,{drawtext}"

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-i", bgm,
        "-t", str(duration),
        "-vf", vf,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-c:a", "aac",
        "-shortest",
        output_path,
    ]
    subprocess.run(cmd, check=True)
