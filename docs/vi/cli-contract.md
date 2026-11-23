# Hợp đồng CLI cho công cụ bên ngoài

[English](../en/cli-contract.md) · [Mục lục tài liệu](README.md) · [CLI](../../scripts/qk.py) · [Test hợp đồng](../../tests/test_contract_v1.py)

Một phần nhỏ của CLI `qk` là hợp đồng có phiên bản mà công cụ ngoài repo này được phép dựa vào: chạy một lượt agent có cô lập, ghi một run do chính công cụ đó dừng, và tự đo trên bộ bài eval của qk. Mọi phần khác của qk có thể đổi mà không báo trước. qk không biết ai gọi nó; bên gọi chỉ tự khai tên ở chỗ nó ghi vào sổ.

Mỗi lệnh trong hợp đồng làm một việc rồi kết thúc. Không lệnh nào gọi lệnh khác theo trình tự hay giữ trạng thái nhiều bước, và không lệnh nào commit, push, mở pull request hay merge. Điều phối là việc của bên gọi.

## Luật chung

- Phiên bản hợp đồng: `qk contract --json` in ra. Trang này mô tả phiên bản **1**.
- Đầu ra cho máy là một object JSON trên stdout khi có `--json`. Tiến độ và thông báo cho người đi ra stderr.
- JSON của các lệnh mới có `"contract": 1`. `qk show --json` và `qk lesson list --json` giữ nguyên đầu ra cũ.
- Mã thoát: `0` xong; `2` bị chặn, hoặc đầu vào bị từ chối (không chạy gì, không ghi gì); `1` lỗi khác.
- Khoá qk theo tag và commit, và gọi `qk contract --json` lúc khởi động để kiểm phiên bản và danh sách lệnh.

## Các lệnh

| Lệnh | Dùng để |
|---|---|
| `qk contract [--json]` | Phiên bản hợp đồng, phiên bản qk và các lệnh hợp đồng có trong bản này |
| `qk show --json [--kind K] [--id ID] [--repo R] [--since 7d]` | Đọc bản ghi trong sổ (trường `v`, `id`, `kind`, `at`, `source`, `recorded_by`, `repo`, `task_kind`, `refs`, `data`) |
| `qk lesson list --json` | Đọc trạng thái mới nhất của từng lesson |
| `qk agent run …` | Một lượt agent không tương tác |
| `qk agent family SPEC [--json]` | Họ model của một spec `runtime:model` |
| `qk log run …` | Ghi một run do công cụ khác dừng |
| `qk eval prepare …`, `qk eval grade …` | Dựng và chấm một bài eval mà không chạy agent |

`qk brief` và `qk decide` dành cho người quyết; công cụ không gọi chúng.

### `qk agent run`

```text
qk agent run --spec RUNTIME:MODEL --cwd DIR (--write | --read-only)
             [--add-dir DIR]... [--timeout GIÂY] [--read-only-mcp NAME]...
             [--no-result-contract] [--no-git-rules]
             [--lessons plan|impl|review [--repo NAME]]
             [--events FILE] [--json]   < prompt
```

- Prompt đọc từ stdin. qk nối thêm hợp đồng kết quả (khối `qk-result`), và với `--write` thì nối thêm luật không chạm git và luật dọn file; hai cờ `--no-…` tắt việc nối. `--lessons` nối các lesson đang bật và đã đo cho giai đoạn đó.
- Cô lập giống runner: không nạp skill của người dùng; lượt `--read-only` không có MCP trừ server nêu trong `--read-only-mcp`, gọi server khác thì lượt dừng với `blocked`.
- Mỗi lượt có thư mục tạm riêng (home riêng của Codex, file câu trả lời cuối), bị xoá khi lượt kết thúc, nên hai lượt chạy cùng lúc không dùng chung gì. `--cwd` và `--add-dir` được đổi thành đường dẫn tuyệt đối trước.
- SIGTERM dừng nhóm tiến trình của agent, xoá thư mục tạm và báo `blocked` với mã thoát 2.
- Lệnh không chạm git. Bên gọi tự kiểm cây làm việc sau lượt chạy.

Đầu ra:

```json
{"contract": 1, "status": "done", "reason": "", "family": "anthropic", "spec": "claude:",
 "result": {"status": "done", "summary": "…", "files": [], "evidence": [], "reason": "", "findings": []},
 "text": "…", "usage": {"input": 15, "cached": 4, "output": 7}, "lessons": [], "events": null, "seconds": 12}
```

`status` là `done`, `blocked` hoặc `needs_input`. Thiếu runtime, quá giờ, thoát mã khác 0 và vi phạm cô lập đều là `blocked` kèm `reason`. `result` là `null` khi tắt hợp đồng kết quả hoặc câu trả lời không có khối hợp lệ. `usage` là `null` khi runtime không báo token, và có thể thiếu `cost_usd` (Codex không báo).

### `qk agent family SPEC`

In họ model (`anthropic`, `openai`, `google`, `xai`) theo đúng luật qk-run dùng để tách người làm và người kiểm. Với `--json`: `{"contract": 1, "spec": "…", "family": "…"}`. Không xác định được họ thì thoát 2.

