# qk/debug

[English](../../en/skills/qk-debug.md) · [Mục lục](../README.md) · [Nguồn skill](../../../skills/qk-debug/SKILL.md)

## Khi nào dùng

Dùng khi có triệu chứng nhưng chưa biết nguyên nhân đã kiểm. Cung cấp lỗi nguyên văn, input, môi trường và từ khi nào xảy ra. Lỗi công cụ/đăng nhập không được biến thành bản vá code sản phẩm.

## Ví dụ đầu vào

```text
/qk-debug Lệnh import chỉ lỗi với CSV rỗng. Lệnh và lỗi chính xác: <dán output đã che dữ liệu nhạy cảm>. Tìm nguyên nhân gốc, chưa sửa code sản phẩm.
```

## Nhận được gì

Tái hiện nhỏ nhất hoặc lý do chưa tái hiện được; cơ chế gây lỗi kèm `file:line`; giả thuyết đã loại bằng phép thử phân biệt; cách sửa nhỏ nhất và lệnh kiểm sau sửa. Mỗi giả thuyết có phép thử có thể bác nó; sửa thử để xem hết lỗi không không phải chẩn đoán.

## Quyền và tiêu chí xong

Được đọc, tái hiện, chạy test hiện có. Log/script chẩn đoán tạm chỉ thêm khi cần và phải gỡ trước báo cáo. Mặc định không sửa code sản phẩm, trừ khi chat yêu cầu sửa.

Nếu đã yêu cầu sửa ngay, áp hợp đồng cook tại chỗ: sửa nhỏ nhất, chạy lại tái hiện và kiểm hồi quy liên quan; không nạp skill qk khác.

Xong khi nguyên nhân giải thích đủ triệu chứng và bằng chứng phân biệt nó với hướng khác. Nếu chỉ yêu cầu chẩn đoán, bạn tự gọi `qk/cook` kèm nguyên nhân đã kiểm khi muốn triển khai sửa.

Chỉ dẫn cấp cao hơn, luật runtime và repo luôn thắng. Skill không đổi model, quyền, hook hay cấu hình và không tự gọi skill qk khác.
