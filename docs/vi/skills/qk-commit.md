# qk/commit

[English](../../en/skills/qk-commit.md) · [Mục lục](../README.md) · [Nguồn skill](../../../skills/qk-commit/SKILL.md)

## Khi nào dùng

Gọi `qk/commit` khi công việc đã xong cần được commit. Nêu rõ các bước được phép: `commit`, `commit push` hoặc `commit push pr`. Skill đọc status và diff, loại file không liên quan hoặc nhạy cảm, quét nội dung sắp commit và theo quy ước commit message của repo. Báo cáo có SHA, danh sách file và trạng thái thật của từng bước được yêu cầu.

## Ví dụ đầu vào

```text
/qk-commit commit push pr
```

Dùng `$qk-commit` trong Codex hoặc `/skill:qk-commit` trong omp (interactive/RPC).

## Quyền hạn và khi nào xong

Skill chỉ chạy các bước đã nêu. Trước khi push, nó chạy [kiểm tra danh tính](../../../scripts/qk_preflight.py) với tài khoản `gh` đang hoạt động. Kiểm tra lỗi thì dừng push; người dùng tự đổi tài khoản. Mô tả PR ghi nội dung, lý do và các lệnh kiểm đã thực sự chạy trong phiên. Skill không amend, force-push, đổi tài khoản, merge hay tag.
