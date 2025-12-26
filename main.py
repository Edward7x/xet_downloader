import json
import subprocess
from pathlib import Path

REFERER = "https://h5.xet.citv.cn"
UA = "Mozilla/5.0"

INPUT_FILE = "m3u8_list.json"
OUTPUT_DIR = Path("videos")
OUTPUT_DIR.mkdir(exist_ok=True)

def safe_name(name: str) -> str:
    return "".join(c for c in name if c not in r'\/:*?"<>|')

def download(item):
    title = safe_name(item["title"])
    url = item["m3u8"]
    out = OUTPUT_DIR / f"{title}.mp4"

    if out.exists():
        print(f"⏭ 跳过已存在：{title}")
        return

    cmd = [
        "ffmpeg",
        "-y",
        "-user_agent", UA,
        "-headers", f"Referer: {REFERER}",
        "-i", url,
        "-c", "copy",
        str(out)
    ]

    print(f"⬇️  下载中：{title}")
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if r.returncode != 0:
        if "Unable to open key file" in r.stderr:
            print("🔒 DRM 检测，已跳过")
        else:
            print("❌ 失败")
            print(r.stderr[-400:])
    else:
        print(f"✅ 完成：{title}")

def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    for item in data:
        download(item)

if __name__ == "__main__":
    main()
