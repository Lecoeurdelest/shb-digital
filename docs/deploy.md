# Deploy — BANK Digital lên dev-vm (S10)

> Đích (khảo sát 18/7): GCP `dev-vm` us-east1-b (Ubuntu 24.04 · 5GB RAM · 23GB disk · Docker 29 +
> Compose v2 sẵn). Domain `digital.tinhdev.com` → Cloudflare → cloudflared systemd → FE-port.
> Container port riêng (FE:3011 · API:8011) + network riêng `shb132` — KHÔNG đụng container khác.

## 0. Nguyên tắc
- **External/one-way = verify TỪNG BƯỚC** (sửa cloudflared là điểm không-đảo-được — làm cuối, có rollback).
- Container dùng `SHB_PROVIDER=zai` (không có CLI login máy trong container → provider keyed).
- Volumes SỐNG CÒN: `claude_home` (~/.claude SDK state) + `conv_data` (transcript resume). Xoá =
  mất resume + phải re-auth. `shb132_pg_data` = DB nghiệp vụ.
- Postgres là transactional core. Mọi datastore phụ được khai báo theo capability trong
  `configs/datastores.json`; không đặt DSN/credential trực tiếp trong file JSON.

## 1. Chuẩn bị .env trên vm (KHÔNG commit — gitignored)
```
cp .env.example .env
# điền: zai=<key> · SHB_PROVIDER=zai · SMTP_USER/SMTP_APP_PASSWORD/NOTIFY_FROM_NAME (mail thật)
# APP_URL=https://digital.tinhdev.com   (link CTA trong mail — prod domain)
```

## 2. Clone + build + up (port riêng, nội bộ)
```
git clone <repo> && cd shb-digital
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```
Backend entrypoint tự chạy `alembic upgrade head` + đăng ký prompt version + seed (idempotent)
trước khi serve. Prompt sync mặc định chỉ tạo version mới hoặc binding còn thiếu, không tự thay
active version mà operator đã chọn.

### Nâng DB đang có dữ liệu

Trước mỗi migration production, dừng writer hoặc đưa backend về maintenance, tạo custom dump và
kiểm archive. Không tự xóa orphan để migration đi qua:

```bash
mkdir -p /secure/backups
docker compose -f docker-compose.prod.yml exec -T db sh -c \
  'pg_dump -U shb -d shb -Fc --no-owner --no-privileges -f /tmp/shb-pre-migrate.dump && pg_restore --list /tmp/shb-pre-migrate.dump >/dev/null'
docker compose -f docker-compose.prod.yml cp \
  db:/tmp/shb-pre-migrate.dump /secure/backups/shb-pre-migrate.dump
```

Sau migration, kiểm head, dữ liệu legacy chưa map và prompt binding:

```bash
docker compose -f docker-compose.prod.yml exec backend uv run alembic current
docker compose -f docker-compose.prod.yml exec db psql -U shb -d shb \
  -c "SELECT issue_type,entity_table,count(*) FROM operational_data_issues GROUP BY 1,2 ORDER BY 1,2"
docker compose -f docker-compose.prod.yml exec backend \
  uv run python -m app.prompting.sync --activate --environment production --actor release
```

`--activate` là thao tác release có chủ đích. Bỏ cờ này khi chỉ muốn đăng ký version để review.

### Connection budget

Mỗi backend process có pool riêng; đặt giới hạn theo ngân sách thật của Postgres:

```dotenv
SHB_DB_POOL_MIN=1
SHB_DB_POOL_MAX=10
SHB_DB_CONNECT_TIMEOUT_SECONDS=5
SHB_DB_POOL_ACQUIRE_TIMEOUT_SECONDS=5
```

Giữ `replicas * SHB_DB_POOL_MAX + migration/jobs + reserve < max_connections`. Connect timeout
chặn DNS/DB lỗi giữ worker vô hạn; acquire timeout cho tải chờ ngắn khi pool đầy rồi fail rõ ràng.
Không tăng `SHB_DB_POOL_MAX` để che slow query/idle transaction; xem lock, query latency và pool
wait trước, rồi mới cân nhắc PgBouncer hoặc read replica.

