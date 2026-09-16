#!/bin/bash
cd "$(dirname "$0")" || exit 1
APP="/Applications/ChatFLOW.app"
if [ ! -x "$APP/Contents/MacOS/ChatFLOW" ]; then
  echo "请先把 ChatFLOW 拖进应用程序，再运行本启动器。"
  read -r -p "按回车退出"
  exit 1
fi
# The application selects its own port and opens the correct browser URL.
# Do not terminate another running instance or remove macOS security attributes.
LOG_DIR="$HOME/Library/Application Support/ChatFLOW"
mkdir -p "$LOG_DIR"
nohup env CF_BROWSER=1 "$APP/Contents/MacOS/ChatFLOW" >> "$LOG_DIR/browser-launch.log" 2>&1 < /dev/null &
echo "ChatFLOW 正在打开浏览器。可以关闭这个终端窗口，请使用新打开的软件页面。"
