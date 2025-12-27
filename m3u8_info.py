#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取m3u8视频信息（视频长度、文件大小）
"""

import os
import re
import sys
import time
import requests
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("m3u8_info.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 禁用SSL警告
requests.packages.urllib3.disable_warnings()

# 全局变量
TOTAL_DURATION = 0.0
TOTAL_SIZE = 0
SUCCESS_COUNT = 0
FAILED_COUNT = 0
TIMEOUT = 30
MAX_WORKERS = 10


class M3U8InfoGetter:
    def __init__(self, timeout=TIMEOUT, max_workers=MAX_WORKERS):
        """初始化M3U8信息获取器"""
        self.timeout = timeout
        self.max_workers = max_workers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.session.verify = False  # 禁用SSL验证

    def get_m3u8_content(self, url):
        """获取m3u8文件内容"""
        try:
            logger.info(f"正在获取m3u8文件: {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = 'utf-8'
            return response.text
        except Exception as e:
            logger.error(f"获取m3u8文件失败: {e}")
            return None

    def is_master_playlist(self, m3u8_content):
        """判断是否为主播放列表（包含#EXT-X-STREAM-INF）"""
        return '#EXT-X-STREAM-INF' in m3u8_content

    def get_best_quality_stream(self, m3u8_content, base_url):
        """获取最高质量的流地址"""
        streams = []
        lines = m3u8_content.strip().split('\n')

        for i, line in enumerate(lines):
            if line.startswith('#EXT-X-STREAM-INF'):
                # 解析带宽信息
                bandwidth_match = re.search(r'BANDWIDTH=(\d+)', line)
                bandwidth = int(bandwidth_match.group(1)) if bandwidth_match else 0

                # 获取下一行的URL
                if i + 1 < len(lines) and not lines[i + 1].startswith('#'):
                    stream_url = lines[i + 1].strip()
                    # 构建完整URL
                    if not stream_url.startswith(('http://', 'https://')):
                        stream_url = urljoin(base_url, stream_url)
                    streams.append((bandwidth, stream_url))

        if streams:
            # 按带宽排序，返回最高带宽的流
            streams.sort(reverse=True, key=lambda x: x[0])
            best_stream = streams[0]
            logger.info(f"选择最高质量流: 带宽={best_stream[0]}bps, URL={best_stream[1]}")
            return best_stream[1]

        logger.warning("未找到流信息")
        return None

    def get_segment_info(self, m3u8_content, base_url):
        """获取所有片段信息"""
        segments = []
        lines = m3u8_content.strip().split('\n')

        for i, line in enumerate(lines):
            if line.startswith('#EXTINF'):
                # 解析时长
                duration_match = re.search(r'#EXTINF:(\d+\.?\d*)', line)
                if duration_match:
                    duration = float(duration_match.group(1))

                    # 获取下一行的URL
                    if i + 1 < len(lines) and not lines[i + 1].startswith('#'):
                        segment_url = lines[i + 1].strip()
                        # 构建完整URL
                        if not segment_url.startswith(('http://', 'https://')):
                            segment_url = urljoin(base_url, segment_url)
                        segments.append((duration, segment_url))

        logger.info(f"找到 {len(segments)} 个视频片段")
        return segments

    def get_file_size(self, url):
        """获取文件大小（字节）"""
        global SUCCESS_COUNT, FAILED_COUNT
        try:
            response = self.session.head(url, timeout=self.timeout)
            response.raise_for_status()

            if 'Content-Length' in response.headers:
                size = int(response.headers['Content-Length'])
                SUCCESS_COUNT += 1
                return size
            else:
                logger.warning(f"未找到Content-Length头: {url}")
                FAILED_COUNT += 1
                return 0
        except Exception as e:
            logger.error(f"获取文件大小失败 {url}: {e}")
            FAILED_COUNT += 1
            return 0

    def process_segment(self, segment):
        """处理单个片段"""
        duration, url = segment
        size = self.get_file_size(url)
        return duration, size

    def get_m3u8_info(self, m3u8_url):
        """获取m3u8视频信息"""
        global TOTAL_DURATION, TOTAL_SIZE, SUCCESS_COUNT, FAILED_COUNT

        # 重置全局变量
        TOTAL_DURATION = 0.0
        TOTAL_SIZE = 0
        SUCCESS_COUNT = 0
        FAILED_COUNT = 0

        start_time = time.time()

        # 获取主m3u8文件
        main_content = self.get_m3u8_content(m3u8_url)
        if not main_content:
            return None

        final_m3u8_url = m3u8_url
        final_content = main_content

        # 如果是主播放列表，获取子播放列表
        if self.is_master_playlist(main_content):
            sub_m3u8_url = self.get_best_quality_stream(main_content, m3u8_url)
            if sub_m3u8_url:
                final_m3u8_url = sub_m3u8_url
                final_content = self.get_m3u8_content(sub_m3u8_url)
                if not final_content:
                    return None

        # 获取片段信息
        segments = self.get_segment_info(final_content, final_m3u8_url)
        if not segments:
            logger.error("未找到视频片段信息")
            return None

        # 计算总时长
        total_duration = sum(duration for duration, _ in segments)
        TOTAL_DURATION = total_duration

        logger.info(f"总时长: {total_duration:.2f}秒")

        # 使用线程池获取文件大小
        logger.info(f"开始获取文件大小信息（使用{self.max_workers}个线程）...")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            results = list(executor.map(self.process_segment, segments))

        # 计算总大小
        total_size = sum(size for _, size in results)
        TOTAL_SIZE = total_size

        # 计算统计信息
        elapsed_time = time.time() - start_time

        info = {
            'url': m3u8_url,
            'final_url': final_m3u8_url,
            'duration': total_duration,
            'size': total_size,
            'segment_count': len(segments),
            'success_count': SUCCESS_COUNT,
            'failed_count': FAILED_COUNT,
            'elapsed_time': elapsed_time
        }

        self.print_info(info)
        return info

    def print_info(self, info):
        """打印信息"""
        print("\n" + "=" * 60)
        print("M3U8视频信息")
        print("=" * 60)
        print(f"原始URL: {info['url']}")
        print(f"最终URL: {info['final_url']}")
        print(f"视频时长: {self.format_duration(info['duration'])}")
        print(f"文件大小: {self.format_size(info['size'])}")
        print(f"片段数量: {info['segment_count']}")
        print(f"成功获取大小: {info['success_count']} 个")
        print(f"获取失败: {info['failed_count']} 个")
        print(f"处理时间: {info['elapsed_time']:.2f} 秒")
        print("=" * 60)

    def format_duration(self, seconds):
        """格式化时长"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours}小时{minutes}分钟{secs}秒"
        elif minutes > 0:
            return f"{minutes}分钟{secs}秒"
        else:
            return f"{secs}秒"

    def format_size(self, bytes_size):
        """格式化文件大小"""
        if bytes_size < 0:
            return "未知"

        units = ['B', 'KB', 'MB', 'GB', 'TB']
        size = float(bytes_size)
        unit_index = 0

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1

        return f"{size:.2f} {units[unit_index]}"


def main():
    """主函数"""
    if len(sys.argv) > 1:
        m3u8_url = sys.argv[1]
    else:
        m3u8_url = input("请输入m3u8文件URL: ").strip()

    if not m3u8_url:
        print("错误: URL不能为空")
        sys.exit(1)

    getter = M3U8InfoGetter()
    getter.get_m3u8_info(m3u8_url)


if __name__ == "__main__":
    main()