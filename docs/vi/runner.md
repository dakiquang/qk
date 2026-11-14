# qk-run: từ yêu cầu đến pull request

[English](../en/runner.md) · [Mục lục](README.md) · [Source](../../scripts/qk_run.py)

`qk-run` là runner chỉ chạy khi bạn gọi. Nó đưa một việc qua các skill qk trên Claude Code, Codex hoặc omp, dừng một lần để bạn duyệt plan, rồi chạy tiếp đến khi mở được pull request đã kiểm chứng — hoặc dừng ở `blocked` kèm lý do. Các skill vẫn không tự gọi nhau; chỉ runner nối chúng, và chỉ khi bạn khởi động.

## Cách dùng

```bash
python3 scripts/qk_run.py start "Thêm X. Xong khi <lệnh kiểm> pass." --repo <path>
python3 scripts/qk_run.py approve <id>            # sau khi đọc plan
python3 scripts/qk_run.py revise <id> "<góp ý>"   # lập lại plan
python3 scripts/qk_run.py status <id>
python3 scripts/qk_run.py resume <id>             # chạy lại bước bị chặn, hoặc kiểm phần bạn tự sửa
python3 scripts/qk_run.py abort <id>
```

Cần Python 3.9+ cùng CLI `git` và `gh`. Mặc định: triển khai `omp:anthropic/claude-opus-5-5`, review `codex:` (model mặc định của Codex). Đổi bằng `--impl runtime:model` và `--review runtime:model`; runtime gồm `omp`, `claude`, `codex`. Người triển khai và người review phải khác họ model; spec omp cần model ghi rõ, nhận ra được họ (ví dụ `omp:anthropic/claude-opus-5-5`), nếu không `start` từ chối. Đặt `QK_RUN_OMP_PROFILE` để chạy omp với profile riêng. `--timeout` giới hạn mỗi lượt agent và mỗi lệnh kiểm (mặc định 1800 giây). `--read-only-mcp NAME` (lặp được, chỉ Claude và omp) cho bước chỉ đọc gọi MCP server `NAME`; xem mục [Cô lập](#cô-lập). `start` từ chối cờ này khi Codex chạy bước lập plan (`--impl`) hoặc review (`--review`).

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

Khi agent chạy, runner in mỗi thao tác công cụ của nó thành một dòng (`read <path>`, `edit <path>`, `write <path>`, `run <lệnh>`, kèm ` -> exit <mã>` khi runtime báo) và in `still running (<n>s, last: <thao tác>)` sau mỗi 60 giây không có sự kiện. Lời gọi MCP hiện thành `mcp <định danh>` với định danh công cụ đầy đủ của runtime (ví dụ `mcp mcp__aws_mcp_aws_run_script`), còn các thiết bị runtime khác của omp hiện thành `tool <tên>` (ví dụ `tool report_issue`), không bao giờ là `write xd://...`. Khi luồng sự kiện của agent kết thúc, runner ghi lượng token thành `tokens in=<n> cached=<n> out=<n>`, thêm ` cost=$<x>` khi runtime báo; `in` gồm cả token cache. Cùng số liệu đó được ghi vào `state.json` dưới `usage`, mỗi bước một danh sách kèm spec của agent. Chỉ so số liệu trong cùng một runtime: mỗi runtime tính cache một kiểu. Sự kiện thô của từng lượt được ghi vào `<stage>-<ts>-<id>.events.jsonl` cạnh `<stage>-<ts>-<id>.out.md`, còn log của runner là `run.log`, cả hai nằm trong thư mục run; `status` in đường dẫn thư mục run và 10 dòng log cuối. Khi hết `--timeout`, runner gửi SIGTERM tới process group của agent, SIGKILL sau 10 giây, và run dừng ở `blocked`.

## Cô lập

Agent không nạp các skill bạn cài toàn cục; runner vẫn chỉ cho agent skill qk cần dùng bằng đường dẫn. Bước chỉ đọc (lập plan và review) còn chạy không có MCP:

- **Claude**: mọi bước có `--disable-slash-commands`. Bước chỉ đọc có thêm `--strict-mcp-config` không kèm config, nên không MCP server nào khởi động; `--read-only-mcp` bỏ cờ này. Bước ghi giữ cấu hình MCP của bạn.
- **omp**: mọi bước có `--no-skills --no-extensions --no-rules`; file ngữ cảnh của repo như `AGENTS.md` vẫn được nạp. omp không tắt trước được MCP, nên chốt chặn bên dưới dừng nó.
- **Codex**: mỗi run có một home riêng, `<thư mục run>/codex-home`, tạo ở lượt Codex đầu tiên và dùng lại về sau. Codex chạy với `HOME=<thư mục run>/codex-home` và `CODEX_HOME=<thư mục run>/codex-home/.codex`. `config.toml` trong đó chỉ giữ các dòng `model` và `model_reasoning_effort` ở cấp cao nhất của cấu hình thật (`$CODEX_HOME`, mặc định `~/.codex`) và tắt plugin, plugin từ xa và apps (nếu không, home mới sẽ tải các plugin được tuyển chọn của tài khoản cùng skill của chúng), còn `auth.json` là symlink tới file thật, nên Codex vẫn đăng nhập nhưng không thấy skill hay MCP server của người dùng. `UV_CACHE_DIR` và `UV_PYTHON_INSTALL_DIR` trỏ về chỗ quen thuộc của uv trong home thật, trừ khi bạn đã đặt chúng.

Chốt chặn bước chỉ đọc: ở bước chỉ đọc, lời gọi công cụ đầu tiên có tên chứa `mcp__` hoặc bắt đầu bằng `xd://` hay `mcp://`, hoặc có đối số chỉ nơi đến (`path`, `file_path` hay `uri`) bắt đầu bằng `xd://` hay `mcp://`, làm runner dừng process group của agent và chặn run với `read-only stage called <thao tác>`, ví dụ `read-only stage called mcp mcp__aws_mcp_aws_run_script`. Công cụ của server ghi trong `--read-only-mcp NAME` được cho qua: định danh công cụ, khi mọi ký tự không phải chữ hay số được đọc là `_`, phải bắt đầu bằng `mcp__<NAME>_`. `xd://report_issue` và tài nguyên `mcp://` không bao giờ được cho qua. Các đối số khác, như mẫu tìm kiếm, không tính; số token của lượt bị dừng vẫn được ghi vào log và `state.json`. `start` từ chối giá trị `--read-only-mcp` rỗng.

## Quyền

- Agent chỉ sửa file trong worktree. Chỉ runner commit, push và mở PR.
- Runner chặn khi worktree rời nhánh của run hoặc HEAD lệch khỏi commit của runner, khi agent đổi nhánh, HEAD hoặc file của checkout chính, hoặc khi agent chỉ đọc làm đổi nội dung worktree. Các kiểm này vẫn chạy khi lời gọi agent lỗi hoặc timeout.
- Nhánh, HEAD và nội dung kỳ vọng của worktree được lưu lại, không chụp lại khi resume: sau khi bị chặn vì các lý do trên, `resume` vẫn bị chặn cho tới khi worktree được khôi phục, nên không thể publish commit hay chỉnh sửa vi phạm bằng cách resume. Checkout chính chỉ được so trong từng lượt agent, nên đừng đụng vào nó khi agent đang chạy; thay đổi của bạn giữa các lượt không làm run dừng.
- Tự sửa tay: khi run bị chặn ở `verifying`, `reviewing` hoặc `fixing`, runner ghi lại worktree đúng lúc bị chặn. Nếu sau đó bạn sửa file rồi `resume`, runner ghi `manual changes recorded: <file>` vào log, lấy worktree của bạn làm bản triển khai mới và chạy tiếp từ `verifying`, nên phần bạn sửa được kiểm và review lại. Việc này không đặt lại vòng sửa duy nhất. Chỉ áp dụng khi bước bị chặn để worktree đúng như đã ghi, hoặc bước đó là `fixing`. Nếu agent chỉ đọc hay lệnh kiểm đã đổi worktree, phần bạn sửa thêm không được nhận và run vẫn bị chặn cho tới khi worktree được khôi phục.
- Không merge, release, tag, deploy, force-push, xoá nhánh hay đổi model. Hết quota, lỗi đăng nhập hoặc thiếu model thì dừng ở `blocked`.
- `resume` sau khi publish không commit lại, push lại hay mở PR thứ hai.

## Giới hạn

- Worktree không phải sandbox. Agent triển khai chạy ở chế độ ghi của runtime (`claude --permission-mode acceptEdits` cho phép Bash, `codex exec --sandbox workspace-write`, `omp --approval-mode yolo`), nên vẫn có thể chạm file và mạng ngoài repo.
- Thành công được định nghĩa bằng lệnh `qk-verify` của plan và một lần review chéo model; lệnh kiểm yếu thì bằng chứng yếu.
- Commit và PR lấy tiêu đề của plan đã duyệt; phần thân PR chứa toàn bộ plan đã duyệt. Với repo theo Conventional Commits, type lấy từ từ đầu tiên của tiêu đề plan (`fix`, `docs`, `test`, `refactor` và các biến thể), còn lại mặc định là `feat`; tiêu đề plan đã đúng quy ước thì giữ nguyên; tiền tố `<từ>: ` không theo quy ước (tên dự án, cả tiền tố ticket như `ABC-123: ` hay `Fix: ` viết hoa) bị bỏ trước khi thêm type; commit merge không được tính. Tiêu đề dài hơn 72 ký tự được cắt ở ranh giới từ. Các quy ước khác (scope, quy tắc viết hoa khác) không được nhận diện, nên hãy sửa tiêu đề plan trước khi `approve` hoặc chỉnh tiêu đề khi merge.
- Mỗi lần chạy một việc; không có queue, daemon hay chạy song song.
- MCP của omp chỉ bị dừng sau lần gọi đầu tiên ở bước chỉ đọc: lần gọi đó đã chạy xong khi chốt chặn dừng agent.
- `--read-only-mcp` khớp theo tiền tố, nên `aws` cũng cho qua `aws-mcp`; hãy ghi đủ tên server.
- Trong home riêng của Codex, công cụ mà Codex chạy không thấy `~/.gitconfig`, đăng nhập `gh` hay cấu hình khác trong thư mục home của bạn.

## Bằng chứng

Hành vi của runner được phủ bởi [`tests/test_qk_run.py`](../../tests/test_qk_run.py), chạy runner với agent giả lập trên repo Git thật. Các lần chạy thật đầu-cuối được ghi ở [Bằng chứng kiểm thử](evidence.md#runner-qk-run).
