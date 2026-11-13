# Hook ghi nhận sở thích

[English](../en/preference-hook.md) · [Mục lục tài liệu](README.md)

Bạn thường dặn agent những điều muốn áp dụng lâu dài: "từ nay commit message viết tiếng Anh", "đừng bao giờ amend commit đã push". Có hai kiểu thất bại: runtime quên mất, hoặc agent tự ghi thẳng vào memory mà không hỏi. Hook tuỳ chọn này nằm giữa hai kiểu đó. Khi prompt có cụm từ thể hiện ý định lâu dài, hook nhắc agent ghi một **đề xuất** vào file cục bộ rồi làm tiếp việc đang dở. Không có gì vào memory, rules, `CLAUDE.md` hay `AGENTS.md` cho tới khi bạn duyệt.

> **Trạng thái:** hook và kho đề xuất nằm trong [`scripts/qk_prefs.py`](../../scripts/qk_prefs.py), có test ở [`tests/test_qk_prefs.py`](../../tests/test_qk_prefs.py). Bạn duyệt đề xuất bằng [qk/prefs](skills/qk-prefs.md) ([ví dụ 5](#5-quyết-định-một-đề-xuất)). Hook chạy được với Claude Code và Codex; xem [Runtime](runtimes.md#hook-ghi-nhận-sở-thích) để biết từng runtime đã kiểm đến đâu.

Hook chỉ thêm một lời nhắc vào prompt. Nó không bắt được agent ghi, và nó không quyết định câu nào là sở thích: agent tự đánh giá, còn bạn là người duyệt.

## 1. Câu nào kích hoạt

Hook tìm các cụm từ nêu quy tắc lâu dài, cả tiếng Việt lẫn tiếng Anh. Những từ thông dụng như "always", "never", "by default" và "mặc định" chỉ được tính khi đứng đầu câu hoặc sau từ dẫn như "please", "you should", "hãy", vì ở chỗ khác chúng thường chỉ mô tả việc đang làm.

| Prompt | Có nhắc? | Lý do |
|---|---|---|
| `Từ nay commit message viết bằng tiếng Anh` | Có | "từ nay" |
| `Mặc định trả lời bằng tiếng Việt` | Có | "mặc định" |
| `Never amend a pushed commit` | Có | "never" đứng đầu câu |
| `Please always use pnpm` | Có | "always" sau "please" |
| `Next time, check the changelog first` | Có | "next time," |
| `This function never returns` | Không | "never" ở giữa câu |
| `Use a dict instead of a list here` | Không | "instead of" không phải cụm kích hoạt, vì thường là lựa chọn một lần |
| `Rename it, by default the arg is None` | Không | "by default" sau dấu phẩy là đang mô tả code |
| `Lần sau mình làm tiếp nhé` | Không | "lần sau" chỉ tính khi đi với "nhớ", "hãy", "đừng", "phải", "luôn" hoặc "cứ" |
| `làm luôn đi` | Không | "luôn" đứng một mình thường nghĩa là "ngay". Chỉ "luôn luôn" mới được tính |
| `never mind, revert that` | Không | "never mind" bị loại trừ |
| ``Rename `alwaysRetry` to `retry` `` | Không | Bỏ qua inline code và khối code |
| `> from now on use tabs` (dòng trích dẫn) | Không | Bỏ qua dòng trích dẫn |
| `/qk-plan từ nay dùng pnpm` | Không | Bỏ qua lệnh gọi skill và slash command |

Vì dựa trên danh sách cụm từ, hook vẫn có lúc bắt nhầm. Ví dụ `Always the same error here` khớp vì "always" đứng đầu câu, và `See you next time, bye` khớp "next time,". Hook cũng bỏ sót sở thích nói theo cách khác, ví dụ `I prefer short commit subjects` hay `Dùng vitest thay vì jest`. Hook chỉ quét 4.000 ký tự đầu của prompt, nên sở thích nêu ở cuối một tin nhắn dài sẽ bị bỏ sót. Bắt nhầm chỉ tốn một lời nhắc bị bỏ qua, vì agent quyết định có đáng ghi hay không. Danh sách đầy đủ là `CUE_RE` trong script; các ca test `POSITIVE`/`NEGATIVE` cho thấy hành vi mong muốn.

## 2. Thử hook mà chưa cần bật

Tự đưa payload vào hook. Khi khớp, hook in lời nhắc ở dạng JSON hook của Claude Code; khi không khớp thì không in gì.

```bash
echo '{"prompt":"Từ nay commit message viết bằng tiếng Anh"}' | python3 ~/src/qk/scripts/qk_prefs.py hook --runtime claude
```

```bash
echo '{"prompt":"làm luôn đi"}' | python3 ~/src/qk/scripts/qk_prefs.py hook --runtime claude
```

Đường dẫn giả định bạn clone qk theo [Bắt đầu](getting-started.md).

## 3. Bật thử ở một project trước

qk không bao giờ sửa config của runtime. Bạn tự thêm hook, và nên bắt đầu ở một project thử để không ảnh hưởng các phiên khác. Thêm vào `.claude/settings.local.json` của project đó:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/src/qk/scripts/qk_prefs.py hook --runtime claude",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

Nếu file đã có khối `hooks`, thêm mục `UserPromptSubmit` vào khối đó chứ đừng thay cả khối. Mở phiên mới để hook có hiệu lực. Muốn bật cho mọi project thì đặt cùng mục đó vào `~/.claude/settings.json`. Muốn tắt thì xoá mục đó.

**Codex** dùng cùng định dạng. Đặt cùng khối JSON vào `.codex/hooks.json` của project, hoặc `~/.codex/hooks.json` cho mọi project, và đổi thành `--runtime codex`. Nếu file đã có thì gộp mục vào, đừng thay cả file. Sau đó mở Codex, gõ `/hooks` để xem và trust hook, vì Codex bỏ qua hook chưa được trust.

Mỗi prompt sẽ chạy một tiến trình Python ngắn. Test độ trễ trong file test kiểm rằng phần hook cộng thêm dưới 50 ms so với lúc khởi động interpreter trống; test này chỉ chạy trên máy local, bị bỏ qua trên CI.

## 4. Agent ghi gì

Trong phiên, bạn gõ: `Từ nay commit message viết bằng tiếng Anh`. Agent nhận lời nhắc. Nếu thấy đây là ý định lâu dài, agent chạy một lệnh kiểu:

```bash
python3 ~/src/qk/scripts/qk_prefs.py propose --stdin <<'QK_PREF'
{"scope": "global", "title": "Commit message language", "content": "Write commit messages in English.", "quote": "Từ nay commit message viết bằng tiếng Anh"}
QK_PREF
```

JSON đi qua heredoc có dấu nháy, nên dấu nháy đơn, `$` hay backtick trong lời của bạn không cần escape cho shell. Các trường này cũng dùng được dưới dạng cờ (`--scope`, `--title`, `--content`, `--quote`) khi gõ tay.

Dùng `"scope": "project"` cho sở thích chỉ áp dụng với repo hiện tại; tên project mặc định là tên thư mục đang đứng, nên hai repo trùng tên thư mục sẽ dùng chung tên project. Ghi lại cùng nội dung lần nữa sẽ trả về ID cũ chứ không tạo bản trùng. Giới hạn của từng lệnh xem bằng `--help`.

Xem các đề xuất đang chờ:

```bash
python3 ~/src/qk/scripts/qk_prefs.py list
```

Mỗi dòng là một đề xuất dạng JSON, ví dụ:

```json
{"id": "2cd33227", "created": "2026-11-13T15:59:32+07:00", "status": "pending", "scope": "global", "project": "", "title": "Commit message language", "content": "Write commit messages in English.", "quote": "Từ nay commit message viết bằng tiếng Anh"}
```

Đề xuất nằm ở `~/.local/state/qk/preferences-pending.jsonl`. Nếu có đặt `$XDG_STATE_HOME` thì là `$XDG_STATE_HOME/qk/`; nếu có đặt `$QK_PREFS_STATE_DIR` thì dùng thư mục đó. File được tạo với quyền `0600` và nằm ngoài mọi repo, vì nó chứa lời nguyên văn của bạn. Lời nhắc có dặn agent không ghi secret hay dữ liệu khách hàng, nhưng đó chỉ là chỉ dẫn, không phải bộ lọc. Hãy đọc đề xuất trước khi áp dụng. Trên macOS và Linux, các lần ghi được tuần tự hoá bằng khoá file; trên Windows script chạy không có khoá, nên đừng ghi hay duyệt đề xuất từ hai phiên cùng lúc.

## 5. Quyết định một đề xuất

Gọi `/qk-prefs`. Skill hiện bảng các đề xuất đang chờ, gợi ý đích cho từng mục và chỉ ghi những mục bạn duyệt; xem ví dụ một phiên ở [qk/prefs](skills/qk-prefs.md).

Muốn làm tay thì chép `content` của đề xuất vào file memory, rules hoặc `AGENTS.md` phù hợp, rồi đánh dấu:

```bash
python3 ~/src/qk/scripts/qk_prefs.py resolve 2cd33227 applied --target "~/.claude/rules/development-rules.md"
```

Hoặc bỏ đề xuất:

```bash
python3 ~/src/qk/scripts/qk_prefs.py resolve 2cd33227 dismissed
```

Mỗi đề xuất chỉ quyết được một lần; quyết lại sẽ báo lỗi `already applied` hoặc `already dismissed`. `list --all` hiện cả các đề xuất đã quyết.

## Vì sao làm như vậy

- **Ghi đề xuất, không ghi thẳng.** Agent hay hiểu nhầm yêu cầu một lần thành quy tắc. File chờ giữ mọi thay đổi lâu dài sau bước duyệt của bạn, đúng nguyên tắc của qk: giao việc không đồng nghĩa giao quyền.
- **Danh sách cụm từ, không phải đoán ý định.** Cách này rẻ, chạy cục bộ và dễ đoán. Agent mới là người đánh giá; hook chỉ đảm bảo agent được hỏi.
- **Python standard library.** qk vốn đã cần Python cho validator và runner, nên hook không thêm dependency nào.

Ý tưởng bắt sở thích lâu dài rồi giữ chờ đồng ý lấy từ [personal-brain-style](https://github.com/nghiacr002/personal-brain-style) (MIT). Bản trong qk được viết riêng.