## 2b. Profile scale cho retrieval lớn (D-78)

Chỉ bật profile này khi `interaction_notes` hoặc corpus semantic đã vượt ngưỡng quét PostgreSQL
trong SLO. PostgreSQL vẫn là nguồn chuẩn; Redis mất dữ liệu chỉ mất cache, Qdrant mất dữ liệu chỉ cần
backfill lại. Hai endpoint phải là nội bộ cùng bank DC, không expose port ra Internet:

```dotenv
# Trong .env trên VM (không commit)
REDIS_URL=redis://redis:6379/0
QDRANT_URL=http://qdrant:6333
```

Khởi tạo hoặc redeploy profile và backfill theo batch bounded:

```bash
docker compose -f docker-compose.prod.yml --env-file .env --profile scale up -d --build
docker compose -f docker-compose.prod.yml exec backend uv run python -m app.retrieval.sync_vectors --batch-size 500
```

Lệnh backfill upsert idempotent theo `note_id`. Với luồng chỉ append, lưu watermark đã xác nhận của
job rồi chạy tiếp `--after-note-id <watermark>`; không chạy `--after-note-id` khi cần refresh embedding
cũ. Kiểm tra collection và cache bằng log/job metric, không log text note hay vector. Cần snapshot
volume `qdrant_data` trước khi nâng major Qdrant; không backup Redis vì đây là cache có TTL.

## 3. Verify NỘI BỘ (trước khi đụng cloudflared)
```
docker compose -f docker-compose.prod.yml ps          # 3 service healthy
curl -fsS http://localhost:8011/api/health            # {"ok":true}
curl -fsS http://localhost:3011/ | head -c 200        # FE index.html (SPA)
# FIX D: providers ≥2 (KHÔNG chỉ claude-cli chết) — bắt lỗi thiếu COPY configs/ trong image.
# /api/models cần auth (prod DEV_SKIP_AUTH off) → login lấy cookie trước.
CJ=$(mktemp); curl -fsS -c "$CJ" -X POST http://localhost:8011/api/auth/login \
  -H 'Content-Type: application/json' -d '{"username":"admin","password":"<ADMIN — mật khẩu đã gửi BTC, không đăng repo>"}' >/dev/null
curl -fsS -b "$CJ" http://localhost:8011/api/models | python3 -c "import sys,json; d=json.load(sys.stdin); \
  ps=d.get('providers',d) if isinstance(d,dict) else d; names=[p['name'] for p in ps]; \
  print('providers:', names); assert len(names)>=2, 'CHỈ 1 provider — thiếu configs/ trong image?'"; rm -f "$CJ"
# smoke 1 vòng: đăng ký khách → form → thẩm định (qua UI localhost:3011)
```
Lỗi → `docker compose -f docker-compose.prod.yml logs backend` (migration/seed/CLI).

## 4. Cloudflared (EXTERNAL — one-way, làm CUỐI + verify từng bước)
```
sudo nano /etc/cloudflared/config.yml
# thêm ingress:
#   - hostname: digital.tinhdev.com
#     service: http://localhost:3011
#   - service: http_status:404        (giữ dòng catch-all cuối)
sudo systemctl restart cloudflared
# verify NGOÀI: curl -I https://digital.tinhdev.com  → 200 + FE load
```

## 4b. Verify cache SAU MỖI redeploy FE (S14 — chống bundle-stale trước giám khảo)

