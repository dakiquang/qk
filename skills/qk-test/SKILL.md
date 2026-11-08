---
name: qk-test
description: >-
  Kiểm tra độc lập một thay đổi bằng lệnh test, lint, typecheck khám phá từ repo;
  báo kết quả thật, phân loại lỗi mới và baseline, không sửa để cho xanh. Chỉ
  dùng khi người dùng gọi đích danh qk/test (`/qk-test`, `$qk-test`,
  `/skill:qk-test`).
disable-model-invocation: true
---

# qk/test

Dùng khi cần kiểm rộng hơn hoặc độc lập với phần kiểm trong `qk/cook`, ví dụ trước khi merge, sau khi người khác sửa, hoặc trên môi trường khác.

| | |
|---|---|
| **Kết quả** | Lệnh đã chạy, exit code, lỗi mới so với baseline, khoảng trống kiểm thử |
| **Quyền** | Chạy lệnh kiểm của repo. Không sửa mã, không đổi cấu hình test, không cài dependency mới, không commit |
| **Xong khi** | Mỗi lệnh có kết quả thật; lỗi được phân loại; điều không chạy được ghi lý do |

## Cách làm

1. Khám phá lệnh theo thứ tự: tài liệu của repo, CI workflow, script trong manifest (`package.json`, `composer.json`, `Makefile`...). Không chọn sẵn công cụ hay package manager.
2. Xác định phạm vi: test của phần thay đổi trước, rồi bộ rộng hơn nếu được yêu cầu hoặc thay đổi chạm giao diện chung.
3. Chạy, giữ output. Output dài thì ghi vào file tạm, chỉ trích phần lỗi.
4. Lỗi xuất hiện: kiểm có trên base không (đọc CI của base, hoặc chạy trên base khi người dùng cho phép tạo worktree tạm). Có trên base là baseline, không tính cho thay đổi.
5. Lỗi chập chờn: chạy lại tối đa hai lần, ghi cả hai kết quả, không gọi là pass.
6. Nêu hành vi đã đổi mà chưa có test nào chạm tới.

## Báo cáo

```text
| Lệnh | Exit | Kết quả |
Lỗi mới:      <test — thông điệp — nghi do đâu>
Baseline:     <lỗi có sẵn>
Chập chờn:    <...>
Chưa kiểm:    <hành vi / môi trường — lý do>
```

Trạng thái CI từ xa ghi là CI, không ghi là test local.

## Ranh giới

- Chỉ dẫn cấp cao hơn, luật runtime và luật repo thắng skill này.
- Không đổi model, quyền, hook hay cấu hình. Không tự gọi skill qk khác.
