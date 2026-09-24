#!/bin/bash
set -e
APP="/Applications/ChatFLOW.app"
if [ ! -x "$APP/Contents/MacOS/ChatFLOW" ]; then
  echo "请先把 ChatFLOW 拖进‘应用程序’。"
  read -r -p "按回车结束"
  exit 1
fi
DATA_DIR="$HOME/Library/Application Support/ChatFLOW"
FLAG="$DATA_DIR/force_browser"
if [ -f "$FLAG" ]; then
  mv "$FLAG" "$FLAG.disabled-$(date +%Y%m%d-%H%M%S)-$$"
  echo "已解除旧版强制浏览器设置，资料和模型不会改动。"
fi
echo "正在打开独立窗口。以后直接打开 ChatFLOW 主程序即可。"
open -n "$APP"
