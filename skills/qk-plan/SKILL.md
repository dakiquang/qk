---
name: qk-plan
description: >-
  Tạo, audit hoặc sửa một kế hoạch triển khai có nguồn, quyết định, tiêu chí xong
  và rủi ro. Chỉ dùng khi người dùng gọi đích danh qk/plan (`/qk-plan`,
  `$qk-plan`, `/skill:qk-plan`). Không dùng cho yêu cầu lập kế hoạch chung chung
  khi người dùng không gọi qk/plan.
disable-model-invocation: true
---

# qk/plan

Ba chế độ, đọc từ lời gọi: `create` (mặc định khi chưa có plan), `audit <path>`, `revise <path>`.

| | |
|---|---|
| **Kết quả** | Một plan người dùng duyệt được: biết làm gì, vì sao, phạm vi, cách kiểm, rủi ro |
| **Quyền** | Đọc repo và nguồn ngoài. Chỉ ghi file plan được chỉ định hoặc theo quy ước repo. Không sửa code, không cài đặt, không chuyển sang triển khai |
| **Xong khi** | Mọi khẳng định có nguồn hoặc nhãn suy đoán; tiêu chí xong kiểm được; câu hỏi cần người dùng quyết được liệt kê |

## create

1. Làm rõ mục tiêu, điều không được đổi và ngoài phạm vi từ lời gọi, plan cũ, issue, mã nguồn. Thiếu một quyết định quan trọng mà nguồn không trả lời được thì hỏi một lần.
2. Đọc luật repo và phần mã liên quan. Thiếu dữ kiện quyết định hướng đi thì kiểm bằng nguồn chính hoặc thử nhanh trong thư mục tạm; nếu cần nghiên cứu dài, dừng và đề xuất `qk/research`.
3. Chọn độ dài theo rủi ro: việc nhỏ vài mục; việc lớn mới tách giai đoạn.
4. Ghi vào `plans/<slug>.md`, hoặc nơi repo đã quy ước. Không ghi đè plan có sẵn khi chưa được yêu cầu.

Cấu trúc gợi ý, bỏ mục không cần:

```markdown
# <Tên việc>
Trạng thái: nháp | đã duyệt | đang làm | xong — <ngày>

## Mục tiêu và ngoài phạm vi
## Hiện trạng và bằng chứng   <!-- nguồn, lệnh đã chạy; đánh dấu [Đã kiểm] / [Suy đoán] -->
## Quyết định                 <!-- chọn gì, vì sao, hướng bị bác -->
## Thay đổi dự kiến           <!-- file, giao diện, dữ liệu -->
## Các bước                   <!-- mỗi bước: việc | xong khi -->
## Kiểm chứng                 <!-- lệnh hoặc kịch bản chứng minh tiêu chí xong -->
## Rủi ro                     <!-- tín hiệu thất bại và cách phản ứng -->
## Câu hỏi mở
```

## audit

Đối chiếu plan với nguồn, không sửa plan:

- Khẳng định về mã, phiên bản, API: đọc lại đúng nguồn hoặc chạy lại lệnh đã nêu.
- Tiêu chí xong có kiểm được không; bước nào thiếu phụ thuộc; scope có phình hoặc mâu thuẫn quyết định đã chốt.
- Mỗi finding: mức (blocker / important / nit), vị trí trong plan, bằng chứng, đề xuất sửa. Không có bằng chứng thì ghi là câu hỏi, không ghi là lỗi.
- Ý kiến của model khác là đầu vào cần kiểm, không phải kết luận.

## revise

Áp các quyết định và finding người dùng đã chấp nhận. Sau đó rà toàn plan để mục khác không còn mâu thuẫn. Giữ bảng quyết định đã chốt và ghi ngày thay đổi. Không tự thêm scope mới.

## Báo cáo

Đường dẫn plan, tóm tắt thay đổi, câu hỏi còn mở. Bước tiếp theo nêu thành lệnh để người dùng gọi, ví dụ `qk/cook <path>`.

## Ranh giới

- Chỉ dẫn cấp cao hơn, luật runtime và luật repo thắng skill này.
- Dùng plan mode, task và tool có sẵn của runtime. Không đổi model, quyền, hook hay cấu hình.
- Không tự gọi skill qk khác. Duyệt plan không phải quyền commit, merge hay phát hành.
