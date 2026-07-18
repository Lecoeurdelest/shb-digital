# Deploy — BANK Digital lên dev-vm (S10)

> Đích (khảo sát 18/7): GCP `dev-vm` us-east1-b (Ubuntu 24.04 · 5GB RAM · 23GB disk · Docker 29 +
> Compose v2 sẵn). Domain `digital.tinhdev.com` → Cloudflare → cloudflared systemd → FE-port.
> Container port riêng (FE:3011 · API:8011) + network riêng `shb132` — KHÔNG đụng container khác.

## 0. Nguyên tắc
- **External/one-way = verify TỪNG BƯỚC** (sửa cloudflared là điểm không-đảo-được — làm cuối, có rollback).
- Container dùng `SHB_PROVIDER=zai` (không có CLI login máy trong container → provider keyed).
- Volumes SỐNG CÒN: `claude_home` (~/.claude SDK state) + `conv_data` (transcript resume). Xoá =
  mất resume + phải re-auth. `shb132_pg_data` = DB nghiệp vụ.

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
Backend entrypoint tự chạy `alembic upgrade head` + seed (idempotent) trước khi serve.

## 3. Verify NỘI BỘ (trước khi đụng cloudflared)
```
docker compose -f docker-compose.prod.yml ps          # 3 service healthy
curl -fsS http://localhost:8011/api/health            # {"ok":true}
curl -fsS http://localhost:3011/ | head -c 200        # FE index.html (SPA)
# FIX D: providers ≥2 (KHÔNG chỉ claude-cli chết) — bắt lỗi thiếu COPY configs/ trong image.
# /api/models cần auth (prod DEV_SKIP_AUTH off) → login lấy cookie trước.
CJ=$(mktemp); curl -fsS -c "$CJ" -X POST http://localhost:8011/api/auth/login \
  -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin"}' >/dev/null
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

## 5. Rollback
- App lỗi: `docker compose -f docker-compose.prod.yml down` → sửa → up lại (data volume GIỮ).
- Cloudflared lỗi: khôi phục `config.yml` cũ (backup trước khi sửa: `cp config.yml config.yml.bak`)
  → `systemctl restart cloudflared`. Domain về trạng thái trước.
- DB migration lỗi: `alembic downgrade -1` (mỗi migration reversible — nguyên tắc BE).

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
  provider=zai. Build lỗi ở bước này → xem log npm (mạng/registry).
