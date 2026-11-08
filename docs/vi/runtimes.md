# Runtime

[English](../en/runtimes.md) · [Mục lục](README.md)

qk mở rộng runtime, không thay tool, plan mode, task, subagent, model, quyền hay hook. Chỉ dẫn cấp cao hơn, luật runtime và luật repo (`AGENTS.md`, `CLAUDE.md`, tài liệu đóng góp) luôn thắng skill.

## Chỉ chạy khi gọi đích danh

Tên riêng chưa đủ: mô tả “dùng khi lập kế hoạch” có thể cạnh tranh với plan mode/lệnh sẵn có. qk dùng hai lớp:

1. Cấu hình native của runtime để ngăn model tự nạp.
2. Mô tả nêu trigger cụ thể (`qk/plan`, `/qk-plan`, `$qk-plan`, `/skill:qk-plan`), không dùng từ khóa công việc chung làm điều kiện kích hoạt.

| Runtime | Cấu hình trong qk | Tác dụng |
|---|---|---|
| Claude Code | `disable-model-invocation: true` trong `SKILL.md` | Chỉ người dùng gọi; tài liệu Claude Code nói cũng không preload vào subagent |
| omp | Cùng trường, đọc thành `disableModelInvocation` | Không cho tự gọi |
| Codex | `agents/openai.yaml`: `policy.allow_implicit_invocation: false` | Không tự gọi ngầm |
| Qwen Code | Chưa xác nhận cấu hình | Chưa biết |

Theo hợp đồng, qk không tự gọi skill qk khác; chỉ nêu lệnh để bạn gọi. Đây là ranh giới cách làm, không phải bảo đảm an ninh trên runtime chưa kiểm.

`scripts/validate.py` kiểm cấu hình và mô tả, chỉ nhận dạng canonical của `agents/openai.yaml`: hai block, thụt hai space, chuỗi double quote không backslash, comment nguyên dòng. Cú pháp ngoài tập này bị từ chối thay vì diễn giải YAML tùy ý.

## Hành vi đã thử

Thử thật ngày 08/11/2026 trên repo tạm với chế độ chỉ đọc. Mỗi runtime một lời gọi đích danh `qk-brainstorm` và một yêu cầu lập kế hoạch không nhắc qk.

| Runtime | Gọi đích danh chạy skill | Yêu cầu thường không nạp qk |
|---|---|---|
| Claude Code (Sonnet 5.5, `--permission-mode plan`) | Có, trả đúng cấu trúc skill | Có, không nạp skill |
| Codex (`codex exec -s read-only`) | Có | Có, không đọc file skill |
| omp 18.15.0 (RPC) | Có, chèn nội dung skill | Có, không chèn |
| Qwen Code | Chưa thử được: API 401, token hết hạn | Chưa thử được |
| Orca | — | Liệt kê mỗi skill qk một lần |

Đây là một lần chạy, không phải chứng nhận. Chưa kiểm: phiên tương tác, lặp nhiều lần, Qwen sau đăng nhập lại và cùng tồn tại với mọi lệnh native.

## Đặc điểm đã thấy

- **omp print mode:** `omp -p "/skill:qk-plan …"` gửi nguyên văn, không mở rộng skill; đã đối chứng bằng `find-skills`. Dùng phiên tương tác hoặc RPC; phiên tương tác chưa được kiểm trực tiếp ở đợt trên.
- **Qwen ghi tham số xuống đĩa:** khi gọi skill, ghi file tạm trong `.qwen/tmp/` dù ở plan mode. Đây là hành vi Qwen, không phải qk; cân nhắc ignore thư mục này theo quy tắc repo của bạn.
- **Codex và thư mục trùng:** link ở hai thư mục nó đọc có thể khiến liệt kê hai lần. Chọn một nơi cài.

## Chọn agent/model theo việc

qk không tạo cấu hình model riêng. Dùng cơ chế runtime:

- **omp:** agent trỏ role qua `model: "@plan"` và ánh xạ `modelRoles`, hoặc `task.agentModelOverrides`. Dùng được khi tắt override từng lời gọi.
- **Claude Code:** `--model` hoặc model trong định nghĩa subagent.
- **Codex:** `-m <model>`.
- **Qwen Code:** `-m <model>`.

`qk/agent-coord` chọn đường chạy đáp ứng đúng agent/model đã nêu; không có thì báo blocked, không âm thầm fallback. Xem [hướng dẫn](skills/qk-agent-coord.md).
