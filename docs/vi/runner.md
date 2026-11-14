# qk-run: từ yêu cầu đến pull request

[English](../en/runner.md) · [Mục lục](README.md) · [Source](../../scripts/qk_run.py)

`qk-run` là runner chỉ chạy khi bạn gọi. Nó đưa một việc qua các skill qk trên Claude Code, Codex hoặc omp, dừng một lần để bạn duyệt plan, rồi chạy tiếp đến khi mở được pull request đã kiểm chứng — hoặc dừng ở `blocked` kèm lý do. Các skill vẫn không tự gọi nhau; chỉ runner nối chúng, và chỉ khi bạn khởi động.

## Cách dùng

```bash
python3 scripts/qk_run.py start "Thêm X. Xong khi <lệnh kiểm> pass." --repo <path>
python3 scripts/qk_run.py approve <id>            # sau khi đọc plan
python3 scripts/qk_run.py revise <id> "<góp ý>"   # lập lại plan
python3 scripts/qk_run.py status <id>
python3 scripts/qk_run.py resume <id>             # chạy lại bước bị chặn, giữ nguyên hiện trạng
python3 scripts/qk_run.py abort <id>
```

Cần Python 3.9+ cùng CLI `git` và `gh`. Mặc định: triển khai `omp:anthropic/claude-opus-5-5`, review `codex:` (model mặc định của Codex). Đổi bằng `--impl runtime:model` và `--review runtime:model`; runtime gồm `omp`, `claude`, `codex`. Người triển khai và người review phải khác họ model; spec omp cần model ghi rõ, nhận ra được họ (ví dụ `omp:anthropic/claude-opus-5-5`), nếu không `start` từ chối. Đặt `QK_RUN_OMP_PROFILE` để chạy omp với profile riêng. `--timeout` giới hạn mỗi lượt agent và mỗi lệnh kiểm (mặc định 1800 giây).

## Các bước

