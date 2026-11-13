# Thiết lập gọn nhẹ

[English](../en/lean-setup.md) · [Mục lục tài liệu](README.md)

Mỗi phiên đều nạp system prompt, tool, mô tả skill và các file instruction trước cả tin nhắn đầu tiên của bạn. Trang này chỉ cách xem phần đó tốn bao nhiêu và cách cắt bớt bằng chính những gì runtime đã có. qk chạy cùng các bộ skill khác và không bao giờ yêu cầu bạn gỡ chúng.

## 1. Đo

Đo trong một thư mục trống để file của dự án không bị tính vào, và mở phiên mới sau mỗi thay đổi. Một lần chạy cho ra con số ước lượng, không phải benchmark.

**Claude Code.** Gõ `/context` trong phiên, hoặc chạy dạng không tương tác:

```bash
claude -p "/context" --output-format json --verbose
```

Lệnh này không gọi model nên không tốn phí. Nó hiện số token ước lượng theo từng nhóm, gồm từng memory file và từng skill. Ví dụ rút gọn:

```text
System prompt      3,000 tokens
System tools      12,000 tokens
MCP tools          5,000 tokens
Memory files       4,000 tokens
  CLAUDE.md        1,000
  rules file       3,000
Skills             2,000 tokens
  some-skill         100
Messages             100 tokens
Free space       150,000 tokens
```

Output đầy đủ còn liệt kê MCP server instructions, MCP và System tools dạng deferred, Custom agents và Autocompact buffer.

**Codex.**

```bash
codex exec --sandbox read-only --skip-git-repo-check --json "Reply with the single word OK."
```

`--skip-git-repo-check` cho lệnh chạy được trong thư mục trống nằm ngoài git repository, điều mà `codex exec` vốn từ chối, còn `--sandbox read-only` giữ cho lần đo không ghi gì xuống đĩa. Đọc `usage.input_tokens` trong sự kiện `turn.completed`; lần đo tốn một lời gọi model nhỏ. Ví dụ: `turn.completed → usage.input_tokens: 12000`. Không có góc nhìn theo nhóm, nên hãy so tổng trước và sau khi thay đổi.

**omp.** Chạy `omp --mode json -p "Reply with the single word OK."` rồi đọc `usage.totalTokens` ở message cuối. Chạy lại với `--no-skills` để xem danh sách skill tốn bao nhiêu, và với `--no-context-files` để bỏ `AGENTS.md` / `CLAUDE.md`. Giá trị ví dụ: `15000 / 13000 / 11000`. `omp stats` và `omp usage` có tồn tại nhưng chưa được thử.

**Qwen Code.** Chưa kiểm.

Các con số là ví dụ, không phải số đo. Phiên bản đã dùng để kiểm các lệnh này nằm ở [Bằng chứng kiểm thử](evidence.md#số-đo-thiết-lập-gọn-nhẹ).

## 2. Cắt ba chỗ thường nặng

**Mô tả của skill tự gọi được.** Mỗi skill mà model được tự gọi đều mang mô tả của nó vào từng phiên; trong Claude Code, nhóm Skills liệt kê chúng kèm số token. Với skill bạn ít dùng:

- chuyển nó sang chỉ chạy khi gọi đích danh bằng thiết lập riêng của runtime (xem [Runtime](runtimes.md#chỉ-chạy-khi-gọi-đích-danh)), hoặc
- bỏ link nếu chính bạn đã tạo link đó và không còn dùng. Kiểm bằng `readlink` trước, như trong [Bắt đầu](getting-started.md#5-gỡ).

Đổi từng skill, không đổi cả bộ kit.

**Rules và file instruction luôn được nạp.** Trong Claude Code, Memory files liệt kê từng `CLAUDE.md` hoặc file rules kèm số token; trong omp, so với một lần chạy có `--no-context-files`. Giữ một mục lục ngắn trong file luôn được nạp và chuyển phần chi tiết sang các file agent chỉ đọc khi mục lục trỏ tới.

**Instruction người dùng bị lặp giữa các runtime.** Cùng một bộ quy tắc chép vào file instruction người dùng của từng runtime, và vào nhiều file mà một runtime cùng nạp, nhiều khả năng bị trả phí lại trong mỗi phiên. Ví dụ omp bỏ cả `AGENTS.md` lẫn `CLAUDE.md` khi có `--no-context-files`, nên quy tắc nằm ở cả hai file có thể bị nạp hai lần; đây là suy luận, không phải số đo. Mỗi runtime chỉ giữ một bản cho mỗi quy tắc và xoá các bản lặp.

## 3. Vì sao skill qk tốn ít cho tới khi được gọi

Mọi skill qk đều đặt `disable-model-invocation: true`, và `policy.allow_implicit_invocation: false` cho Codex. Trong lần kiểm trên Claude Code, skill có trường này không xuất hiện trong bảng Skills, nên chúng không thêm token ở đó cho tới khi bạn gọi.

Trên omp và Codex, cùng các thiết lập đó chặn việc tự gọi, nhưng mô tả có còn được nạp hay không thì chưa đo. Dùng cách so trước/sau ở trên. Xem [Runtime](runtimes.md#chỉ-chạy-khi-gọi-đích-danh) để biết mức bằng chứng.

## 4. Chạy cùng các bộ kit khác

qk không yêu cầu gỡ hay tắt thứ gì. Muốn cắt bớt thì đo, chuyển một skill sang chỉ chạy khi gọi đích danh, mở phiên mới rồi đo lại. Chỉ giữ thay đổi nếu phần chênh lệch đáng để mất khả năng tự gọi skill đó; nếu không thì hoàn tác.

Chỉnh sửa bên trong file của bộ kit khác có thể bị ghi đè khi bộ kit đó cập nhật, nên hãy đo lại sau mỗi lần cập nhật.
