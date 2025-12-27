# XET Downloader

小鹅通课程视频下载器（油猴 + Python 联动版）

支持自动抓取课程标题、主 m3u8 导出、并发下载、限速控制和实时进度条。支持AES-128加密视频解密，提供视频信息获取功能。

---

## 功能特点

### 油猴脚本
- 自动识别课程页面主 m3u8 地址
- 自动抓取课程标题
- 一键导出 JSON (`m3u8_list.json`) 供 Python 下载器使用
- 提供一键复制功能

### Python 下载器
- 并发下载（可配置最大并发数）
- 支持AES-128加密视频解密
- 实时进度条显示每节课下载进度
- 规范化日志系统（控制台 + 文件）
- 自动跳过已下载文件
- 智能选择最高码率视频流

### M3U8信息获取器
- 获取视频总时长
- 计算视频文件大小
- 统计视频片段数量
- 支持多线程获取信息

---

## 项目结构

```
xet_downloader/
├─ tampermonkey/
│  └─ xet_m3u8_export.user.js    # 油猴脚本
├─ main.py                       # Python 主下载器
├─ m3u8_info.py                  # M3U8视频信息获取器
├─ utils.py                      # 公共函数和工具
├─ requirements.txt              # Python依赖
├─ m3u8_list.json               # 油猴导出的课程列表（示例）
├─ videos/                       # 下载的视频存放目录
├─ logs/                         # 日志目录
└─ README.md
```

---

## 使用说明

### 1. 环境准备

#### 安装FFmpeg
- Windows: 下载并解压[FFmpeg](https://ffmpeg.org/download.html)，将其bin目录添加到系统PATH环境变量
- macOS: 使用Homebrew `brew install ffmpeg`
- Linux: 使用包管理器 `sudo apt install ffmpeg` 或 `sudo yum install ffmpeg`

#### 安装Python依赖
```bash
pip install -r requirements.txt
```

### 2. 浏览器端（油猴脚本）
1. 安装 [Tampermonkey](https://www.tampermonkey.net/)
2. 安装油猴脚本: 将 `tampermonkey/xet_m3u8_export.user.js` 文件内容复制到Tampermonkey中，或直接安装脚本 [小鹅通 m3u8 导出 / 一键复制工具](https://greasyfork.org/zh-CN/scripts/560384-%E5%B0%8F%E9%B9%85%E9%80%9A-m3u8-%E5%AF%BC%E5%87%BA-%E4%B8%80%E9%94%AE%E5%A4%8D%E5%88%B6%E5%B7%A5%E5%85%B7)
3. 打开小鹅通课程页面并播放视频
4. 点击页面右下角「导出本课」按钮，保存生成的 `m3u8_list.json` 文件

> 每节课需要点击一次「导出本课」，Python 下载器可累积下载。

---

### 3. Python 下载器

#### 运行下载
```bash
python main.py
```

- 下载的视频将存放在 `videos/` 目录
- 日志文件在 `m3u8_download.log`
- 可在 `main.py` 配置：
  - `MAX_THREADS` 并发数
  - `DOWNLOAD_TIMEOUT` 下载超时时间
  - `OUTPUT_DIR` 输出目录

#### 配置建议
| 场景     | 并发数 | 说明 |
| -------- | ------ | ---- |
| 家用宽带 | 8-16   | 平衡下载速度和稳定性 |
| 高速网络 | 16-32  | 充分利用带宽 |
| 稳定下载 | 4-8    | 减少网络波动 |

### 4. M3U8信息获取

获取视频信息（时长、大小等）
```bash
python m3u8_info.py [m3u8_url]
```
或运行后输入URL

---

## 依赖说明

### Python 依赖
- `requests`: HTTP请求处理
- `pycryptodome`: AES-128解密支持
- `tqdm`: 进度条显示（可选）
- `urllib3`: HTTP库

### 系统依赖
- `ffmpeg`: 视频合并工具
- `ffprobe`: 视频信息获取（可选）

---

## 日志说明

- **INFO**: 用户可见操作信息
- **ERROR**: 下载失败或异常情况
- **DEBUG**: 详细调试信息（写入日志文件）

日志文件: `m3u8_download.log`

---

## 注意事项

- 本项目仅用于 **你本身有观看权限的课程**
- 请遵守相关网站的使用条款
- 建议合理设置并发数，避免对服务器造成过大压力
- 加密视频需要安装pycryptodome库
- 确保FFmpeg已正确安装并添加到PATH

---

## 常见问题

### 1. 提示找不到FFmpeg
确保FFmpeg已安装，并且其bin目录已添加到系统PATH环境变量

### 2. 加密视频下载失败
安装pycryptodome库: `pip install pycryptodome`

### 3. 下载速度慢
- 调整MAX_THREADS参数
- 检查网络连接
- 尝试在非高峰时段下载

### 4. 视频合并失败
- 确保FFmpeg版本较新
- 检查磁盘空间是否充足
- 检查分片文件是否完整

---

## 开源协议
MIT License