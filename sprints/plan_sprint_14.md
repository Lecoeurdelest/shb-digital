# Sprint 14 — LOOP DOGFOOD (user chốt 19/7, full-auto §7)

**Theme:** Dùng app như USER THẬT trên prod `digital.tinhdev.com` → tìm lỗi/điểm-dở từ góc
người dùng → fix theo lô → re-verify → lặp tới sạch. KHÁC test kỹ thuật đã pass (8/8 luồng):
dogfood soi **UX + nghiệp vụ + cảm giác dùng** — cái happy-path test không bắt.

## Luật (từ kickoff team-lead — craft/00-paradigm §ĐÚNG VAI)
1. Tester ĐEO PERSONA, chấm bằng tâm thế USER ("phục vụ được chưa?") không phải builder
   ("chạy được chưa?"):
   - **Persona A = KHÁCH vay** — không biết thuật ngữ ngân hàng, sốt ruột, hỏi lan man, gõ sai.
   - **Persona B = CÁN BỘ duyệt** — cần quyết nhanh, cần thấy lý do rõ để ký.
2. Mỗi finding = verdict + LÝ DO + TẦNG (UX / nghiệp-vụ / kỹ-thuật) + repro + MỨC
   (demo-killer / khó-chịu / cosmetic). Verdict suông = vô giá trị.
3. Fix theo LÔ, phân tầng đúng. Author ≠ checker giữ nguyên.
4. **RÀO:** chỉ fix trong SPEC (§2 không thêm primitive). Lỗi cần tính-năng-mới → GHI đề xuất,
   không tự build. Prod phải sạch trước giờ G — destructive → reset + biên lai theo số.
5. KHÔNG chạy 2 persona song song đa tab (waiver cookie-share S11).

## Cấu trúc lô
| Lô | Nội dung | Ai |
|---|---|---|
| 1 | Persona A — khách vay, trọn hành trình cửa khách trên prod | tester |
| 2 | Persona B — cán bộ duyệt, Tower 6 tab + duyệt phiếu + trace | tester |
| 3+ | Fix wave theo findings lô 1+2 → re-verify → lô bổ sung nếu còn | BE/FE + tester |

Findings ghi vào `docs/dogfood-findings.md` (single source). Báo team-lead sau MỖI lô.

## Baseline
497 test (367 BE + 130 FE) · scenarios doc 8/8 · prod: 3 loans active (L001/L007/L108),
1 approval auto, CI xanh, HEAD d474142.

## Gate đóng sprint
- Mọi finding mức **demo-killer** + **khó-chịu**: fixed + re-verified, hoặc waiver §6b có duyệt.
- **Cosmetic**: triage — fix rẻ thì fix, còn lại ghi trạng thái `deferred` trong findings doc.
- Đề xuất ngoài SPEC: ghi mục riêng trong findings doc + báo lead, KHÔNG build.
- Test ≥ 497, CI xanh, scenarios doc vẫn 8/8 (regression).
- Prod reset về trạng thái demo-sạch, biên lai THEO SỐ (bài học S13).

## Kickoff — 2026-07-19
Backlog đến qua spawn prompt team-lead (đúng luật kickoff đầu-loại-việc). Không có plan nháp
trước — file này tạo mới tại kickoff, drift = 0. SPEC/CLAUDE.md không đổi từ S13. Task list
cuối = bảng lô ở trên.
