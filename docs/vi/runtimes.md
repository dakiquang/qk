# Runtime

[English](../en/runtimes.md) · [Mục lục](README.md)

qk mở rộng runtime, không thay tool, plan mode, task, subagent, cấu hình model, quyền hay hook của nó. Chỉ dẫn cấp cao hơn, luật runtime và luật repo (`AGENTS.md`, `CLAUDE.md`, tài liệu đóng góp) luôn thắng skill qk.

## Mức hỗ trợ

| Runtime | Trạng thái |
|---|---|
| Claude Code | Đã kiểm smoke |
| Codex | Đã kiểm smoke |
| omp | Đã kiểm smoke ở chế độ RPC; print mode không mở rộng `/skill:` (xem [đặc điểm đã thấy](#đặc-điểm-đã-thấy)) |
| Qwen Code | Đã nối link nhưng chưa kiểm; chưa xác nhận cấu hình chỉ-gọi-đích-danh |
| Orca | Không cần cài; Orca liệt kê skill của các agent nó chạy |

"Đã kiểm smoke" nghĩa là [checklist thủ công](evidence.md#checklist-kiểm-thủ-công) đạt trên phiên bản ghi trong [Bằng chứng kiểm thử](evidence.md). Đây không phải chứng nhận, và bản runtime mới hơn có thể cho kết quả khác.

## Chỉ chạy khi gọi đích danh

Skill qk chỉ nên chạy khi bạn gọi. Chỉ dựa vào tên thì chưa đủ: một skill có mô tả "dùng khi lập kế hoạch" có thể cạnh tranh với plan mode hay lệnh có sẵn của runtime. qk dùng hai lớp bảo vệ.

1. **Thiết lập riêng của từng runtime** ngăn model tự nạp skill.
2. **Mô tả nêu trigger cụ thể** (`qk/plan`, `/qk-plan`, `$qk-plan`, `/skill:qk-plan`) thay vì từ khoá công việc chung.

| Runtime | Thiết lập trong qk | Tác dụng |
|---|---|---|
| Claude Code | `disable-model-invocation: true` trong `SKILL.md` | Chỉ bạn gọi được skill. Tài liệu Claude Code nói thiết lập này cũng ngăn preload skill vào subagent |
| omp | Cùng trường, đọc thành `disableModelInvocation` | Không cho tự gọi |
| Codex | `agents/openai.yaml`: `policy.allow_implicit_invocation: false` | Không tự gọi ngầm |
| Qwen Code | Chưa xác nhận thiết lập | Chưa biết |

Theo hợp đồng, skill qk không nạp lẫn nhau; mỗi skill nêu lệnh tiếp theo để bạn tự gọi. Đây là ranh giới cách làm, không phải bảo đảm an ninh trên runtime chưa kiểm.

`scripts/validate.py` kiểm cả hai lớp. Nó chỉ nhận một dạng canonical của `agents/openai.yaml` (hai block, thụt hai space, chuỗi double quote không backslash, comment nguyên dòng), nên không biến thể YAML nào giấu được một policy khác.

## Hook ghi nhận sở thích

[Hook ghi nhận sở thích](preference-hook.md) là hook lệnh `UserPromptSubmit`, bật tuỳ chọn. Claude Code và Codex ghi trong tài liệu cùng một định dạng output (`hookSpecificOutput.additionalContext`), và hook in đúng định dạng đó cho cả hai.

| Runtime | Đăng ký ở đâu |
|---|---|
| Claude Code | `hooks` trong `settings.json` (user) hoặc `.claude/settings.local.json` (project) |
| Codex | `~/.codex/hooks.json`, `.codex/hooks.json` của project, hoặc `[hooks]` trong `config.toml` |
| omp, Qwen Code | Chưa hỗ trợ, chưa kiểm |

Codex bỏ qua hook mới hoặc vừa sửa cho tới khi bạn trust nó bằng `/hooks`; hook của project còn cần lớp `.codex/` của project đó được trust. Những gì đã kiểm trên từng runtime nằm ở [Bằng chứng kiểm thử](evidence.md#hook-ghi-nhận-sở-thích).

## Đặc điểm đã thấy

- **omp print mode.** `omp -p "/skill:qk-plan …"` gửi nguyên văn cho model, không mở rộng skill, với mọi skill kể cả skill có sẵn của omp. Dùng phiên tương tác hoặc chế độ RPC.
- **Danh sách skill trong omp.** Hỏi có những skill nào sẽ không thấy skill qk, vì chúng chỉ chạy khi gọi đích danh. Kiểm bản cài bằng cách gọi đích danh một skill.
- **Qwen ghi tham số skill xuống đĩa.** Khi gọi skill, Qwen ghi file tạm trong `.qwen/tmp/` của repo hiện tại, kể cả ở plan mode. Đây là hành vi của Qwen, không phải của qk; cân nhắc ignore `.qwen/` trong repo của bạn.
- **Thư mục skill trùng.** Link một skill vào hai thư mục mà cùng một runtime đọc có thể làm skill hiện hai lần. Chọn một nơi.

## Chọn agent và model theo việc

qk không có cấu hình model riêng. Dùng cái runtime đã có:

- **omp:** định nghĩa agent có frontmatter trỏ tới một role (`model: "@plan"`) và ánh xạ role trong `modelRoles`, hoặc đặt `task.agentModelOverrides`. Cách này vẫn dùng được khi tắt override model cho từng lời gọi.
- **Claude Code:** `--model`, hoặc model trong định nghĩa subagent.
- **Codex:** `-m <model>`.
- **Qwen Code:** `-m <model>`.

`qk/agent-coord` dùng các đường này để chạy việc trên đúng agent và model bạn nêu, và báo `blocked` thay vì âm thầm chuyển sang model khác. Xem [qk/agent-coord](skills/qk-agent-coord.md).
