# qk/handoff

[English](../../en/skills/qk-handoff.md) · [Mục lục](../README.md) · [Nguồn skill](../../../skills/qk-handoff/SKILL.md)

## Khi nào dùng

Dùng trước khi chuyển phiên/agent và khi nhận lại bản bàn giao. Giữ quyết định và bằng chứng, không giữ toàn transcript hoặc chuyển quyền hành động.

## Ví dụ

```text
/qk-handoff write Phiên sau tập trung kiểm chứng migration còn lại.
/qk-handoff resume plans/handoff-YYYYMMDD-migration.md
```

## Chế độ write

Là mặc định. Lưu theo quy ước repo, thường là `plans/handoff-<YYYYMMDD>-<slug>.md`; repo không có nơi phù hợp thì hỏi đường dẫn. In nội dung giống hệt file đã lưu trong câu trả lời.

Gồm mục tiêu, trạng thái thật kèm revision, quyết định/lý do, hướng đã bác và bẫy, nguồn bằng chứng, việc mở/phụ thuộc, quyền đã cấp trong phiên và checklist vào lại. Trỏ plan/issue/commit thay vì chép lại. Kiểm chưa chạy phải ghi chưa kiểm. Loại secret, token, dữ liệu khách hàng và URL riêng.

## Chế độ resume

Đọc bàn giao và nguồn được trỏ; kiểm branch, revision, trạng thái worktree, file được nhắc và độ lệch plan. Báo điều còn đúng, điều đổi, bước tiếp theo hợp lý và quyền cần xin lại. Chờ bạn xác nhận trước khi sửa.

## Quyền và tiêu chí xong

Write chỉ ghi file bàn giao. Resume chỉ đọc cho tới khi bạn xác nhận bước tiếp. Quyền commit/push/merge/publish cũ không truyền qua file.

Write xong khi phiên mới không phải tìm lại quyết định đã chốt. Resume xong khi độ lệch đã được nêu, không phải khi tự bắt đầu triển khai phần còn lại. Bạn chọn lệnh tiếp theo.

Chỉ dẫn cấp cao hơn, luật runtime và repo luôn thắng. Skill không đổi model, quyền, hook hay cấu hình và không tự gọi skill qk khác.
