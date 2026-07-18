# Sprint 12 — Port LAB drop `missions/shb-132` (retrieval + Products/Ops certified + planner)

**Mở khoá 19/7**: user báo LAB hoàn thiện; explore inventory đầy đủ (agent explore, có version
hash 4 dấu từng role). Nguồn: `../shb-digital-experts/missions/shb-132` (CHỈ ĐỌC).
**User chốt**: (a)+(c) phần VỎ đã có (legal/main) → MERGE-COMPARE có cân nhắc, không đè mù ·
(b) prod chưa dùng thật → thay snapshot world 8bf6b4, giữ bảng users · (d) GO ngay, test kỹ,
prod làm bãi test thoải mái.

## Task list

| # | Task | Ai | Phụ thuộc |
|---|---|---|---|
| T12-0 | Policy vào sổ: D-65 (4 chốt user) + D-entry SPEC §14 vector-lật-hẹp + deviation legal-bơm-sau-certify | architect | — |
| T12-1 | Port `retrieval.py` theo RETRIEVAL-README §7: `wiki_*`+`notes_search` → common server, `legal_related_exposure` → legal pack; SCHEMAS_RETRIEVAL + ANNOTATIONS; adapter GIỮ WRITE-whitelist chỉ assessments (retrieval toàn READ) | BE | sau S15-BE |
| T12-2 | Migration 4 bảng PG (wiki_pages/wiki_links/interaction_notes/party_relations) + seed: copy `wiki/` 82 file vào repo, chuyển seed SQLite→PG (notes 2215 + party_relations + L901 + assumption `related_group_cap_pct`), snapshot D-62 cập nhật world 8bf6b4 (GIỮ users) + `uv add sentence-transformers pyvi` + env EMB_MODEL khớp seed | BE | T12-1 |
| T12-3 | Port Products/Ops CERTIFIED v1 trọn (SKILL + functions theo "PHONG BÌ BÀN GIAO" AGENT-*-DONE.md; janitor KHÔNG mang sang). **`ops_disburse` thay stub BÊN DƯỚI phanh gated — phanh không đổi** (30 money-test guard + test tích hợp mới) | BE | T12-2 |
| T12-4 | Merge-compare: legal SKILL (VỎ v3 + D-61 brand ⊕ đoạn SÁCH TRA CỨU LAB) · credit SKILL (⊕ đoạn notes_search) · planner v0 vs main_skill (cherry điều phối, KHÔNG đổi kiến trúc MAIN) — architect diff + draft, BE áp + verify | architect+BE | T12-1 |
| T12-5 | Tester wave: 5 tool retrieval live (trap `uu-dai-tet-68` phả hệ · trần nhóm 25% L901 · notes_search citation) + Products/Ops live + smoke lại legal/credit trên world mới + re-derive số demo script (SQL — bài học S11) → script v10. Rồi DEPLOY (image rebuild + HF cache volume + đo RAM VM báo số + env disable `local`) + §4b | tester → architect | T12-3/4 |

## Rủi ro đã nhận diện (tự xử, đã báo user)
ops_disburse×phanh (điểm review nặng nhất) · world mới đổi số → script v10 · RAM VM 5GB
(+~1GB model; notes_search degrade sạch nếu căng — đo thật sau deploy).

## Kickoff — 2026-07-19
Chạy song song S15 (BE nối S15→S12 tuần tự, FE gần như không dính S12). Baseline lúc kickoff:
514 test + S15 đang cộng. Gate đóng: theo T12-5 + gates §6a chuẩn.
