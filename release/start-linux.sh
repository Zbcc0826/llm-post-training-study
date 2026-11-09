#!/bin/sh
# 启动本地静态服务，用于页内 PDF.js 分栏阅读论文。
cd "$(dirname "$0")/.."
PORT=8766
echo "请在浏览器打开: http://127.0.0.1:${PORT}/release/基模爷大学习.html"
exec python3 -m http.server "${PORT}" --bind 127.0.0.1
