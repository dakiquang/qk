---
name: qk-debug
description: >-
  Tìm nguyên nhân gốc của một lỗi bằng chuỗi bằng chứng và tái hiện, rồi đề xuất
  cách sửa nhỏ nhất; mặc định không sửa code. Chỉ dùng khi người dùng gọi đích
  danh qk/debug (`/qk-debug`, `$qk-debug`, `/skill:qk-debug`).
disable-model-invocation: true
---

# qk/debug

| | |
|---|---|
| **Kết quả** | Nguyên nhân gốc có bằng chứng `file:line`, cách tái hiện, đề xuất sửa và cách kiểm sau sửa |
| **Quyền** | Đọc, chạy tái hiện, chạy test hiện có. Log hoặc script chẩn đoán tạm chỉ khi cần và phải gỡ trước khi báo cáo. Không sửa code sản phẩm trừ khi chat yêu cầu sửa |
| **Xong khi** | Có lệnh tái hiện (hoặc lý do không tái hiện được); nguyên nhân giải thích đủ triệu chứng; giả thuyết bị loại có lý do |

## Cách làm

1. Ghi triệu chứng chính xác: lỗi, input, môi trường, từ khi nào. Phân biệt điều người dùng thấy với điều mình suy ra.
2. Tái hiện bằng lệnh nhỏ nhất. Không tái hiện được thì thu hẹp điều kiện trước khi đoán.
3. Thu hẹp vùng: so với base hoặc bản chạy được, đọc log, chia đôi commit hay input.
4. Mỗi giả thuyết kèm phép thử có thể bác nó. Chạy phép thử, ghi kết quả. Không sửa thử để xem có hết lỗi không.
5. Tách triệu chứng với nguyên nhân: sửa chỗ lỗi hiện ra hay chỗ dữ liệu sai sinh ra? Tìm cùng mẫu lỗi ở chỗ khác.
6. Lỗi do môi trường hay công cụ, không phải mã: ghi rõ, không đề xuất sửa mã.

## Báo cáo

```text
Triệu chứng:   <...>
Tái hiện:      <lệnh> → <kết quả>
Nguyên nhân:   <file:line — cơ chế>
Bằng chứng:    <đã đọc gì / chạy gì>
Đã loại:       <giả thuyết — vì sao>
Đề xuất sửa:   <nhỏ nhất> — kiểm bằng: <lệnh>
```

Người dùng muốn sửa: nêu lệnh `qk/cook` kèm nguyên nhân đã kiểm làm đầu vào. Nếu chat đã yêu cầu sửa ngay, làm theo hợp đồng của qk/cook: thay đổi nhỏ nhất, chạy lại lệnh tái hiện và test hồi quy.

## Ranh giới

- Chỉ dẫn cấp cao hơn, luật runtime và luật repo thắng skill này.
- Dùng debugger và tool có sẵn của runtime. Không đổi model, quyền, hook hay cấu hình.
- Không tự gọi skill qk khác.
