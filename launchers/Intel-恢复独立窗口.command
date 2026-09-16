#!/bin/bash
set -e
APP="/Applications/ChatFLOW.app"
if [ ! -x "$APP/Contents/MacOS/ChatFLOW" ]; then
  echo "请先把 ChatFLOW 放进应用程序，再运行本文件。"
  read -r -p "按回车结束"
  exit 1
fi
DATA_DIR="$HOME/Library/Application Support/ChatFLOW"
FLAG="$DATA_DIR/force_browser"
if [ -f "$FLAG" ]; then
  mv "$FLAG" "$FLAG.disabled-$(date +%Y%m%d-%H%M%S)-$$"
  echo "已备份并解除旧版强制浏览器设置，产品资料和模型不会改动。"
fi
echo "正在打开独立窗口。以后直接打开应用程序里的 ChatFLOW 即可。"
open -n "$APP"
