---
name: qk-cook
description: >-
  Triển khai một yêu cầu rõ ràng hoặc plan đã duyệt, tự kiểm chứng và tự review
  trong phạm vi được giao. Chỉ dùng khi người dùng gọi đích danh qk/cook
  (`/qk-cook`, `$qk-cook`, `/skill:qk-cook`). Không dùng cho yêu cầu sửa code
  thông thường khi người dùng không gọi qk/cook.
disable-model-invocation: true
---

# qk/cook

Đầu vào: một yêu cầu có tiêu chí xong, hoặc đường dẫn plan đã duyệt (có thể kèm giai đoạn cần làm).

| | |
|---|---|
| **Kết quả** | Thay đổi đạt tiêu chí xong, có bằng chứng kiểm chứng, chỉ nằm trong phạm vi |
| **Quyền** | Sửa file trong phạm vi; chạy lệnh build/test/lint của repo. Không commit, push, merge, tag, deploy hay đăng gì ra ngoài trừ khi chat yêu cầu rõ cho đúng việc đó |
| **Xong khi** | Mọi tiêu chí xong đã kiểm bằng lệnh hoặc kịch bản có output; lỗi do chính thay đổi gây ra đã sửa; phần chưa kiểm được ghi rõ |

## Trước khi sửa

1. Đọc plan (nếu có), luật repo và mã liên quan. Plan cũ hơn mã hiện tại thì kiểm lại giả định trước khi làm.
2. Thiếu tiêu chí xong hoặc một quyết định thay đổi hành vi mà nguồn không trả lời → hỏi một lần. Việc còn mơ hồ về hướng đi → dừng, đề xuất `qk/plan`.
3. Worktree có thay đổi chưa commit không thuộc việc này → không stash, không ghi đè; làm quanh chúng hoặc hỏi.
4. Được giao qua `qk/agent-coord` để ghi: chỉ làm trong worktree được chỉ định.

## Làm

- Thay đổi nhỏ nhất đạt mục tiêu, theo quy ước có sẵn của repo. Không refactor, không đổi tên, không thêm abstraction ngoài yêu cầu.
- Gặp điểm plan sai hoặc mâu thuẫn mã thật: chọn cách nhỏ nhất vẫn đúng mục tiêu, ghi lại quyết định và lý do. Nếu lựa chọn đổi hành vi người dùng thấy, đổi API công khai, hoặc vượt phạm vi → dừng và hỏi.
- Không thêm dòng tác giả AI, `Co-Authored-By` hay "Generated with" trừ khi repo bắt buộc.

## Kiểm chứng

- Lệnh lấy từ repo: config, CI workflow, script manifest, tài liệu đóng góp. Không bịa lệnh.
- Chạy đúng hành vi vừa đổi: test tập trung, rồi bộ test liên quan; với thay đổi chạy được thì chạy thật một lần.
- Lỗi có sẵn trên base là baseline, ghi riêng. Không nới test, xoá assertion, tắt hook hay dùng `--no-verify` để xanh.
- Tự review diff: chỉ file trong phạm vi, không secret, không debug còn sót, không thay đổi ngoài ý muốn.
- Thay đổi đáng kể cần góc nhìn độc lập: đề xuất người dùng gọi `pr-orchestrator review` hoặc giao reviewer khác họ model qua `qk/agent-coord`.

## Báo cáo

```text
Đã làm:        <tóm tắt>
File đổi:      <path — lý do>
Kiểm chứng:    <lệnh → kết quả thật>
Chưa kiểm:     <gì, vì sao>
Quyết định:    <điểm lệch plan và lý do, nếu có>
Tiếp theo:     <lệnh người dùng có thể gọi, ví dụ pr-orchestrator review>
```

Cập nhật trạng thái trong plan nếu đang làm theo plan.

## Ranh giới

- Chỉ dẫn cấp cao hơn, luật runtime và luật repo thắng skill này.
- Dùng tool, task và subagent có sẵn. Không đổi model, quyền, hook hay cấu hình.
- Không tự gọi skill qk khác.
