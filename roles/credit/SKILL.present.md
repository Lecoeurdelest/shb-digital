<!-- PROVISIONAL — vỏ viết (D-36), LAB đè khi dạy present. KHÔNG phải skill LAB gốc.
     mount_role APPEND file này vào SKILL.md nếu tồn tại. LAB drop skill thật có present → xoá file này. -->

## Trình kết quả lên canvas (bắt buộc, TRƯỚC khi trả lời text)

Khi đã thẩm định xong (có đủ DSCR / LTV / nhóm CIC từ tool credit_assess/credit_cic_get):

1. Gọi tool `present` với:
   - type: "metric"
   - title: "Thẩm định tín dụng — <tên khách/DN>"
   - items: danh sách chỉ số, MỖI item kèm `source` = tên tool đã trả số đó. Ví dụ:
     - {name: "DSCR", value: <số từ credit_assess>, threshold: ">= 1.2", pass: <true/false>, source: "credit_assess"}
     - {name: "LTV", value: <số>, threshold: "<= 70%", pass: <true/false>, source: "credit_assess"}
     - {name: "Nhóm CIC", value: <nhóm từ credit_cic_get>, threshold: "nhóm 1-2", pass: <true/false>, source: "credit_cic_get"}

2. Mọi số trên card PHẢI từ tool và kèm `source` đúng tên tool đã trả số đó. Số không lấy từ tool
   → KHÔNG đưa lên card, KHÔNG đưa vào câu trả lời.

3. Tool trả "card đã lên canvas — tiếp tục" → LÚC ĐÓ mới viết text kết luận ngắn gọn trả về
   (verdict + điều kiện kèm theo).
