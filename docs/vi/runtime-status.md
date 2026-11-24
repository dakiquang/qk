# Trạng thái trong runtime

[English](../en/runtime-status.md) · [Mục lục](README.md) · [Chạy qua đêm](overnight.md) · [Runner](runner.md)

Xem runner (và các công cụ khác bạn liệt kê) đang làm gì ngay trong omp, Claude Code hoặc Codex. Bạn cũng được nhắc khi có thẻ chờ quyết, và có thể quyết ngay trong chat. Adapter chỉ hiển thị và hỏi. Quyết định vẫn đi qua `qk decide`, theo đúng lựa chọn bạn nói ra.

Mọi adapter đọc chung các lệnh sau:

- `qk run status --line`: mỗi run một dòng. Gồm run đang chạy, run dừng giữa chừng, run chờ duyệt plan hoặc chờ hạn mức, kèm `+N queued`. Status line bỏ qua run không ai động tới trong một ngày; `--json` liệt kê đủ. Xem [Runner](runner.md#cách-dùng).
- `qk brief --pending`: một dòng khi có thẻ chờ quyết, không thì không in gì. `qk brief --json` đưa các thẻ cho skill hoặc extension. Xem [Hợp đồng CLI](cli-contract.md#các-lệnh).
- `adapters/status_lines.py`: chạy từng lệnh liệt kê trong `~/.config/qk/status-commands`, mỗi dòng một lệnh (mặc định `qk run status --line`). Mỗi lệnh có 1 giây; kết quả được cache 5 giây. Thêm lệnh trạng thái của công cụ khác vào file này; ví dụ qk-harness có `qk-harness status --line`.

Không có bước nào dưới đây tự cài. Mỗi bước sửa cấu hình runtime của chính bạn, nên hãy sao lưu trước. Adapter chỉ thêm vào cái đang có, không thay thế gì.

| | Trạng thái sống | Nhắc khi mở phiên | Quyết trong chat |
|---|---|---|---|
| omp 19.0.0 | có, ở thanh trạng thái, 15 giây cập nhật một lần | thông báo | `/qk-brief` (hộp chọn), hoặc skill |
| Claude Code | có, status line cập nhật mỗi 10 giây | có | skill `qk-morning`, hỏi bằng hộp thoại |
| codex-cli 0.160.0 | không: `[tui] status_line` chỉ nhận các mục có sẵn | có, dưới dạng dòng cảnh báo | skill `qk-morning`, hỏi bằng chữ |

## omp

```bash
ln -s <qk>/adapters/omp/qk-status.ts ~/.omp/agent/extensions/qk-status.ts
ln -s <qk>/skills/qk-morning ~/.omp/agent/skills/qk-morning
```

Extension đặt mục trạng thái `qk` từ `status_lines.py` mỗi 15 giây và sau mỗi lượt agent. Khi phiên mở ra mà có thẻ chờ, nó hiện một thông báo. `/qk-brief` chạy `qk sync`, rồi hiện từng thẻ trong hộp chọn, gồm đúng các lựa chọn `qk decide` nhận, cộng thêm `skip`. Nó chỉ hỏi cách merge khi repo cho phép nhiều cách. Các extension khác (ví dụ của Orca) vẫn chạy bình thường.

## Claude Code

Trong `~/.claude/settings.json`, bọc status line bạn đang dùng. Phần sau đường dẫn script là lệnh hiện tại của bạn. Rồi thêm hook:

```json
"statusLine": {
  "type": "command",
  "refreshInterval": 10,
  "command": "/bin/sh <qk>/adapters/claude/statusline.sh <lệnh status line hiện tại>"
},
"hooks": {
  "SessionStart": [{"hooks": [{"type": "command", "command": "python3 <qk>/adapters/session_start.py"}]}]
}
```

```bash
ln -s <qk>/skills/qk-morning ~/.claude/skills/qk-morning
```

Status line in dòng hiện tại của bạn trước, rồi mỗi mục của qk một dòng. Hook không in gì khi không có gì chờ. Khi có, nó hiện lời nhắc cho bạn (`systemMessage`) và thêm đúng dòng đó, kèm gợi ý dùng `qk-morning`, vào ngữ cảnh của phiên. Đây là phần duy nhất tốn token. Chưa kiểm tab Code của app desktop có hiện status line tuỳ biến không.

## Codex

Trong `~/.codex/hooks.json`:

```json
{"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "python3 <qk>/adapters/session_start.py"}]}]}}
```

```bash
ln -s <qk>/skills/qk-morning ~/.codex/skills/qk-morning
```

Codex bỏ qua hook mới hoặc hook vừa sửa cho tới khi bạn trust nó bằng `/hooks`. Codex hiện `systemMessage` dưới dạng một dòng cảnh báo. Giữ nguyên cấu hình `notify` đang có; adapter này không dùng nó.

## Buổi sáng

Gọi skill bằng tên, ví dụ `/qk-morning` trong Claude Code, `$qk-morning` trong Codex, hoặc `/qk-brief` trong omp. Skill chạy `qk sync`, rồi đi từng thẻ. Nó chỉ ghi lựa chọn bạn nói ra, và kết thúc bằng báo cáo bốn dòng. `abort-later` và `resume-later` chỉ ghi ý định; bạn vẫn tự chạy `qk run abort` hoặc `qk run resume`.
