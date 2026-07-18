# deploy/seed — SNAPSHOT seed cho deploy (D-62)

## `shb-132.db`
- **md5:** `8b3597cd205fd46ca0ff1ff86083da1d`
- **Ngày snapshot:** 2026-07-18
- **Nguồn:** `../shb-digital-experts/missions/shb-132/seed/shb-132.db` (LAB repo — D-08).

## ĐÂY LÀ SNAPSHOT DEPLOY — KHÔNG PHẢI NGUỒN SỰ THẬT
Nguồn sự thật = LAB repo (`shb-digital-experts`). File này là bản CHỤP để repo TỰ CHỨA seed khi
deploy (VM clone-trần KHÔNG có LAB sibling → seed vỡ nếu không có snapshot). "Đặt đâu chạy đó"
(CLAUDE.md §1) + demo tất định + LAB tiếp tục evolve không ảnh hưởng deploy.

## Fallback chain (seed_from_lab)
Code seed resolve theo thứ tự: **LAB sibling path → snapshot này**. Dev có LAB cạnh repo → dùng
LAB (hành vi cũ). Deploy/VM không có LAB → tự rơi vào snapshot. 0 config.

## Refresh snapshot (khi LAB seed đổi có chủ đích)
```
cp ../shb-digital-experts/missions/shb-132/seed/shb-132.db deploy/seed/shb-132.db
md5sum deploy/seed/shb-132.db   # cập nhật md5 ở trên
```
> LƯU Ý: md5 file LAB gốc TRÔI liên tục (LAB train ghi runtime vào bảng assessments trong chính
> file db — by-design, xem T7-1). md5 ở đây = dấu content lúc snapshot, không cần khớp file LAB
> hiện tại. Schema + phân bố nghiệp vụ mới là thứ cần đúng (validator seed kiểm).