### `qk log run`

```text
qk log run --producer "TÊN PHIÊN-BẢN" --state-dir DIR [--json]   < state.json
```

Ghi một run đã dừng và các finding của nó qua cùng phép chiếu qk-run dùng, nên run hiện trong `qk show`, `qk stats` và `qk brief`. Đầu vào trên stdin:

| Trường | Bắt buộc | Ghi chú |
|---|---|---|
| `id` | có | Id run của bên gọi |
| `stage` | có | `done`, `blocked` hoặc `aborted` |
| `repo` | có | Đường dẫn tuyệt đối của repository; sổ lưu tên thư mục cuối, và `qk brief` chạy `gh` từ đó |
| `task`, `task_kind` | không | `task` bị cắt còn 120 ký tự |
| `impl`, `review` | không | Nhãn văn bản; nhiều model thì nối bằng dấu phẩy |
| `commit`, `pr_url` | không | `qk brief` hiện PR; `qk decide` đọc lại đầu PR trước khi merge |
| `verify_results` | không | Danh sách `{"exit": số nguyên}` |
| `usage` | không | Theo giai đoạn; chỉ giữ tên giai đoạn của runner: `preflight`, `planning`, `implementing`, `verifying`, `reviewing`, `fixing`, `publishing` |
| `fix_rounds`, `findings`, `addressed` | không | Finding có `severity`, `class`, `file` và `line` |
| `diff_stat` | không | `{"files": [], "added": n, "deleted": n}` |
| `blocked_at` | khi bị chặn | Chỉ tên giai đoạn; sổ không lưu lý do |
| `ledger_revision` | không | Tăng số này khi ghi trạng thái mới hơn của cùng một run |

- `--state-dir` là thư mục của bên gọi cho run này: phải tồn tại, nằm ngoài mọi repository và có `state.json`, file mà bản ghi trỏ tới. Đường dẫn này là danh tính của run, nên ảnh chụp sau của cùng run thay ảnh trước trong `qk brief`.
- `--producer` được lưu vào `data.producer` (một dòng, tối đa 100 ký tự). Card bị chặn của run này ghi tên producer thay vì gợi ý `qk run resume`.
- Đầu vào bị từ chối thì thoát 2 và không ghi gì. Gửi cùng đầu vào hai lần không thêm gì.
- Đầu ra: `{"contract": 1, "id": "<id bản ghi run>", "findings": n}`; không có `--json` thì in id bản ghi.

### `qk eval prepare` và `qk eval grade`

```text
qk eval prepare CASE DIR [--json]
qk eval grade   CASE WORKDIR [--final FILE] [--events FILE] [--json]
```

- `prepare` dựng repository Git của bài trong `DIR/repo` đúng như `qk-eval`: commit bản nền, và với bài review thì áp thay đổi mà không commit. Trả `{"contract": 1, "case", "skill", "write", "workdir", "task", "plan", "diff"}`: `task` cho bài làm, `plan` và `diff` (chép cạnh repository, ngoài thư mục bài) cho bài review. `DIR/repo` không được tồn tại trước.
- `grade` chạy `check.py` của bài từ một bản chép riêng và trả `{"contract": 1, "case", "criteria": [{"name", "passed", "detail"}], "passed"}`. `--final` là câu trả lời cuối của agent (mặc định rỗng). `--events` thêm tiêu chí `clean`: hỏng khi sự kiện nhắc tới thư mục bài. Bài không đạt tiêu chí vẫn thoát 0; đọc `passed`.
- Hai lệnh này không chạy agent, không ghi baseline và không ghi sổ. Các cờ cũ `qk eval --case/--skill/--all` không đổi.

## Định dạng thuộc hợp đồng

| Định dạng | Nội dung |
|---|---|
| Khối `qk-result` | JSON trong rào ```` ```qk-result ````: `status` (`done`, `blocked`, `needs_input`), `summary`, `files`, `evidence`, `reason`, `findings` |
| Khối `qk-verify` | Rào ```` ```qk-verify ````, mỗi dòng một lệnh shell; thành công là thoát 0 |
| Plan | Nội dung giữa `<<<QK-PLAN` và `QK-PLAN>>>` |
| `skills/<tên>/SKILL.md` | Đọc từ bản qk đã khoá |

Bên gọi tự tách các khối này.

## Luật phiên bản

- Tương thích, giữ phiên bản: thêm lệnh, thêm cờ tuỳ chọn, thêm trường JSON.
- Phá tương thích, tăng phiên bản và ghi CHANGELOG: bỏ hoặc đổi tên lệnh, cờ, trường; đổi nghĩa một trường, một mã thoát hay định dạng một khối.
- `tests/test_contract_v1.py` so đầu ra với các mẫu trong `tests/fixtures/contract/`. Sửa mẫu là quyết định về hợp đồng, không phải sửa test.

Không thuộc hợp đồng: hàm Python trong `scripts/`, máy trạng thái và thư mục trạng thái của qk-run, tên file của sổ, câu chữ prompt nội bộ, và mọi lệnh không liệt kê ở trên.
