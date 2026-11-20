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

`qk sync` đọc trạng thái PR bằng `gh` và in `Decision snapshots: N recorded; N unchanged; N failures.` (thoát 1 khi có lỗi). `qk brief` in một thẻ cho mỗi run. Thẻ của run không bị chặn hiện:

- dòng tiêu đề kết thúc bằng `RISK: <level> — <rule>; full: qk show --id <id>` (quy tắc dài quá 100 ký tự bị cắt);
- `Done`, `Evidence`, `Unchecked`, `History`;
- `Decision: human decision required; …`.

Thẻ của run bị chặn chỉ hiện dòng tiêu đề, rồi `Done`, `Next` và `History`. Thẻ của run dừng giữa chừng cũng vậy (xem [Khi có sự cố](#khi-có-sự-cố)).

Thẻ xếp theo high, medium, low; trong cùng mức, run dừng giữa chừng đứng trước, rồi tới run bị chặn. Quy tắc khớp đầu tiên quyết định mức, và nội dung quy tắc được in ra:

- **high:** `stopped at <stage> (runner gone)`, `blocked at <stage>: <reason>`, `<n> blocker/important findings remain` (finding nit không tính; run ghi trước khi sổ lưu mức độ hiện `<n> findings remain (severity unknown)` và tính mọi finding còn lại), `verify failed (<n> nonzero)`, `sensitive file <path>` (`+N more`). Nhạy cảm nghĩa là `.github/`, manifest và lockfile phụ thuộc (`package.json`, `*.lock`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `Gemfile`, `Dockerfile`, `requirements*.txt`, …), `*.tf`, `migrations/`, hoặc đường dẫn chứa `auth`, `secret`, `permission` hay `policy`.
- **medium:** `fix round used`, `<n> lines changed` (trên 300), `<n> files changed` (trên 10), `PR head differs from recorded commit`, `never synced`, `scope unknown`.
- **low:** `no rule matched`.

Các quy tắc không trao quyền duyệt. Brief bỏ qua run đã abort, run không bị chặn có PR đã merge hoặc đóng, và run chưa có PR trừ khi run bị chặn hoặc dừng giữa chừng. Khi không có gì để hiện, brief in `No open, unknown or blocked runs recorded.`

Thẻ của run bị chặn hiện `Next: qk run resume <id> after fixing the cause, or qk run abort <id>`. Xem nguyên nhân bằng `qk run status <id>`. `resume` chạy trong terminal của bạn, không trong drain. Nếu run bị chặn ở verifying, reviewing hoặc fixing, phần bạn tự sửa được kiểm và review lại (xem [Quyền](runner.md#quyền)). `qk run abort <id>` giữ lại worktree; xoá nó bằng `git worktree remove`.

### Quyết định ngay trong terminal

Khi cả stdin lẫn stdout là terminal, `qk brief` hỏi sau mỗi thẻ. Khi output được pipe hoặc chuyển hướng, nó chỉ in và không gọi mạng.

- Run không bị chặn: `[y] merge  [n] leave  [d] diff  [s] skip`. `y` merge bằng `gh`, và chỉ khi head của PR vẫn đúng commit mà run đã ghi: nó kiểm tài khoản `gh` đang active có quyền merge ở repo đó không (không có thì báo ngay, trước khi hỏi gì; thoát rồi chạy lại bằng `GH_TOKEN="$(gh auth token --user <account>)" qk brief`), đọc các cách merge repo cho phép, hỏi chọn cách nào khi có nhiều cách, và truyền `--match-head-commit`. Nếu không merge được, nó in `qk brief: not merged: <reason>` rồi hỏi lại. `d` in diff của PR rồi hỏi lại. `n` ghi lại rằng bạn để nguyên PR.
- Run bị chặn: `[a] abort later  [r] resume later  [s] skip`. Hai lựa chọn này chỉ ghi lại ý định; bạn tự chạy `qk run abort` hoặc `qk run resume`.
- Run dừng giữa chừng: `[a] abort later  [s] skip`. `a` chỉ ghi lại ý định.
- `s` không ghi gì. Hết input (Ctrl-D) thì dừng hỏi; các thẻ còn lại chỉ được in.

Mỗi lựa chọn được ghi vào sổ thành một decision với `source=user`, rồi in `Recorded <choice>: <id>`. Lựa chọn đã ghi không ẩn thẻ; PR đã merge rời khỏi brief sau lần `qk sync` kế tiếp.

Khi không có terminal, ví dụ khi một agent trong khung chat chạy lệnh thay bạn, ghi từng quyết định bằng `qk decide <run-id> merge|leave|abort-later|resume-later`. Lệnh chỉ nhận đúng các lựa chọn mà thẻ đó có, áp cùng các bước kiểm trước khi merge (head đúng commit đã ghi, quyền merge, `--match-head-commit`), và cần `--method` khi repo cho phép nhiều cách merge. Chỉ chạy lệnh này theo đúng lựa chọn người dùng đã nói, kể cả cách merge; agent không được tự chọn. Quyết định được ghi y như trong brief, nhưng với `via=decide` thay vì `via=brief`, và `elapsed_s` để trống vì không có thẻ nào được bấm giờ. `source=user` gán lựa chọn cho người dùng; nó không chứng minh ai đã gõ lệnh. Các agent do `qk-run` khởi động được dặn không bao giờ merge hay chạy `qk decide`.

## Khi có sự cố

- **Drain bị dừng giữa chừng** (Ctrl-C, đóng terminal, bị kill) để run đó kẹt ở bước đang chạy. `resume`, `approve` và `drain` đều bỏ qua nó. Khi run đang làm việc, runner giữ `run.lock` trong thư mục run và hệ điều hành nhả khoá khi tiến trình chết, nên `qk brief` hiện run đang ở bước làm việc mà khoá trống là `stopped at <stage> (runner gone)`, kèm `Next: qk run status <id>, then qk run abort <id>`. Khoá trống chỉ cho biết runner đã chết: agent mà runner khởi động chạy trong session riêng và có thể vẫn đang làm nốt lượt trong worktree, nên kiểm bằng `ps` trước khi abort. Chỉ `qk run abort <id>` đưa run ra. Abort để nguyên nhánh, nhánh đã push và PR nếu có.
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
