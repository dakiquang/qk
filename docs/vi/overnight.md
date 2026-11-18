# Chạy qua đêm

[English](../en/overnight.md) · [Mục lục](README.md) · [Runner](runner.md) · [Sổ bằng chứng](ledger.md)

Duyệt plan vào buổi tối, để [runner](runner.md) chạy lần lượt từng run qua đêm, và quyết định kết quả vào buổi sáng. Bạn cần `qk` trên `PATH` (xem [Cài từ bản clone](ledger.md#cài-từ-bản-clone)), checkout chính không còn thay đổi chưa commit, và macOS cho `caffeinate` và `--notify`. Thông báo của runner in cùng lệnh con dưới dạng `qk-run …`; `qk run …` là cùng một lệnh.

## Buổi tối

1. Khởi động từng việc. `start` in id của run dưới dạng `qk-run <id>`, rồi lập plan và dừng với `Plan ready: …`:
   ```bash
   qk run start "Thêm X. Xong khi <lệnh kiểm> pass." --repo <path>
   ```
2. Đọc `plan.md` trong thư mục run: mặc định `~/.local/state/qk-run/<id>/plan.md`, hoặc dưới `$QK_RUN_STATE_DIR`, hay `$XDG_STATE_HOME/qk-run`, khi có đặt. Sửa thẳng file, hoặc lập lại plan bằng `qk run revise <id> "<góp ý>"`.
3. Xếp hàng:
   ```bash
   qk run approve <id> --later
   ```
   `approve` đọc lại `plan.md`, từ chối plan không có khối `qk-verify`, đóng băng thành `approved-plan.md`, in các lệnh kiểm sẽ chạy và chuyển sang bước `queued`.
4. Lặp lại cho các việc khác. Run trong hàng đợi chạy theo thứ tự cũ nhất trước.

## Ban đêm

```bash
caffeinate -i qk run drain --until 07:00 --notify
```

- Mỗi lần một run, run xếp hàng sớm nhất trước. `drain` thứ hai thoát với `another drain is already running`.
- `--until 07:00` nghĩa là 07:00 kế tiếp sau thời điểm hiện tại. Hạn chỉ được kiểm trước khi bắt đầu một run: run đang chạy vẫn chạy xong, rồi drain in `Deadline reached; N queued runs left.` Run chưa bắt đầu vẫn nằm trong hàng đợi cho lần drain sau.
- `--notify` hiện một thông báo cho mỗi run bị chặn và một thông báo tổng kết. Thông báo lỗi chỉ in cảnh báo.
- Dòng cuối là `Drain: X done, Y blocked, Z left queued.` Mã thoát là 1 nếu có run bị chặn.

## Buổi sáng

```bash
qk sync
qk brief
```

`qk sync` đọc trạng thái PR bằng `gh` và in `Decision snapshots: N recorded; N unchanged; N failures.` (thoát 1 khi có lỗi). `qk brief` chạy offline và in một thẻ cho mỗi run. Thẻ của run không bị chặn hiện:

- dòng tiêu đề kết thúc bằng `RISK: <level> — <rule>`;
- `Done`, `Evidence`, `Unchecked`, `History`;
- `Decision: human decision required; …`.

Thẻ của run bị chặn chỉ hiện dòng tiêu đề, rồi `Done`, `Next` và `History`.

Thẻ xếp theo high, medium, low; trong cùng mức, run bị chặn đứng trước. Quy tắc khớp đầu tiên quyết định mức, và nội dung quy tắc được in ra:

- **high:** `blocked at <stage>: <reason>`, `<n> findings remain`, `verify failed (<n> nonzero)`, `sensitive file <path>` (`+N more`). Nhạy cảm nghĩa là `.github/`, manifest và lockfile phụ thuộc (`package.json`, `*.lock`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `Gemfile`, `Dockerfile`, `requirements*.txt`, …), `*.tf`, `migrations/`, hoặc đường dẫn chứa `auth`, `secret`, `permission` hay `policy`.
- **medium:** `fix round used`, `<n> lines changed` (trên 300), `<n> files changed` (trên 10), `PR head differs from recorded commit`, `never synced`, `scope unknown`.
- **low:** `no rule matched`.

Các quy tắc không trao quyền duyệt. Brief bỏ qua run đã abort, run không bị chặn có PR đã merge hoặc đóng, và run chưa có PR trừ khi run bị chặn. Khi không có gì để hiện, brief in `No open, unknown or blocked runs recorded.`

Thẻ của run bị chặn hiện `Next: qk run resume <id> after fixing the cause, or qk run abort <id>`. Xem nguyên nhân bằng `qk run status <id>`. `resume` chạy trong terminal của bạn, không trong drain. Nếu run bị chặn ở verifying, reviewing hoặc fixing, phần bạn tự sửa được kiểm và review lại (xem [Quyền](runner.md#quyền)). `qk run abort <id>` giữ lại worktree; xoá nó bằng `git worktree remove`.

## Khi có sự cố

- **Drain bị dừng giữa chừng** (Ctrl-C, đóng terminal, bị kill) để run đó kẹt ở bước đang chạy. `resume`, `approve` và `drain` đều bỏ qua nó, và nó không có trong `qk brief`. `qk run status <id>` hiện bước và các dòng log cuối; chỉ `qk run abort <id>` đưa nó ra. Abort để nguyên nhánh, nhánh đã push và PR nếu có.
- **Hết quota hoặc lỗi đăng nhập** làm run đó dừng ở `blocked`, và drain chuyển sang run kế tiếp, run này có thể bị chặn vì cùng lý do.
- **Hai việc cùng lúc:** drain không bao giờ chạy hai run trong hàng đợi cùng lúc, nhưng không chặn `start`, `approve` không có `--later`, hay `resume` mà bạn tự chạy ở terminal khác.
- **Máy ngủ:** máy ngủ thì agent và drain tạm dừng. Giữ `caffeinate -i` trước `drain`.

## Tài khoản publish

Tài khoản `gh` đang hoạt động phải có quyền push vào repo. Runner kiểm ở `start` và kiểm lại ngay trước khi push trong lúc drain; `gh pr create` cũng dùng tài khoản đó. `git push` dùng thông tin đăng nhập riêng của git, nên chúng cũng phải push được; với origin SSH, key quyết định, và bước kiểm không biết key thuộc tài khoản nào. Từ bản clone qk, kiểm mà không đổi gì:

```bash
python3 skills/qk-commit/scripts/qk_preflight.py identity --repo <path>
```

**Cách 1: đổi tài khoản đang hoạt động.** Chạy `gh auth switch -u <other-account>` trước `start`, giữ nguyên suốt lúc drain, rồi `gh auth switch -u <your-account>` sau đó. Cách này chỉ áp dụng cho `git push` khi git lấy thông tin đăng nhập github.com từ `gh auth git-credential`; kiểm bằng `git config --get-regexp '^credential'`. Việc đổi có tác dụng toàn cục, nên mọi terminal khác cũng thấy.

**Cách 2: chỉ một terminal, không đổi gì toàn cục.** `GH_TOKEN` được ưu tiên hơn đăng nhập `gh` đã lưu, còn các biến `GIT_CONFIG_*` thêm cấu hình git cho shell này và các tiến trình con. Helper rỗng xoá các credential helper khác của bạn cho github.com:

```bash
export GH_TOKEN="$(gh auth token --user <other-account>)"
export GIT_CONFIG_COUNT=2
export GIT_CONFIG_KEY_0=credential.https://github.com.helper GIT_CONFIG_VALUE_0=
export GIT_CONFIG_KEY_1=credential.https://github.com.helper GIT_CONFIG_VALUE_1='!gh auth git-credential'
```

Chạy `start`, `drain` và `qk sync` trong terminal đó. Agent khởi động từ đó thừa hưởng các biến này, và agent triển khai chạy ở chế độ ghi.
