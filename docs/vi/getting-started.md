# Bắt đầu

[English](../en/getting-started.md) · [Mục lục](README.md)

## 1. Cài đặt

qk là Markdown thuần: không build, không dependency runtime. Clone một lần rồi tạo symlink từng thư mục skill vào nơi runtime đọc. Mọi runtime dùng cùng nguồn; `git pull` cập nhật các link đó. Repo hiện riêng tư nên cần tài khoản GitHub có quyền đọc.

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

Một số runtime đọc nhiều thư mục. Cài cùng skill ở hai nơi có thể khiến liệt kê trùng; omp gộp link cùng trỏ về một thư mục. Nếu chưa chắc, kiểm danh sách skill của runtime. Mở phiên mới để runtime nhận skill.

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

```bash
git -C ~/src/qk pull
```

Link dùng phiên bản mới ở phiên tiếp theo. Đọc [changelog](../../CHANGELOG.md) trước khi cập nhật.

## 5. Gỡ

Chỉ xoá link đã xác minh trỏ tới clone qk của bạn, không xoá toàn bộ thư mục skill. Kiểm một link:

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

Kiểm tên folder/frontmatter, cấu hình gọi đích danh Claude Code/omp/Codex, link nội bộ và cặp docs EN/VI. Kiểm đường dẫn cá nhân và mẫu secret áp cho file text UTF-8 mọi hậu tố ngoài `.git`, trừ mẫu phát hiện của chính validator. `QK_DENYLIST` là file UTF-8 chứa term literal, mỗi dòng một term; khớp không phân biệt hoa thường theo biên ký tự chữ và áp cả cho validator. Không kiểm file binary, tên file hoặc lịch sử Git. Đây là kiểm tĩnh, không chứng nhận mọi runtime sẽ tuân thủ.
