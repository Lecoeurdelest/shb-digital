# Sprint {{X}} — Plan

<!-- LUẬT SỐNG CÒN (đọc trước khi sửa file):
     Plan này là 1 SOURCE OF TRUTH duy nhất cho sprint. Kickoff KHÔNG viết file mới —
     architect EDIT IN-PLACE file này (drift <10% = note inline; 10–30% = edit + History appendix; >30% = rewrite), rồi
     APPEND section `## Kickoff — YYYY-MM-DD` ở CUỐI. Never dispatch từ plan stale.
     Task = spec: mỗi task phải có verification MÁY-KIỂM-ĐƯỢC (chạy được/đo được), nếu
     không agent tự break sai + không biết lúc nào xong.
     Task-id do architect đặt, MỘT quy ước nhất quán cả project (vd T<sprint>-<n>) —
     dùng đúng id đó xuyên suốt dispatch / plan / end_sprint. -->

**Objective:** {{1-2 câu — sprint này đạt cái gì; nối với bước nào trong ARCHITECTURE §8}}
**Theme:** {{1 cụm — mọi task chung theme, độc lập sprint khác}}
**Baseline test count:** {{<count> — end_sprint phải ≥ số này}}

## Tasks (3-6, làm theo dependency)

### {{<task-id>}} — {{tên ngắn}}
- **Assignee:** {{be / fe / tester / architect}}
- **Mô tả:** {{1-2 câu — làm gì, chạm file/module nào}}
- **Dependency:** {{<task-id khác> / none}}
- **Verification:** {{tiêu chí pass CỤ THỂ, đo được — vd: "curl GET /<resource> trả 200 + N field non-null" / "unit test <path> pass, assert observable behavior"}}

### {{<task-id>}} — {{...}}
- **Assignee:** {{...}}
- **Mô tả:** {{...}}
- **Dependency:** {{...}}
- **Verification:** {{...}}

<!-- ...lặp tới 3-6 task. Gate mỗi task phải chạy được, không "làm cho tốt". -->

---

<!-- ↓ Section dưới do ARCHITECT append lúc kickoff. Trước kickoff để trống khung này. -->

## Kickoff — {{YYYY-MM-DD}}

**Drift since plan:** {{cái gì đã đổi so với lúc viết plan — spec mới, code thực tế khác giả định, task trước để lại findings. "none" nếu khớp.}}

**Plan revisions:** {{đã sửa gì IN-PLACE ở trên — task thêm/bỏ/đổi verification. Trỏ tới task-id cụ thể.}}

**Final task list (chốt dispatch):**
- {{<task-id>}} → {{assignee}} — {{gate 1 dòng}}
- {{<task-id>}} → {{assignee}} — {{gate 1 dòng}}
