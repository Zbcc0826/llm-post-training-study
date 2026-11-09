#!/bin/bash
# 启动本地静态服务并打开合集学习页，便于页内 PDF.js 分栏阅读论文。
cd "$(dirname "$0")/.."
PORT=8766
(sleep 0.6 && open "http://127.0.0.1:${PORT}/release/%E5%9F%BA%E6%A8%A1%E7%88%B7%E5%A4%A7%E5%AD%A6%E4%B9%A0.html") &
echo "已在浏览器打开: http://127.0.0.1:${PORT}/release/基模爷大学习.html"
exec python3 -m http.server "${PORT}" --bind 127.0.0.1
