# Bắt đầu

[English](../en/getting-started.md) · [Mục lục](README.md)

## 1. Cài đặt

qk là Markdown thuần cùng hai script Python nhỏ; không có gì phải build. Bạn cần ít nhất một runtime được hỗ trợ. Script mà `qk/commit` và `qk/prefs` dùng cần Python 3.9 trở lên; bước kiểm account trước khi push còn cần GitHub CLI `gh`.

### Bằng `npx skills` (khuyên dùng)

[`npx skills`](https://github.com/vercel-labs/skills) chép các thư mục skill vào thư mục skill của từng runtime. Lệnh này cần Node.js.

```bash
npx skills add dakiquang/qk -g -a claude-code codex qwen-code -y
```

- `-g` cài cho tài khoản của bạn thay vì một project; `-a` chọn runtime; `-y` bỏ qua câu hỏi.
- Khi chọn nhiều runtime, file nằm một chỗ ở `~/.agents/skills`, các runtime còn lại nhận symlink tới đó. Bản của Codex chính là `~/.agents/skills`, thư mục skill của người dùng theo tài liệu Codex.
- **omp** không có đích riêng. Tài liệu omp liệt kê `~/.agents/skills` và `~/.claude/skills` trong số thư mục nó đọc, nên cài cho Codex hoặc Claude Code là omp cũng dùng được.
- Nếu có đặt `CLAUDE_CONFIG_DIR`, bản cho Claude Code nằm ở `$CLAUDE_CONFIG_DIR/skills` thay vì `~/.claude/skills`.
- Trên Claude Code, skill giữ tên gốc, nên bạn gọi `/qk-plan`, không phải `/qk:qk-plan`.
- Nếu thư mục skill đã có skill qk cùng tên, ví dụ link của bản cài thủ công, `npx skills` sẽ thay nó. Khi chuyển từ cài thủ công, gỡ các link cũ trước (xem [Gỡ](#5-gỡ)) để không runtime nào còn giữ bản cũ.

Để cố định ở một bản phát hành, thêm tag sau dấu `#` (từ `v0.3.0` trở đi bản phát hành mới có layout mà cách này cần):

```bash
npx skills add 'dakiquang/qk#v0.3.0' -g -a claude-code codex qwen-code -y
```

`dakiquang/qk@<tên>` không chọn phiên bản: `npx skills` hiểu phần sau `@` là tên skill.

### Cài thủ công (clone và link)

Dùng cách này khi bạn muốn chạy [`qk-run`](runner.md) hay validator, sửa skill, hoặc không có Node.js. Clone một lần rồi tạo symlink từng thư mục skill vào nơi runtime đọc; `git pull` sẽ cập nhật mọi runtime.

```bash
(
  git clone https://github.com/dakiquang/qk ~/src/qk || exit 1
  dest=~/.claude/skills          # lặp lại cho thư mục runtime ở bảng dưới
  set -- ~/src/qk/skills/qk-*
  for skill do
    [ -f "$skill/SKILL.md" ] || { echo "invalid or missing skill: $skill" >&2; exit 1; }
    target="$dest/$(basename "$skill")"
    if [ -e "$target" ] || [ -L "$target" ]; then
      echo "already exists: $target" >&2
      exit 1
    fi
  done
  mkdir -p "$dest" || exit 1
  for skill do
    ln -s "$skill" "$dest/$(basename "$skill")" || exit 1
  done
)
```

Khối lệnh chạy trong subshell: clone lỗi hoặc nguồn skill thiếu/không hợp lệ sẽ dừng mà không thoát shell của bạn. Script kiểm mọi skill và đích trước khi tạo link, không tạo link nếu có đích đã tồn tại. Chạy khi không có tiến trình khác cài skill vào cùng thư mục; đây không phải installer xử lý đồng thời hoặc rollback.

| Runtime | Thư mục skill |
|---|---|
| Claude Code | `~/.claude/skills` |
| Codex | `~/.codex/skills` |
| omp | `~/.agents/skills` hoặc `~/.omp/agent/skills` |
| Qwen Code | `~/.qwen/skills` |
| Orca | Không cài riêng; thấy skill của agent nó chạy |

Một số runtime đọc nhiều thư mục. Cài cùng skill ở hai nơi có thể khiến liệt kê trùng; omp gộp link cùng trỏ về một thư mục. Nếu chưa chắc, kiểm danh sách skill của runtime.

Muốn thử bản đang sửa trong clone theo layout của `npx skills`, cài từ đường dẫn của clone: `npx skills add ~/src/qk -g -a claude-code -y`. Bản cài từ đường dẫn local là bản chép, nên chạy lại lệnh sau mỗi lần sửa.

Mở phiên mới để runtime nhận skill.

## 2. Gọi skill

| Runtime | Cú pháp | Ví dụ |
|---|---|---|
| Claude Code | `/qk-<name>` | `/qk-plan thêm health endpoint` |
| Codex | `$qk-<name>` | `$qk-plan thêm health endpoint` |
| omp | `/skill:qk-<name>` | `/skill:qk-plan thêm health endpoint` |

Trong docs, `qk/plan` là tên luồng công việc, không phải cú pháp gõ nguyên văn.

qk được cấu hình để chỉ chạy khi gọi đích danh, không tự nạp chỉ vì có từ lập kế hoạch/debug/review. Xem [Runtime](runtimes.md) để phân biệt cơ chế, kết quả quan sát và runtime chưa kiểm.

## 3. Lần chạy đầu

Thử skill chỉ đọc trong một repo:

```text
/qk-brainstorm App nên đọc cấu hình từ biến môi trường hay file TOML?
```

Kỳ vọng: một câu nêu vấn đề, bảng hướng đi với lợi/hại, giả định, khuyến nghị và quyết định dành cho bạn. Không ghi file. Sau đó thử vòng plan → cook với việc nhỏ; xem [Quy trình](workflows.md).

Tuỳ chọn: [hook ghi nhận sở thích](preference-hook.md) biến câu "từ nay…" thành đề xuất để bạn duyệt bằng `qk/prefs`. Bật tay, riêng biệt.

## 4. Cập nhật

Với `npx skills`:

```bash
npx skills check
```

```bash
npx skills update -g -y
```

Bản cài cố định bằng `#<tag>` sẽ đứng yên ở tag đó; muốn lên bản mới thì cài lại với tag mới hơn. Bản cài từ đường dẫn local không kiểm hay cập nhật được; chạy lại đúng lệnh `npx skills add <đường dẫn>`.

Với bản cài thủ công:

```bash
git -C ~/src/qk pull
```

Link dùng phiên bản mới ở phiên tiếp theo. Đọc [changelog](../../CHANGELOG.md) trước khi cập nhật.

Link của bản cài thủ công trỏ tới clone, nên phiên bản đang checkout sẽ có hiệu lực trên mọi runtime ở phiên tiếp theo. Để cố định ở một bản phát hành, checkout tag của bản đó (danh sách bản phát hành nằm trong [changelog](../../CHANGELOG.md)):

```bash
git -C ~/src/qk fetch --tags
```

```bash
git -C ~/src/qk checkout v0.3.0
```

Để trở lại bản mới nhất trên `main`:

```bash
git -C ~/src/qk checkout main
```

```bash
git -C ~/src/qk pull
```

## 5. Gỡ

Với `npx skills`, gỡ các skill qk theo tên:

```bash
npx skills remove -g -y qk-agent-coord qk-brainstorm qk-commit qk-cook qk-debug qk-dogfood qk-handoff qk-plan qk-prefs qk-release-notes qk-research qk-test
```

Với bản cài thủ công, chỉ xoá link đã xác minh trỏ tới clone qk của bạn, không xoá toàn bộ thư mục skill. Kiểm một link:

```bash
readlink ~/.claude/skills/qk-plan
```

Nếu output là thư mục `skills/qk-plan` trong clone qk của bạn thì xoá link đó:

```bash
rm ~/.claude/skills/qk-plan
```

Lặp lại cho từng link thuộc bản cài của bạn. Không xoá link của bản cài khác hoặc thư mục thật. Chỉ xoá `~/src/qk` sau khi gỡ link và giữ lại mọi thay đổi cục bộ cần thiết.

## 6. Kiểm bộ kit

Từ thư mục gốc clone:

```bash
python3 scripts/validate.py
```

Kiểm tên folder/frontmatter, cấu hình gọi đích danh Claude Code/omp/Codex, link nội bộ và cặp docs EN/VI. Kiểm đường dẫn cá nhân và mẫu secret áp cho file text UTF-8 mọi hậu tố ngoài `.git`, trừ mẫu phát hiện của chính validator. `QK_DENYLIST` là file UTF-8 chứa term literal, mỗi dòng một term; khớp không phân biệt hoa thường theo biên ký tự chữ và áp cả cho validator. Không kiểm file binary, tên file hoặc lịch sử Git. Trên CI, gitleaks quét dải commit của từng sự kiện push hoặc pull request, không quét toàn bộ lịch sử. Đây là kiểm tĩnh, không chứng nhận mọi runtime sẽ tuân thủ.
