# Trạng thái trong runtime

[English](../en/runtime-status.md) · [Mục lục](README.md) · [Chạy qua đêm](overnight.md) · [Runner](runner.md)

Xem runner (và các công cụ khác bạn liệt kê) đang làm gì ngay trong omp, Claude Code hoặc Codex. Bạn cũng được nhắc khi có thẻ chờ quyết, và có thể quyết ngay trong chat. Adapter chỉ hiển thị và hỏi. Quyết định vẫn đi qua `qk decide`, theo đúng lựa chọn bạn nói ra.

Mọi adapter đọc chung các lệnh sau:

- `qk run status --line`: mỗi run một dòng. Gồm run đang chạy, run dừng giữa chừng, run chờ duyệt plan hoặc chờ hạn mức, kèm `+N queued`. Status line bỏ qua run không ai động tới trong một ngày, và nhiều run dừng giữa chừng được gộp thành một dòng; `--json` liệt kê đủ. Xem [Runner](runner.md#cách-dùng).
- `qk brief --pending`: một dòng khi có thẻ chờ quyết, không thì không in gì. `qk brief --json` đưa các thẻ cho skill hoặc extension. Xem [Hợp đồng CLI](cli-contract.md#các-lệnh).
- `adapters/status_lines.py`: chạy từng lệnh liệt kê trong `~/.config/qk/status-commands`, mỗi dòng một lệnh (mặc định `qk run status --line`). Mỗi lệnh có 1 giây; kết quả được cache 5 giây. Thêm lệnh trạng thái của công cụ khác vào file này; ví dụ [qk-harness](https://github.com/dakiquang/qk-harness) có `qk-harness status --line`.

Không có bước nào dưới đây tự cài. Mỗi bước sửa cấu hình runtime của chính bạn, nên hãy sao lưu trước. Adapter chỉ thêm vào cái đang có, không thay thế gì.

| | Trạng thái sống | Nhắc khi mở phiên | Quyết trong chat |
|---|---|---|---|
| omp 19.0.0 | có, ở thanh trạng thái, 15 giây cập nhật một lần | thông báo | `/qk-brief` (hộp chọn), hoặc skill |
| Claude Code | có, status line cập nhật mỗi 10 giây | có | skill `qk-morning`, hỏi bằng hộp thoại |
| codex-cli 0.160.0 | không: `[tui] status_line` chỉ nhận các mục có sẵn | có, dưới dạng dòng cảnh báo | skill `qk-morning`, hỏi bằng chữ |

## Trông như thế nào

Status line trong Claude Code, nằm dưới dòng của lệnh bạn đang dùng (nếu lệnh đó in ra gì):

```text
qk 3f9c implementing 3/7 · 12m +2 queued
harness aaea46 · review.run eval · 1/2 tasks
```

Các dòng khác có thể gặp:

```text
qk 3f9c waiting claude limit until 23:50
qk 7b21 waits: approve plan
qk 3 runs stopped mid-stage (qk run status --json)
harness aaea46 · waits: approve plan
harness aaea46 · claude limit until 23:50
harness aaea46 · task api stopped mid-step · qk-harness run
harness 7 jobs not running (qk-harness status)
```

omp hiện đúng các dòng này ở thanh trạng thái, nối bằng ` | `:

```text
qk 3f9c implementing 3/7 · 12m | harness aaea46 · review.run eval · 1/2 tasks
```

Lời nhắc khi mở phiên (thông báo của Claude Code, dòng cảnh báo của Codex):

```text
qk: 3 runs to decide (latest 07:09): qk sync && qk brief; harness 7 jobs not running (qk-harness status)
```

Thông báo của omp chỉ có phần đầu: `qk: 3 runs to decide (latest 07:09): qk sync && qk brief (or /qk-brief here)`. Chỉ phần `qk: 3 runs to decide …` được đưa vào ngữ cảnh của model, kèm câu `Use the qk-morning skill to read the cards and record decisions.` Không có gì chờ thì không thêm gì.

Một thẻ trong `qk-morning` (đúng các dòng của brief), rồi câu hỏi:

```text
#1 project: Add CSV export (https://github.com/example/project/pull/10)  RISK: medium — never synced; full: qk show --id 0b837bbf8f5d
  Done: run 20261124-010203-abcdef status=done; 2 files, +72/-7; impl=codex:… review=claude:; PR=UNKNOWN; synced=never / unknown; full: qk show --id 0b837bbf8f5d
  Evidence: verify: 2 checks (exit=0:2 nonzero:0 unknown:0); review: remaining=0, queued-for-fix=0; UNKNOWN commit comparison / not verified; full: qk show --id 0b837bbf8f5d
  Unchecked: remaining findings=0; claims (not independent verification): no recorded model claims
  History: feature 7/8 done/total (informational)
  Decision: human decision required; sync state is a recorded observation, not approval.

Thẻ 1/3: merge / leave / skip?
```

Sau khi bạn trả lời: `Recorded merge: 5c1e…`. Báo cáo kết thúc bằng bốn dòng Xong, Bằng chứng, Chưa kiểm và Cần bạn quyết.

## omp

```bash
ln -s <qk>/adapters/omp/qk-status.ts ~/.omp/agent/extensions/qk-status.ts
```

Cài skill `qk-morning` như các skill qk khác ([Bắt đầu](getting-started.md)); omp đọc `~/.agents/skills`.

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

Cài skill `qk-morning` như các skill qk khác ([Bắt đầu](getting-started.md)).

Status line in dòng hiện tại của bạn trước, rồi mỗi mục của qk một dòng. Hook không in gì khi không có gì chờ. Khi có, nó hiện cho bạn lời nhắc và tối đa ba dòng trạng thái (`systemMessage`). Chỉ khi có thẻ chờ quyết, nó mới thêm đúng dòng đó, kèm gợi ý dùng `qk-morning`, vào ngữ cảnh của phiên: đây là phần duy nhất tốn token. Chưa kiểm tab Code của app desktop có hiện status line tuỳ biến không.

## Codex

Trong `~/.codex/hooks.json`:

```json
{"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "python3 <qk>/adapters/session_start.py"}]}]}}
```

Codex đọc skill `qk-morning` từ `~/.agents/skills` ([Bắt đầu](getting-started.md)). Codex bỏ qua hook mới hoặc hook vừa sửa cho tới khi bạn trust nó bằng `/hooks`. Codex hiện `systemMessage` dưới dạng một dòng cảnh báo. Giữ nguyên cấu hình `notify` đang có; adapter này không dùng nó.

## Buổi sáng

Gọi skill bằng tên, ví dụ `/qk-morning` trong Claude Code, `$qk-morning` trong Codex, hoặc `/qk-brief` trong omp. Skill chạy `qk sync`, rồi đi từng thẻ. Nó chỉ ghi lựa chọn bạn nói ra, và kết thúc bằng báo cáo bốn dòng. `abort-later` và `resume-later` chỉ ghi ý định; bạn vẫn tự chạy `qk run abort` hoặc `qk run resume`.
