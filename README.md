# XET Downloader

小鹅通课程视频下载器（油猴 + Python 联动版）  

支持自动抓取课程标题、主 m3u8 导出、并发下载、限速控制和实时进度条。

---

## 功能特点

- **油猴脚本**
  - 自动识别课程页面主 m3u8 地址
  - 自动抓取课程标题
  - 一键导出 JSON (`m3u8_list.json`) 供 Python 下载器使用

- **Python 下载器**
  - 并发下载（可配置最大并发数）
  - 单任务限速（防止网络炸掉）
  - 实时进度条显示每节课下载进度
  - 规范化日志系统（控制台 + 文件）
  - 自动跳过已下载文件

---

## 项目结构

```
xet_downloader/
├─ tampermonkey/
│ └─ xet_m3u8_export.user.js # 油猴脚本
├─ downloader/
│ ├─ download_from_json.py # Python 主下载器
│ └─ utils.py # 日志和公共函数
├─ m3u8_list.json # 油猴导出的课程列表（示例）
├─ videos/ # 下载的视频存放目录
└─ logs/ # 日志目录
```

---

## 使用说明

### 1. 浏览器端（油猴脚本）

1. 安装 [Tampermonkey](https://www.tampermonkey.net/)  
2. 导入 `tampermonkey/xet_m3u8_export.user.js`  
3. 打开课程页面并播放视频  
4. 点击页面右下角「导出本课」按钮  
5. 保存生成的 `m3u8_list.json` 文件

> 每节课需要点击一次「导出本课」，Python 下载器可累积下载。

---

### 2. Python 下载器

#### 安装依赖

```bash
pip install tqdm
```

#### 运行下载

```
cd downloader
python download_from_json.py
```

- 下载的视频将存放在 `videos/` 目录

- 日志文件在 `logs/download.log`

- 可在 `download_from_json.py` 配置：

  - `MAX_WORKERS` 并发数

  - `RATE_LIMIT` 单任务限速（如 `"2M"`）

配置建议

| 场景     | 并发数 | 限速 |
| -------- | ------ | ---- |
| 家用宽带 | 2      | 2M   |
| 高速网络 | 3      | 4M   |
| 公司网络 | 1      | 1M   |

------

## 日志说明

- INFO：用户可见操作信息
- DEBUG：详细调试信息（全部写入 `logs/download.log`）
- ERROR：下载失败或异常情况

------

## 注意事项

- 本项目仅用于 **你本身有观看权限的课程**
- DRM 加密或无法访问的 m3u8 将跳过
- ffmpeg 需已安装并可执行
- 建议不要设置过高并发，以免被服务器封 IP

------

## 扩展功能

- 可增加 GUI 界面显示实时进度 + 日志
- 可增加断点续传
- 可实现课程目录自动抓取批量导出 JSON

------

## 开源协议

MIT License