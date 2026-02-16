#!/bin/bash
# GPU-Insight 自动循环脚本
# 每 4 小时执行一次分析循环
#
# 使用方式：
#   chmod +x auto-loop.sh
#   ./auto-loop.sh              # 前台运行
#   nohup ./auto-loop.sh &      # 后台运行
#
# 或配置 cron：
#   0 */4 * * * cd /path/to/GPU-Insight && python main.py >> logs/cron.log 2>&1

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

INTERVAL=14400  # 4 小时 = 14400 秒
LOG_DIR="logs"

mkdir -p "$LOG_DIR"

echo "🚀 GPU-Insight 自动循环启动"
echo "   间隔：${INTERVAL}s (4h)"
echo "   日志：${LOG_DIR}/"
echo ""

cycle=1
while true; do
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    log_file="${LOG_DIR}/cycle_$(date '+%Y%m%d_%H%M').log"

    echo "[$timestamp] 第 ${cycle} 轮开始..." | tee -a "$log_file"

    # 执行主程序
    python main.py 2>&1 | tee -a "$log_file"

    exit_code=${PIPESTATUS[0]}
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    if [ $exit_code -eq 0 ]; then
        echo "[$timestamp] 第 ${cycle} 轮完成 ✅" | tee -a "$log_file"
    else
        echo "[$timestamp] 第 ${cycle} 轮异常 (exit=$exit_code) ⚠️" | tee -a "$log_file"
    fi

    echo ""
    cycle=$((cycle + 1))

    echo "⏳ 等待 ${INTERVAL}s 后开始下一轮..."
    sleep $INTERVAL
done
