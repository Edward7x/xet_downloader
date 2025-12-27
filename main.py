import json
import subprocess
import re
import sys
import time
import requests
from pathlib import Path
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import os
import shutil
import string
import random

# 引入解密库
try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad

    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

# --- 配置区域 ---
LOG_FILE = "m3u8_download.log"
INPUT_FILE = "m3u8_list.json"
OUTPUT_DIR = Path("videos")
MAX_THREADS = 16  # 适当增加线程数
DOWNLOAD_TIMEOUT = 30
CHUNK_SIZE = 1024 * 1024
FFMPEG_TIMEOUT = 600  # 合并超时时间

# --- 日志配置 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 禁用SSL警告
requests.packages.urllib3.disable_warnings()

# 全局请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Referer": "https://h5.xet.citv.cn"  # 根据实际情况修改
}


def clean_filename(name):
    """生成安全的文件名"""
    valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    cleaned = ''.join(c for c in name if c in valid_chars)
    return cleaned.strip()[:50] or "untitled_video"


class M3U8Downloader:
    def __init__(self, url, title, output_dir):
        self.url = url
        self.title = clean_filename(title)
        self.output_dir = output_dir
        self.temp_dir = output_dir / f"temp_{self.title}_{int(time.time())}"
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.session.verify = False

        self.key_iv = None
        self.key_content = None
        self.segments = []

    def get_content(self, url, is_binary=False):
        """通用的网络请求方法"""
        try:
            resp = self.session.get(url, timeout=DOWNLOAD_TIMEOUT)
            resp.raise_for_status()
            if is_binary:
                return resp.content
            resp.encoding = 'utf-8'
            return resp.text
        except Exception as e:
            logger.error(f"请求失败 [{url}]: {e}")
            return None

    def parse_m3u8(self):
        """解析M3U8，处理嵌套和加密"""
        content = self.get_content(self.url)
        if not content:
            return False

        # 1. 检查是否是主播放列表（Master Playlist），如果是则选择最高码率
        if "#EXT-X-STREAM-INF" in content:
            logger.info("检测到多码率列表，选择最高清晰度...")
            lines = content.splitlines()
            best_bandwidth = -1
            best_url = None

            for i, line in enumerate(lines):
                if "#EXT-X-STREAM-INF" in line:
                    bw_match = re.search(r'BANDWIDTH=(\d+)', line)
                    bw = int(bw_match.group(1)) if bw_match else 0
                    if bw > best_bandwidth and i + 1 < len(lines):
                        sub_url = lines[i + 1].strip()
                        if not sub_url.startswith("#"):
                            best_bandwidth = bw
                            best_url = urljoin(self.url, sub_url)

            if best_url:
                logger.info(f"跳转至子播放列表: {best_url}")
                self.url = best_url
                content = self.get_content(best_url)
                if not content: return False

        # 2. 解析加密 Key (AES-128)
        # 格式示例: #EXT-X-KEY:METHOD=AES-128,URI="key.key",IV=0x...
        key_match = re.search(r'#EXT-X-KEY:METHOD=([^,]+),URI="([^"]+)"(?:,IV=(0x[0-9a-fA-F]+))?', content)
        if key_match:
            method, key_uri, iv_hex = key_match.groups()
            if method.upper() == 'AES-128':
                if not HAS_CRYPTO:
                    logger.error("检测到加密视频，但未安装 pycryptodome 库，无法解密！")
                    return False

                full_key_url = urljoin(self.url, key_uri)
                logger.info(f"检测到加密，正在获取密钥: {full_key_url}")
                self.key_content = self.get_content(full_key_url, is_binary=True)

                if not self.key_content:
                    logger.error("无法获取解密密钥")
                    return False

                # 处理 IV
                if iv_hex:
                    self.key_iv = bytes.fromhex(iv_hex.replace("0x", ""))
                # 如果没有IV，通常使用序列号（在下载时处理）
            else:
                logger.warning(f"不支持的加密方法: {method}，可能会导致合并失败")

        # 3. 提取分片链接
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("#EXTINF"):
                # 尝试获取下一行作为URL
                for j in range(i + 1, min(i + 5, len(lines))):
                    seg_line = lines[j].strip()
                    if seg_line and not seg_line.startswith("#"):
                        full_seg_url = urljoin(self.url, seg_line)
                        self.segments.append({
                            "index": len(self.segments),
                            "url": full_seg_url
                        })
                        break

        logger.info(f"解析完成，共 {len(self.segments)} 个分片")
        return len(self.segments) > 0

    def decrypt_segment(self, content, sequence_number):
        """解密分片数据"""
        if not self.key_content:
            return content

        iv = self.key_iv
        if not iv:
            # 如果 M3U8 里没给 IV，标准是用序列号(big-endian binary)
            iv = sequence_number.to_bytes(16, byteorder='big')

        cryptor = AES.new(self.key_content, AES.MODE_CBC, iv)
        try:
            # M3U8 的 AES-128 通常是满块对齐的，但也可能有 padding
            return cryptor.decrypt(content)
        except Exception as e:
            logger.warning(f"解密分片 {sequence_number} 失败: {e}")
            return content  # 尝试返回原始内容

    def download_segment(self, segment):
        """下载单个分片任务"""
        idx = segment['index']
        url = segment['url']
        save_path = self.temp_dir / f"{idx:05d}.ts"

        if save_path.exists() and save_path.stat().st_size > 0:
            return True

        for attempt in range(3):
            try:
                content = self.get_content(url, is_binary=True)
                if not content:
                    raise Exception("Empty content")

                # 解密
                if self.key_content:
                    content = self.decrypt_segment(content, idx)

                # 简单校验：TS流通常以 0x47 开头
                # 注意：如果是解密后的数据，也应该符合这个规则。
                # 如果不校验，很容易合并进 404 HTML 导致 FFmpeg 崩溃
                if content and len(content) > 188 and content[0] != 0x47:
                    # 尝试找一下同步字节，有时候数据头有点垃圾数据
                    sync_offset = content.find(b'\x47')
                    if sync_offset != -1 and sync_offset < 1000:
                        content = content[sync_offset:]

                with open(save_path, 'wb') as f:
                    f.write(content)
                return True
            except Exception as e:
                if attempt == 2:
                    logger.warning(f"分片 {idx} 下载失败: {e}")
                time.sleep(1)
        return False

    def merge_segments(self, output_file):
        """使用 FFmpeg Concat 协议合并"""
        ts_files = sorted(list(self.temp_dir.glob("*.ts")))
        if not ts_files:
            return False

        # 生成 concat 列表文件 (使用绝对路径，且统一用正斜杠防止转义问题)
        concat_file_path = self.temp_dir / "filelist.txt"
        with open(concat_file_path, "w", encoding="utf-8") as f:
            for ts in ts_files:
                # 关键：Windows路径在ffmpeg filelist中需要小心处理
                # 使用 to_posix() 可以将反斜杠转换为正斜杠，这在 ffmpeg 中是通用的
                safe_path = ts.absolute().as_posix()
                f.write(f"file '{safe_path}'\n")

        logger.info(f"开始合并 {len(ts_files)} 个分片 -> {output_file.name}")

        # 命令构建：直接合并为 MP4，不经过中间巨大的 TS 文件，减少出错概率
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file_path.absolute()),
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",  # 修复音频流格式，防止 MP4 没声音
            str(output_file.absolute())
        ]

        try:
            # Windows 下隐藏控制台窗口
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo
            )
            stdout, stderr = process.communicate(timeout=FFMPEG_TIMEOUT)

            if process.returncode != 0:
                logger.error(f"FFmpeg合并失败: {stderr.decode('utf-8', errors='ignore')}")
                return False

            # 校验输出文件
            if output_file.exists() and output_file.stat().st_size > 1024:
                return True
            return False

        except Exception as e:
            logger.error(f"合并过程异常: {e}")
            return False

    def run(self):
        """执行下载流程"""
        print(f"\n🎬 开始任务: {self.title}")

        # 1. 创建目录
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        final_mp4 = self.output_dir / f"{self.title}.mp4"
        if final_mp4.exists():
            print(f"✅ 文件已存在，跳过")
            return True

        # 2. 解析
        if not self.parse_m3u8():
            print("❌ 解析M3U8失败")
            return False

        # 3. 下载
        total = len(self.segments)
        completed = 0
        print(f"📥 开始下载 {total} 个分片 (线程: {MAX_THREADS})...")

        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            futures = [executor.submit(self.download_segment, seg) for seg in self.segments]

            for i, future in enumerate(as_completed(futures)):
                if future.result():
                    completed += 1

                # 简单的进度条
                percent = (i + 1) / total * 100
                sys.stdout.write(f"\r进度: {percent:.1f}% [{completed}/{total}]")
                sys.stdout.flush()

        print("")  # 换行

        if completed < total * 0.95:
            print("❌ 丢失分片过多(>5%)，放弃合并")
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            return False

        # 4. 合并
        print("🔄 正在合并...")
        if self.merge_segments(final_mp4):
            print(f"✅ 下载成功: {final_mp4}")
            # 成功后清理临时文件
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            return True
        else:
            print("❌ 合并失败，保留临时文件以便检查")
            return False


def main():
    if not Path(INPUT_FILE).exists():
        # 创建示例文件
        with open(INPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump([{"title": "Demo", "m3u8": "http://example.com/video.m3u8"}], f, indent=2)
        print(f"请在 {INPUT_FILE} 中填入视频信息")
        return

    # 检查 FFmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print("❌ 错误: 未找到 ffmpeg，请先安装 ffmpeg 并添加到环境变量 PATH 中。")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        tasks = json.load(f)

    print(f"🚀 加载了 {len(tasks)} 个任务")

    for task in tasks:
        downloader = M3U8Downloader(
            url=task.get('m3u8'),
            title=task.get('title', '未命名视频'),
            output_dir=OUTPUT_DIR
        )
        downloader.run()


if __name__ == "__main__":
    main()