Cơ chế bền (đã vào code, KHÔNG phải fix tay 1 lần): Vite content-hash tên bundle
(`assets/index-<hash>.js` — đổi mỗi build) + `frontend/nginx.conf` set `index.html →
Cache-Control: no-cache` và `/assets/ → immutable 1 năm`. Cloudflare KHÔNG cache HTML mặc định
và pass-through header origin. Sau mỗi redeploy FE, verify 10 giây:
```
curl -sI https://digital.tinhdev.com/ | grep -i cache-control        # PHẢI: no-cache
curl -s https://digital.tinhdev.com/ | grep -o 'assets/index-[^"]*'  # hash PHẢI ĐỔI so với build trước
```
Lưu ý 1 lần: browser đã mở app TRƯỚC fix này (commit 67350cd) có thể còn giữ index.html cũ
→ hard-refresh 1 phát là hết vĩnh viễn (từ đó no-cache tự lo). Checklist giờ G: hard-refresh
máy demo đầu phiên.

## 5. Rollback
- App lỗi: `docker compose -f docker-compose.prod.yml down` → sửa → up lại (data volume GIỮ).
- Cloudflared lỗi: khôi phục `config.yml` cũ (backup trước khi sửa: `cp config.yml config.yml.bak`)
  → `systemctl restart cloudflared`. Domain về trạng thái trước.
- DB migration lỗi trước khi nhận write mới: chạy đúng revision downgrade đã diễn tập. Nếu đã nhận
  write theo schema mới, không downgrade mù; dừng writer, đánh giá forward-fix hoặc restore custom
  dump vào DB tách rồi cutover. Mỗi migration Alembic vẫn phải reversible để diễn tập đường lùi.

## 6b. SEED SOURCE = SNAPSHOT trong repo (D-62 — đã chốt)
LAB seed db sống NGOÀI repo (D-08). Deploy = **snapshot `deploy/seed/shb-132.db`** COPY vào image.
`seed_from_lab` fallback chain: **LAB sibling path (dev) → snapshot (deploy)** — 0 config, repo
tự chứa ("đặt đâu chạy đó" §1). Refresh snapshot + md5: xem `deploy/seed/README.md`.
> S12 sau này cùng pattern: wiki/ + retrieval seed snapshot vào `deploy/seed/`.

## 6c. SEED-NẾU-RỖNG (entrypoint — D-62, đã chốt)
Entrypoint: `alembic upgrade head` (LUÔN, idempotent) → `seed_if_empty` (check `count(assumptions)`
>0 → SKIP). Restart container GIỮA ca KHÔNG wipe khách C9xx đã đăng ký (gate S10 "session bền").
**RESET CHỦ ĐỘNG** (khi muốn demo lại từ đầu):
```
docker compose -f docker-compose.prod.yml exec backend uv run python -m app.db.reset_demo
```

## 6. Lưu ý container
- **1 worker no-reload** (D-38) — không hot-reload trong container; đổi code = rebuild image.
- FE build-time gọi API path tương đối `/api` → nginx proxy sang `backend:8000` (network shb132).
  SSE (`/api/.../sse`) nginx đã tắt buffer + timeout 3600s (stream sống dài).
- Claude CLI cài trong image backend (`npm i -g @anthropic-ai/claude-code`) — SDK runtime cần dù
  provider=zai. Build lỗi ở bước này → xem log npm (mạng/registry). Note (ref DevCrew): ref dùng
  trick symlink `claude` sau COPY node_modules (COPY deref symlink → hỏng require path). Mình cài
  trực tiếp `npm i -g` (không multi-stage COPY node_modules) → `claude --version` pass, KHÔNG cần trick.

## 6d. Volume ownership durable (port DevCrew ref) + sandbox deps (bật theo bằng chứng)
- **UID/GID build-arg (đã áp):** Dockerfile `ARG UID/GID` + `mkdir -p data/conversations ~/.claude
  && chown TRƯỚC USER`. Named volume RỖNG lần đầu copy ownership từ image dir → appuser sở hữu, HẾT
  "Permission denied mkdir conversations" fresh deploy. Compose args `DOCKER_UID/GID` (default 1000).
  Host UID khác 1000 → set `DOCKER_UID=$(id -u) DOCKER_GID=$(id -g)` trước `compose build`.
