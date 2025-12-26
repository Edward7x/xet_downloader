import logging
from pathlib import Path
import subprocess

# 日志初始化
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

def setup_logger():
    logger = logging.getLogger("xet_downloader")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")

    # 控制台
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    # 文件
    fh = logging.FileHandler(LOG_DIR / "download.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    logger.addHandler(ch)
    logger.addHandler(fh)
    return logger

logger = setup_logger()

# 文件名安全化
def safe_name(name: str) -> str:
    return "".join(c for c in name if c not in r'\/:*?"<>|').strip()

# 获取 m3u8 总时长（秒）
def get_duration(url):
    cmd = [
        "ffprobe",
        "-i", url,
        "-show_entries", "format=duration",
        "-v", "quiet",
        "-of", "csv=p=0"
    ]
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True, timeout=10)
        return float(r.stdout.strip())
    except Exception:
        logger.warning(f"无法获取时长: {url}")
        return None
