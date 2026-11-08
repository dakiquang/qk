# qk-run: từ yêu cầu đến pull request

[English](../en/runner.md) · [Mục lục](README.md) · [Source](../../scripts/qk_run.py)

`qk-run` là runner chỉ chạy khi bạn gọi. Nó đưa một việc qua các skill qk trên Claude Code, Codex hoặc omp, dừng một lần để bạn duyệt plan, rồi chạy tiếp đến khi mở được pull request đã kiểm chứng — hoặc dừng ở `blocked` kèm lý do. Các skill vẫn không tự gọi nhau; chỉ runner nối chúng, và chỉ khi bạn khởi động.

## Cách dùng

```bash
python3 scripts/qk_run.py start "Thêm X. Xong khi <lệnh kiểm> pass." --repo <path>
python3 scripts/qk_run.py approve <id>            # sau khi đọc plan
python3 scripts/qk_run.py revise <id> "<góp ý>"   # lập lại plan
python3 scripts/qk_run.py status <id>
python3 scripts/qk_run.py resume <id>             # chạy lại bước bị chặn
python3 scripts/qk_run.py abort <id>
```

Mặc định: triển khai `omp:anthropic/claude-opus-5-5`, review `codex:` (model mặc định của Codex). Đổi bằng `--impl runtime:model` và `--review runtime:model`; runtime gồm `omp`, `claude`, `codex`. Người triển khai và người review phải khác họ model. Đặt `QK_RUN_OMP_PROFILE` để chạy omp với profile riêng. `--timeout` giới hạn mỗi lượt agent và mỗi lệnh kiểm (mặc định 1800 giây).

## Các bước

1. **preflight** — từ chối checkout chính còn thay đổi chưa commit (không stash), kiểm `gh auth`, tìm nhánh base, tạo worktree trên nhánh mới `qk/<slug>-<id>`.
2. **planning** — `qk/plan` chỉ đọc; runner lưu plan, plan phải có khối `qk-verify` chứa lệnh kiểm của repo.
3. **awaiting_approval** — cổng người duy nhất.
4. **implementing** — `qk/cook` trong worktree.
5. **verifying** — runner tự chạy mọi lệnh `qk-verify`; xoá file do các lệnh đó tạo ra; chặn nếu chúng sửa file đã track.
6. **reviewing** — model khác họ review toàn bộ diff ở chế độ chỉ đọc, trả finding có cấu trúc.
7. **fixing** — tối đa một vòng cho lệnh kiểm lỗi hoặc finding blocker/important trên file đã đổi, rồi kiểm và review lại.
8. **publishing** — runner commit (tiêu đề plan, không dòng tác giả AI), push nhánh và mở PR ready-for-review kèm lệnh kiểm, finding còn lại và plan.

Trạng thái và log nằm ngoài repo, tại `$XDG_STATE_HOME/qk-run/<id>/` (mặc định `~/.local/state/qk-run/`). Worktree được giữ lại sau khi chạy.

## Quyền

- Agent chỉ sửa file trong worktree. Chỉ runner commit, push và mở PR.
- Runner chặn khi agent đổi `HEAD`, đụng checkout chính, hoặc agent chỉ đọc làm đổi nội dung worktree.
- Không merge, release, tag, deploy, force-push, xoá nhánh hay đổi model. Hết quota, lỗi đăng nhập hoặc thiếu model thì dừng ở `blocked`.
- `resume` sau khi publish không commit lại, push lại hay mở PR thứ hai.

## Giới hạn

- Worktree không phải sandbox. Agent triển khai chạy ở chế độ ghi của runtime (`claude --permission-mode acceptEdits` cho phép Bash, `codex exec --sandbox workspace-write`, `omp --approval-mode yolo`), nên vẫn có thể chạm file và mạng ngoài repo.
- Thành công được định nghĩa bằng lệnh `qk-verify` của plan và một lần review chéo model; lệnh kiểm yếu thì bằng chứng yếu.
- Mỗi lần chạy một việc; không có queue, daemon hay chạy song song.

## Đã kiểm

Ngày 08/11/2026: 16 unit test với agent giả lập và repo Git thật phủ mọi chuyển trạng thái, vòng sửa duy nhất, chặn commit của agent, vi phạm chỉ đọc, checkout bẩn, file sinh ra khi kiểm và resume sau khi lệnh tạo PR lỗi. Chạy thật đầu-cuối trên một repo GitHub private tạm đã mở PR ready-for-review chỉ chứa đúng file dự kiến với từng runtime triển khai: omp (Opus 5.5) do Codex review, Claude Code (Sonnet) do Codex review, và Codex do omp (Opus 5.5) review. Đây là các lần chạy đơn lẻ, không phải chứng nhận.
