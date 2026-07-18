#!/usr/bin/env bash
# restart-server.sh — restart :8000 AN TOÀN (chống restart-giữa-ca giết sub in-flight, 18/7).
# Giao thức: commit runtime → restart → re-curl. NHƯNG kiểm CA-LIVE trước kill (bài học D-54 giết
# task Legal tester rehearse). Có ca đang chạy → cảnh báo + chờ confirm.
#   Dùng:  scripts/restart-server.sh          (hỏi confirm nếu có ca live)
#          scripts/restart-server.sh -y        (bỏ confirm — CHỈ khi chắc không ai dùng)
# FIX-B (T9-4): (i) kill guard `|| true` — pgrep no-match không làm set -e giết script trước start;
#              (ii) source .env trước start → SMTP/provider env vào process (mail thật chạy).
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

# 2. KILL server cũ — pkill pattern (parent uv-wrapper + child) + fuser -k port (chắc chắn giết
# process GIỮ PORT dù pattern lệch). MỌI lệnh kill/pgrep GUARD `|| true` (FIX-B bug-i: pgrep no-match
# =exit1 dưới set -e/pipefail → script chết TRƯỚC start, không restart lại). Đếm dùng `|| echo 0`.
echo "→ kill uvicorn :$PORT (pkill parent+child + fuser -k port) ..."
pkill -f "uvicorn app.main.*$PORT" 2>/dev/null || true
fuser -k "$PORT/tcp" 2>/dev/null || true   # giết port-holder (uv-wrapper respawn-parent) — chắc ăn
sleep 2
# ASSERT SẠCH: 0 process uvicorn còn trước khi start (chống 2-instance chồng). `pgrep||true` chặn
# no-match-exit1 (bug-i); `wc -l` LUÔN exit 0 + xuất 1 số (KHÔNG `|| echo 0` — nó append số thứ 2).
leftover=$( { pgrep -f "uvicorn app.main.*$PORT" 2>/dev/null || true; } | wc -l | tr -d ' ')
if [ "${leftover:-0}" != "0" ]; then
  echo "⚠️  còn $leftover process uvicorn sau pkill — kill -9 + fuser lần cuối..."
  pkill -9 -f "uvicorn app.main.*$PORT" 2>/dev/null || true
  fuser -k -9 "$PORT/tcp" 2>/dev/null || true
  sleep 1
fi

# 3. START mới (no-reload D-38 tránh --reload+SSE treo). Detached.
# FIX-B bug-ii: SOURCE .env TRƯỚC start → SMTP_USER/APP_PASSWORD/NOTIFY_FROM_NAME + zai key... vào
# env process (email.py/providers.py đọc os.environ). Không source = mail no-op + provider thiếu key.
REPO_ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [ -f "$REPO_ROOT_DIR/.env" ]; then
  # Parse line-by-line (KHÔNG `. .env` — value có SPACE như 'NOTIFY_FROM_NAME=BANK Digital' làm
  # source chạy 'Digital' như lệnh). Bỏ dòng trống/comment; export nguyên value (kể cả space).
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in ''|'#'*) continue ;; esac
    [ "${line#*=}" = "$line" ] && continue  # không có '=' → bỏ
    export "${line%%=*}=${line#*=}"
  done < "$REPO_ROOT_DIR/.env"
  echo "→ đã nạp .env (SMTP/provider env vào process)"
else
  echo "⚠️  KHÔNG có .env — mail no-op + provider keyed thiếu key (dev claude-cli vẫn chạy)"
fi
cd "$REPO_ROOT_DIR/backend"
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
