---
name: qk-handoff
description: >-
  Viết bản bàn giao để phiên hoặc agent khác tiếp tục đúng việc mà không mất
  quyết định, hoặc nhận một bản bàn giao và kiểm lại trạng thái trước khi làm
  tiếp. Chỉ dùng khi người dùng gọi đích danh qk/handoff (`/qk-handoff`,
  `$qk-handoff`, `/skill:qk-handoff`).
disable-model-invocation: true
---

# qk/handoff

Hai chế độ: `write [trọng tâm phiên sau]` (mặc định) và `resume <path>`.

| | |
|---|---|
| **Kết quả** | `write`: bản bàn giao đủ để làm tiếp. `resume`: báo cáo trạng thái thật so với bản bàn giao |
| **Quyền** | `write`: chỉ ghi file bàn giao. `resume`: chỉ đọc cho tới khi người dùng xác nhận bước tiếp theo. Bàn giao truyền ngữ cảnh, **không truyền quyền** |
| **Xong khi** | `write`: phiên mới không phải hỏi lại điều đã quyết. `resume`: mọi điểm lệch giữa bản bàn giao và repo đã nêu |

## write

1. Không chép lại nội dung đã có trong plan, issue, commit hay diff; trỏ tới đường dẫn hoặc revision.
2. Ghi trạng thái thật, không ghi việc định làm thành việc đã xong. Cái chưa chạy kiểm chứng thì ghi "chưa kiểm".
3. Ghi quyền: quyền nào đã được cấp trong phiên này và **không** tự chuyển sang phiên sau (commit, push, merge, publish...).
4. Xoá secret, token, dữ liệu khách hàng, URL riêng. Không chép transcript.
5. Lưu theo quy ước repo, mặc định `plans/handoff-<YYYYMMDD>-<slug>.md`. Repo không có chỗ phù hợp thì hỏi đường dẫn. In nội dung giống hệt trong câu trả lời.

```markdown
# Bàn giao — <việc> (<ngày giờ>)
Trọng tâm phiên sau: <...>

## Mục tiêu
## Trạng thái            <!-- xong / đang làm / bị chặn / chưa kiểm; kèm revision -->
## Quyết định và lý do
## Hướng đã bác và bẫy đã biết
## Bằng chứng            <!-- file, commit, lệnh + kết quả -->
## Việc còn mở           <!-- trạng thái và phụ thuộc, không phải lệnh cho agent -->
## Quyền                 <!-- đã cấp trong phiên này; cần xin lại ở phiên sau -->
## Vào lại
Đọc <các file>. Kiểm lại revision và trạng thái repo trước khi làm. Hỏi người dùng bước tiếp theo.
```

## resume

1. Đọc bản bàn giao và các nguồn nó trỏ tới.
2. Kiểm lại: branch, revision, `git status`, file được nhắc còn đúng không, plan có đổi sau bản bàn giao không.
3. Báo: điều còn đúng, điều đã lệch, việc tiếp theo hợp lý, và quyền cần xin lại.
4. Chờ người dùng xác nhận trước khi sửa gì.

## Ranh giới

- Chỉ dẫn cấp cao hơn, luật runtime và luật repo thắng skill này.
- Không đổi model, quyền, hook hay cấu hình. Không tự gọi skill qk khác.