- **SDK sandbox deps (bubblewrap/socat/cap_add) — CHƯA cài, bật NẾU CẦN:** ref DevCrew ghi bwrap/
  socat "required by Claude Agent SDK sandbox". Mình dùng `setting_sources=[]` → sandbox thường KHÔNG
  engage → không cài để khỏi phình image. **NẾU MAIN turn trên VM fail lỗi sandbox/bwrap/seccomp** →
  thêm vào backend/Dockerfile runtime deps: `bubblewrap socat` + compose backend:
  `cap_add: [SYS_ADMIN]` + `security_opt: [seccomp:unconfined, apparmor:unconfined]` (ref-proven).

## 7. Lark / Webhook Doorbell

Webhook ngoài chỉ là **chuông cửa** cho bàn phê duyệt: báo `pending|approved|rejected` rồi đưa cán
bộ về đúng phiếu trong Control Tower. Không có đường duyệt từ chat; người duyệt phải mở link, đăng
nhập bằng tài khoản ngân hàng và quyết định trong Tower để auth + audit ở lại bank DC (D-71).

### Tạo Lark custom incoming bot

1. Trong nhóm Lark của bàn phê duyệt, thêm **Custom Bot / Incoming Webhook** và chỉ cấp quyền cho
   đúng nhóm vận hành. Copy webhook URL một lần; URL có token chính là secret.
2. Trên VM, ghi URL thẳng vào `.env` đã gitignore; không dán vào issue, chat, ảnh chụp, command
   history hay log. Giới hạn quyền file (`chmod 600 .env`). Nếu URL lộ, xoay/recreate bot ngay.
3. Đặt `APP_URL` thành URL Control Tower mà cán bộ ngân hàng truy cập được, rồi cấu hình:

```dotenv
APP_URL=https://digital.tinhdev.com
SHB_NOTIFY_WEBHOOK_URL=https://open.larksuite.com/open-apis/bot/v2/hook/<secret>
SHB_NOTIFY_CHANNEL=lark
SHB_NOTIFY_INCLUDE_AMOUNT=0
```

Với receiver nội bộ dùng JSON phẳng, đổi `SHB_NOTIFY_CHANNEL=generic`. Thiếu/rỗng URL là tắt;
channel thiếu mặc định `generic`; amount thiếu mặc định `0`. **CẤM đặt
`SHB_NOTIFY_INCLUDE_AMOUNT=1` nếu webhook nằm ngoài bank DC.** Chỉ cân nhắc amount cho receiver
on-prem/private đã được ngân hàng phê duyệt phạm vi xử lý dữ liệu.

Áp cấu hình mà không rebuild image:

```bash
docker compose -f docker-compose.prod.yml --env-file .env config >/dev/null
docker compose -f docker-compose.prod.yml --env-file .env up -d --no-deps --force-recreate backend
```

### Biên dữ liệu và payload