1. **preflight** — từ chối checkout chính còn thay đổi chưa commit (không stash), kiểm quyền push của tài khoản `gh` đang hoạt động với origin trên GitHub, tìm nhánh base, tạo worktree trên nhánh mới `qk/<slug>-<id>`.
2. **planning** — `qk/plan` chỉ đọc; runner lưu plan, plan phải có khối `qk-verify` chứa lệnh kiểm của repo.
3. **awaiting_approval** — cổng người duy nhất. Có thể sửa `plan.md` trước khi duyệt; `approve` đọc lại file, in các lệnh kiểm sẽ chạy và đóng băng thành `approved-plan.md`. Reviewer, vòng sửa và PR dùng bản đóng băng này; bản đó bị sửa thì run dừng.
4. **implementing** — `qk/cook` trong worktree.
5. **verifying** — runner tự chạy mọi lệnh `qk-verify`, xoá file do các lệnh đó tạo ra và chặn nếu chúng đổi nội dung khác của worktree (file đã track hoặc file mới).
6. **reviewing** — model khác họ review toàn bộ diff ở chế độ chỉ đọc, trả finding có cấu trúc.
7. **fixing** — tối đa một vòng cho lệnh kiểm lỗi hoặc finding blocker/important trên file đã đổi, rồi kiểm và review lại.
8. **publishing** — runner commit với tiêu đề của plan đã duyệt (không dòng tác giả AI). Runner thêm type theo quy ước (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`) và viết thường chữ cái đầu (từ viết tắt như `README` hay `CI` giữ nguyên) khi phần lớn trong 20 tiêu đề commit gần nhất không phải merge của nhánh base theo dạng `type(scope): subject`. Sau đó runner push nhánh và mở PR ready-for-review cùng tiêu đề đó, kèm lệnh kiểm, vấn đề đã xử lý trong vòng sửa, finding còn lại và plan đã duyệt. Runner kiểm tra lại quyền push ngay trước khi push.

Trạng thái và log nằm ngoài repo, tại `$XDG_STATE_HOME/qk-run/<id>/` (mặc định `~/.local/state/qk-run/`). Worktree được giữ lại sau khi chạy.

Khi agent chạy, runner in mỗi thao tác công cụ của nó thành một dòng (`read <path>`, `edit <path>`, `write <path>`, `run <lệnh>`, kèm ` -> exit <mã>` khi runtime báo) và in `still running (<n>s, last: <thao tác>)` sau mỗi 60 giây không có sự kiện. Sự kiện thô của từng lượt được ghi vào `<stage>-<ts>.events.jsonl` cạnh `<stage>-<ts>.out.md`, còn log của runner là `run.log`, cả hai nằm trong thư mục run; `status` in đường dẫn thư mục run và 10 dòng log cuối. Khi hết `--timeout`, runner gửi SIGTERM tới process group của agent, SIGKILL sau 10 giây, và run dừng ở `blocked`.

## Quyền

- Agent chỉ sửa file trong worktree. Chỉ runner commit, push và mở PR.
- Runner chặn khi worktree rời nhánh của run hoặc HEAD lệch khỏi commit của runner, khi agent đổi nhánh, HEAD hoặc file của checkout chính, hoặc khi agent chỉ đọc làm đổi nội dung worktree. Các kiểm này vẫn chạy khi lời gọi agent lỗi hoặc timeout.
- Nhánh, HEAD và nội dung kỳ vọng của worktree được lưu lại, không chụp lại khi resume: sau khi bị chặn vì các lý do trên, `resume` vẫn bị chặn cho tới khi worktree được khôi phục, nên không thể publish commit hay chỉnh sửa vi phạm bằng cách resume. Tự sửa worktree sau khi bị chặn cũng vẫn bị chặn; muốn đổi nội dung thì `abort` rồi chạy run mới. Checkout chính chỉ được so trong từng lượt agent, nên đừng đụng vào nó khi agent đang chạy; thay đổi của bạn giữa các lượt không làm run dừng.
- Không merge, release, tag, deploy, force-push, xoá nhánh hay đổi model. Hết quota, lỗi đăng nhập hoặc thiếu model thì dừng ở `blocked`.
- `resume` sau khi publish không commit lại, push lại hay mở PR thứ hai.

## Giới hạn

- Worktree không phải sandbox. Agent triển khai chạy ở chế độ ghi của runtime (`claude --permission-mode acceptEdits` cho phép Bash, `codex exec --sandbox workspace-write`, `omp --approval-mode yolo`), nên vẫn có thể chạm file và mạng ngoài repo.
- Thành công được định nghĩa bằng lệnh `qk-verify` của plan và một lần review chéo model; lệnh kiểm yếu thì bằng chứng yếu.
- Commit và PR lấy tiêu đề của plan đã duyệt; phần thân PR chứa toàn bộ plan đã duyệt. Với repo theo Conventional Commits, type lấy từ từ đầu tiên của tiêu đề plan (`fix`, `docs`, `test`, `refactor` và các biến thể), còn lại mặc định là `feat`; tiêu đề plan đã đúng quy ước thì giữ nguyên; tiền tố `<từ>: ` không theo quy ước (tên dự án, cả tiền tố ticket như `ABC-123: ` hay `Fix: ` viết hoa) bị bỏ trước khi thêm type; commit merge không được tính. Tiêu đề dài hơn 72 ký tự được cắt ở ranh giới từ. Các quy ước khác (scope, quy tắc viết hoa khác) không được nhận diện, nên hãy sửa tiêu đề plan trước khi `approve` hoặc chỉnh tiêu đề khi merge.
- Mỗi lần chạy một việc; không có queue, daemon hay chạy song song.

## Bằng chứng

Hành vi của runner được phủ bởi [`tests/test_qk_run.py`](../../tests/test_qk_run.py), chạy runner với agent giả lập trên repo Git thật. Các lần chạy thật đầu-cuối được ghi ở [Bằng chứng kiểm thử](evidence.md#runner-qk-run).
