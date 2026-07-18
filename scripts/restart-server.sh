#!/usr/bin/env bash
# restart-server.sh — restart :8000 AN TOÀN (chống restart-giữa-ca giết sub in-flight, 18/7).
# Giao thức: commit runtime → restart → re-curl. NHƯNG kiểm CA-LIVE trước kill (bài học D-54 giết
# task Legal tester rehearse). Có ca đang chạy → cảnh báo + chờ confirm.
#   Dùng:  scripts/restart-server.sh          (hỏi confirm nếu có ca live)
#          scripts/restart-server.sh -y        (bỏ confirm — CHỈ khi chắc không ai dùng)
set -euo pipefail

PORT=8000
DB_URL="${DATABASE_URL:-postgresql://shb:shb@localhost:5432/shb}"
FORCE="${1:-}"

# 1. KIỂM CA-LIVE trước khi kill (task status running/queued = có sub đang chạy → restart sẽ giết).
running=$(psql "$DB_URL" -tA -c \
  "SELECT count(*) FROM tasks WHERE status IN ('running','queued')" 2>/dev/null || echo "?")
if [ "$running" != "0" ] && [ "$running" != "?" ]; then
  echo "⚠️  CÓ CA ĐANG CHẠY ($running task running/queued) — restart SẼ GIẾT (orphan-cleanup)."
  psql "$DB_URL" -tA -c \
    "SELECT '   - '||role||' ['||status||'] conv='||left(conv_id,8) FROM tasks \
     WHERE status IN ('running','queued') ORDER BY queued_at" 2>/dev/null || true
  if [ "$FORCE" != "-y" ]; then
    read -r -p "Tiếp tục restart (giết các task trên)? [y/N] " ans
    [ "$ans" = "y" ] || [ "$ans" = "Y" ] || { echo "HỦY restart — chờ ca xong."; exit 1; }
  else
    echo "   (-y: bỏ qua confirm — restart luôn)"
  fi
elif [ "$running" = "?" ]; then
  echo "⚠️  KHÔNG query được DB (psql/conn) — KHÔNG biết có ca live. Kiểm tay trước khi -y."
  [ "$FORCE" = "-y" ] || { echo "HỦY — chạy -y nếu chắc không ai dùng."; exit 1; }
fi

# 2. KILL server cũ (fuser theo port — gọn, không nhầm process khác).
echo "→ kill uvicorn :$PORT ..."
fuser -k "$PORT/tcp" 2>/dev/null || true
sleep 2

# 3. START mới (no-reload D-38 tránh --reload+SSE treo; env giữ). Detached.
cd "$(dirname "$0")/../backend"
DATABASE_URL="$DB_URL" DEV_SKIP_AUTH="${DEV_SKIP_AUTH:-1}" \
  nohup uv run uvicorn app.main:app --host 0.0.0.0 --port "$PORT" \
  --timeout-graceful-shutdown 3 > "/tmp/srv${PORT}.log" 2>&1 &
sleep 6

# 4. HEALTH-CHECK + in pid/time (re-curl từ đây — chống crossing curl-server-cũ).
if curl -sf "http://localhost:$PORT/api/health" >/dev/null 2>&1; then
  pid=$(fuser "$PORT/tcp" 2>/dev/null | tr -d ' ' || echo "?")
  echo "✅ server restarted pid=$pid lúc $(date '+%H:%M:%S') — health OK. RE-CURL từ đây."
else
  echo "❌ health-check FAIL sau restart — xem /tmp/srv${PORT}.log"
  exit 1
fi