Shape duy nhất nằm tại [`CONTRACT §8 — Outbound webhook doorbell`](CONTRACT.md#8-outbound-webhook-doorbell-s19--d-71);
runbook không định nghĩa một biến thể thứ hai:

| Channel | Shape chính xác |
|---|---|
| `generic` | §8a: JSON phẳng chỉ có `action`, `conv_id` đúng 8 ký tự đầu, `status`, `deep_link`; chỉ thêm integer `amount` khi flag bằng `1` |
| `lark` | §8b: interactive card cố định có title, một dòng nội dung từ đúng whitelist generic và nút **Open Control Tower** |

Tuyệt đối không gửi tên khách, owner/loan/application ID, CIC, hồ sơ/tài liệu, lý do, người duyệt,
biên nhận, headers hay approval row. Không ghi full webhook URL/token hoặc request/response body vào
log. Deep-link chỉ là định danh cửa vào; dữ liệu chuẩn luôn được đọc lại từ bank DC sau auth.

### Transport, rate limit và failure mode

- Mỗi `POST application/json` có timeout **5 giây**. Timeout/network error, HTTP `429` hoặc `5xx`
  thử tối đa **3 attempts tổng**: lần đầu ngay, rồi sau `1s`, rồi sau thêm `3s`. `4xx` khác không retry.
- Lark có thể rate-limit incoming bot; `429` đi đúng retry trên, hết lượt thì warning + drop. Không
  tăng vòng retry hoặc biến webhook thành một dependency của luồng phê duyệt.
- Delivery là best-effort sau commit + SSE: lỗi webhook không đổi HTTP response/main flow. Retry có
  thể tạo chuông trùng; trạng thái thật vẫn ở Tower. **Không thêm outbox, queue bền hay replay** chỉ
  để chống trùng cho kênh chuông cửa.
- Không đặt nút/action approve hoặc nhận lệnh quyết định từ Lark/generic webhook. Chat chỉ mở Tower.

### Tắt và rollback

Để tắt ngay, đặt `SHB_NOTIFY_WEBHOOK_URL=` (hoặc xoá key) trong `.env` rồi recreate riêng backend:

```bash
docker compose -f docker-compose.prod.yml --env-file .env up -d --no-deps --force-recreate backend
```

Không có migration hay dữ liệu webhook cần rollback. In-app queue/SSE và mail hiện hữu tiếp tục chạy.
Sau khi tắt, tạo một phiếu thử và xác nhận receiver không nhận request; chỉ kiểm log theo channel /
status / conv-id rút gọn, không in URL bí mật.

## 8. Profile headless trong bank DC (S21 · D-74)

`docker-compose.prod.yml` ở repo là **demo profile**: còn DB credential demo và provider `wrap`
ngoài DC. Không được đổi tên nó thành production bank hoặc dùng ảnh `/api/health` để kết luận data
residency. Bản triển khai ngân hàng phải đặt ít nhất:

```dotenv
SHB_RUNTIME_MODE=bank_dc
SHB_CORS_ORIGINS=https://saha.bank.vn,https://los.bank.vn
SHB_BANK_PROVIDER_HOSTS=llm-gateway.bank.dc,ollama.bank.dc
JWT_SECRET=<random-secret-it-nhat-32-ky-tu>
DATABASE_URL=postgresql://<user>:<strong-password>@<postgres.bank.dc>/<db>
DEV_SKIP_AUTH=0
COOKIE_SECURE=1
SEED_USER_PASSWORD=<non-demo-it-nhat-12-ky-tu>
SEED_ADMIN_PASSWORD=<non-demo-it-nhat-12-ky-tu>
SEED_C001_PASSWORD=<non-demo-it-nhat-12-ky-tu>
SEED_B001_PASSWORD=<non-demo-it-nhat-12-ky-tu>
SEED_C019_PASSWORD=<non-demo-it-nhat-12-ky-tu>
```

Mọi provider còn enabled phải là API HTTP(S), đủ credential và có hostname exact trong
`SHB_BANK_PROVIDER_HOSTS`; provider subscription/CLI hoặc host ngoài danh sách làm process từ chối
startup. Check được lặp lại lúc resolve từng conversation để config reload nóng hay ca cũ không mở
lại egress. Đây là guard ứng dụng, **không thay thế** firewall/egress policy của hạ tầng ngân hàng.

Sau migrate và trước khi nhận traffic:

```bash
curl -fsS http://127.0.0.1:8000/api/ready
```

Response hợp lệ phải có `ready:true`, `profile:"bank_dc"` và bốn cờ boolean `database`,
`migrations`, `provider`, `mcp_mounts` đều `true` như CONTRACT §9a. Bất kỳ dependency nào lỗi trả
`503` envelope 4-field, còn chi tiết chỉ nằm trong server log. Readiness xác minh cấu hình provider,
không gọi thử ra model; đội hạ tầng vẫn phải chạy probe egress và kiểm SSO/ownership trước go-live.
