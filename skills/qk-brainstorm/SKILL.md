---
name: qk-brainstorm
description: >-
  So sánh các hướng giải quyết một vấn đề chưa rõ, nêu đánh đổi và giả định cần
  kiểm, rồi khuyến nghị một hướng để người dùng chọn. Chỉ dùng khi người dùng gọi
  đích danh qk/brainstorm (`/qk-brainstorm`, `$qk-brainstorm`,
  `/skill:qk-brainstorm`).
disable-model-invocation: true
---

# qk/brainstorm

| | |
|---|---|
| **Kết quả** | 2–4 hướng khả thi, đánh đổi, giả định then chốt và một khuyến nghị. Người dùng chọn hướng |
| **Quyền** | Chỉ đọc. Ghi file chỉ khi được yêu cầu kèm đường dẫn. Không triển khai |
| **Xong khi** | Mỗi hướng có lợi, hại, chi phí quay đầu; giả định kiểm được bằng nguồn có sẵn đã kiểm; điều cần người dùng quyết được nêu rõ |

## Cách làm

1. Nhắc lại vấn đề bằng một câu, kèm ràng buộc và điều không được đổi. Hiểu sai vấn đề thì mọi hướng đều sai, nên hỏi trước nếu vấn đề còn hai cách hiểu khác nhau về kết quả.
2. Đọc mã, tài liệu và quyết định cũ liên quan. Ý tưởng phải bám hệ thống thật, không bám mô hình lý tưởng.
3. Luôn xét hướng đơn giản nhất và hướng "không làm / làm thủ công". Loại hướng vi phạm ràng buộc, ghi một dòng lý do.
4. So theo: kết quả có đạt không; trường hợp xấu nhất hợp lý; khó đảo ngược đến đâu; chi phí bảo trì; phụ thuộc mới.
5. Tách giả định then chốt (sai thì hướng hỏng). Cái nào kiểm nhanh được thì kiểm ngay; cái nào cần nghiên cứu thì đề xuất `qk/research`.

## Báo cáo

```markdown
Vấn đề: <một câu> — Ràng buộc: <...>

| Hướng | Cách làm | Được | Mất | Quay đầu |
|---|---|---|---|---|

Giả định then chốt: <giả định — đã kiểm / chưa kiểm>
Khuyến nghị: <hướng> vì <lý do>; đổi ý nếu <điều kiện>
Cần người dùng quyết: <câu hỏi>
Tiếp theo: qk/plan sau khi chọn hướng, hoặc qk/research cho giả định chưa kiểm
```

## Ranh giới

- Chỉ dẫn cấp cao hơn, luật runtime và luật repo thắng skill này.
- Không đổi model, quyền, hook hay cấu hình. Không tự gọi skill qk khác.
