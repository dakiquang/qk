# qk

[English](README.md)

Bộ skill nhỏ cho cách tôi làm việc thật: quyết định dựa trên bằng chứng, lập kế hoạch trước thay đổi lớn, triển khai có kiểm chứng, bàn giao giữa các phiên, và để con người quyết mọi thứ đi ra khỏi máy.

qk mở rộng Claude Code, Codex và omp, không thay thế chúng. Mỗi skill **được cấu hình để chỉ chạy khi gọi đích danh**, không phải vì yêu cầu có nhắc tới lập kế hoạch hay debug. Runtime vẫn giữ tool, plan mode, subagent, cấu hình model và quyền của nó.

> Dự án cá nhân, không liên quan công ty nào, không cam kết hỗ trợ.

## Skill

| Skill | Dùng để | Ghi gì |
|---|---|---|
| `qk/brainstorm` | So sánh hướng đi, đánh đổi, giả định; khuyến nghị một hướng | Mặc định không ghi |
| `qk/research` | Trả lời câu hỏi phục vụ quyết định bằng nguồn chính và thử nghiệm có đối chứng | Không, hoặc mục bằng chứng của plan |
| `qk/plan` | Tạo, audit hoặc sửa plan có nguồn, quyết định và tiêu chí xong | Chỉ file plan |
| `qk/cook` | Triển khai yêu cầu rõ hoặc plan đã duyệt, rồi kiểm chứng và tự review | File trong phạm vi; không commit, push, phát hành trừ khi được yêu cầu |
| `qk/debug` | Tìm nguyên nhân gốc bằng tái hiện và chuỗi bằng chứng | Mặc định không ghi |
| `qk/test` | Kiểm tra độc lập và báo kết quả thật | Không ghi |
| `qk/handoff` | Viết bàn giao cho phiên mới, hoặc nhận bàn giao và kiểm độ lệch | Chỉ file bàn giao |
| `qk/agent-coord` | Giao việc có giới hạn cho agent và model chỉ định, rồi kiểm kết quả | Worktree riêng của worker |
| `qk/release-notes` | Soạn nháp release notes và CHANGELOG từ commit và PR | Chỉ bản nháp; không tag, không phát hành |

Mỗi skill ghi rõ **kết quả, quyền và tiêu chí xong** ở đầu file. Skill không gọi lẫn nhau; khi có bước tiếp theo hợp lý, skill nêu lệnh để bạn tự gọi.

Review và chấm điểm pull request dùng skill đồng hành [pr-orchestrator](https://github.com/dakiquang/pr-orchestrator). Nó vẫn là dự án riêng; `qk/cook` và `qk/agent-coord` nhắc tới nó theo tên.

## Cách gọi

| Runtime | Ví dụ | Cơ chế chỉ chạy khi gọi |
|---|---|---|
| Claude Code | `/qk-plan` | `disable-model-invocation: true` |
| Codex | `$qk-plan` | `agents/openai.yaml` → `allow_implicit_invocation: false` |
| omp | `/skill:qk-plan` | `disable-model-invocation: true` |
| Qwen Code | chưa kiểm | chưa kiểm |

Orca chạy các agent này trong terminal của nó và thấy skill đã cài cho từng agent.

Các cấu hình này báo cho runtime không tự nạp skill; Claude Code ghi trong tài liệu rằng cấu hình của nó cũng giữ skill ngoài subagent. Runtime có tuân thủ thật hay không thì chưa được thử (xem Mức hỗ trợ). Chủ ý: qk không giành lấy yêu cầu mà bạn không chuyển cho nó.

## Cài đặt

Clone một lần, rồi tạo symlink từng thư mục skill vào thư mục skill của runtime bạn dùng. Symlink giữ mọi runtime trên cùng một nguồn; `git pull` cập nhật tất cả.

```bash
git clone https://github.com/dakiquang/qk ~/src/qk
dest=~/.claude/skills            # hoặc ~/.codex/skills, ~/.agents/skills, ~/.omp/agent/skills, ~/.qwen/skills
mkdir -p "$dest"
collision=0
for skill in ~/src/qk/skills/qk-*; do
  target="$dest/$(basename "$skill")"
  if [ -e "$target" ] || [ -L "$target" ]; then echo "already exists: $target"; collision=1; fi
done
if [ "$collision" = 0 ]; then
  for skill in ~/src/qk/skills/qk-*; do ln -s "$skill" "$dest/$(basename "$skill")"; done
fi
```

Script kiểm mọi đích trước và không tạo link nào nếu có đích đã tồn tại, nên skill hay thư mục có sẵn không bao giờ bị thay hoặc bị ghi vào. Mỗi runtime dùng một nơi cài; vài runtime đọc nhiều thư mục và sẽ liệt kê một skill hai lần nếu cài trùng. Gỡ skill bằng cách xoá symlink.

Mở phiên mới sau khi cài để runtime nhận skill.

## Mức hỗ trợ

Cấu trúc và cấu hình gọi được `scripts/validate.py` kiểm. Trên omp 18.15.0 đã kiểm trong project tạm: nhận đủ skill, cùng tồn tại với skill sẵn có. Gọi đích danh, không tự kích hoạt và cùng tồn tại với lệnh native chưa được thử trên runtime nào; kết quả sẽ ghi tại đây theo runtime và phiên bản.

## Kiểm tra

```bash
python3 scripts/validate.py
```

Kiểm tên thư mục và frontmatter, cấu hình chỉ chạy khi gọi cho Claude Code, omp và Codex, link nội bộ, đường dẫn cá nhân và chuỗi giống secret. Đặt `QK_DENYLIST` trỏ tới file các từ không được xuất hiện trong repo. CI chạy thêm gitleaks trên toàn lịch sử.

## Giấy phép

[MIT](LICENSE). Tác giả [Quang Dang](https://quangdk.com).
