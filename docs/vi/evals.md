# qk-eval: kiểm trước/sau cho skill và bước review của runner

[English](../en/evals.md) · [Mục lục](README.md) · [Source](../../scripts/qk_eval.py)

`qk-eval` chạy vài việc cố định qua một runtime và chấm từng kết quả bằng code, không bằng model. Dùng nó trước và sau khi bạn sửa một skill hoặc bước review của runner: nó cho biết tiêu chí nào pass, lượt chạy tốn bao nhiêu token, mất bao lâu, và so với baseline đã ghi.

## Cách dùng

```bash
python3 scripts/qk_eval.py --case csv-export --runtime omp:anthropic/claude-opus-5-5
python3 scripts/qk_eval.py --skill qk-debug --runtime codex:
python3 scripts/qk_eval.py --all --runtime claude:opus
python3 scripts/qk_eval.py --all --runtime codex: --update-baseline
```

Chọn đúng một trong `--case NAME`, `--skill NAME` (mọi case của skill đó, hoặc `runner-review`) và `--all`. `--runtime` nhận spec `runtime:model` giống [qk-run](runner.md). `--timeout` giới hạn mỗi lượt agent (mặc định 1800 giây). Case không tồn tại, hoặc lựa chọn không có case nào, thoát với mã 2. Cần Python 3.9+ và `git`.

## Các case

Case nằm ở `evals/cases/<tên>/`. Mỗi case chạy một lượt agent trong một repo git tạm mới: `repo/` của case được commit làm base, và agent làm việc ở đó.

| Case | Chạy | Tiêu chí được chấm |
|---|---|---|
| `csv-export` | `qk-cook` với `task.md`, có quyền ghi | `hidden-tests` (test nghiệm thu ẩn cho hợp đồng CSV), `repo-tests`, `scope` (chỉ module mới và file test của nó thay đổi), `csv-module` (module ghi bằng `csv.writer` hoặc `csv.DictWriter`), `report` |
| `pagination-empty-page` | `qk-debug` với `task.md`, có quyền ghi | `hidden-regression` (trang rỗng vẫn còn marker không còn kết thúc danh sách), `repo-tests`, `test-catches-bug` (test của repo fail khi đặt lại module gốc, và pass với một module đúng), `scope` (chỉ `collector/collect.py` và file test thay đổi), `report` |
| `waf-bundle-review` | prompt review của runner, chỉ đọc, trên pull request thật của `waf-upgrade-check` thêm chế độ bundle cho AWS MCP (khoảng 1.200 dòng thêm, 10 file), với tám lỗi mà lượt review thật cần nhiều vòng mới tìm hết được đặt lại | `result`, một tiêu chí cho mỗi lỗi (`pagination-empty-page`, `rules-not-list`, `priority-type`, `nested-statement`, `capacity-type`, `label-name-type`, `listed-version-name`, `caller-account-check`: một finding blocker hoặc important đúng file, nêu được trường nào sai và sai thế nào), `no-outside-important` |
| `bundle-malformed` | prompt review của runner (`qk_run.review_prompt`), chỉ đọc, trên một diff chưa commit | `result` (`qk-result` hợp lệ với status `done`), `capacity`, `nested-statement`, `list-name` (một finding blocker hoặc important cho mỗi chỗ trong ba chỗ kiểm tra bị bỏ sót, đúng dòng và nêu được trường nào sai, sai thế nào), `no-outside-important` (không có finding blocker hoặc important trên file ngoài diff) |

Mỗi case còn có tiêu chí `clean` do harness thêm: fail khi sự kiện của lượt chạy nhắc tới thư mục case (`evals/cases/`), vì agent có thể đã đọc bộ chấm. Bộ chấm (`check.py`, `hidden/`) được chép sang một thư mục riêng trước lượt chạy và chạy từ bản sao đó, nên agent có quyền ghi không sửa được thứ chấm mình.

`report` pass khi câu trả lời cuối có các nhãn `Done`, `Evidence`, `Not verified` và `Needs your decision`, mỗi nhãn ở đầu dòng và theo sau là `:` (in đậm hay không đều được). `check.py` của mỗi case in tiêu chí dưới dạng JSON; `check.py` bị lỗi, quá thời gian hoặc in thứ khác được tính là một tiêu chí fail tên `check.py`.

## Đọc kết quả

```text
case                   criteria                                   result    tokens    time
csv-export             hidden-tests, repo-tests, scope=FAIL, csv-module, report    FAIL(1)   212,400   3m10s
vs baseline csv-export (2026-11-20): 5/5 → 4/5, lost: scope; tokens -6.0%; time +4.0%; rerun: yes
verdict: regression (criterion lost: csv-export/scope)
```

- Mỗi tiêu chí fail được đánh dấu `=FAIL` trong cột tiêu chí. `result` là `PASS`, `FAIL(n)` với số tiêu chí fail, hoặc `ERROR` khi lời gọi agent thất bại (thiếu binary, quá thời gian, mã thoát khác 0).
- `tokens` là token đầu vào cộng đầu ra của lượt chạy; đầu vào đã gồm token cache. Hiện `n/a` khi runtime không báo usage.
- Khi runtime chưa có baseline, dòng so sánh là `no baseline for <spec>` và không có gì bị tính là regression.

## Thế nào là regression

Mã thoát là 1 khi có bất kỳ trường hợp nào dưới đây, và dòng verdict nêu từng lý do:

- **Mất tiêu chí:** một tiêu chí pass trong baseline nay fail hoặc không còn.
- **Token:** vượt quá 10% so với baseline của cùng case và runtime (+10% vẫn ổn, +11% thì không). Thời gian chỉ được báo, không bao giờ làm lượt chạy fail.
- **Lỗi agent:** bất kỳ case nào có lời gọi agent thất bại. `check.py` vẫn chạy trên những gì agent để lại.

Khi tập tiêu chí pass khác baseline theo bất kỳ chiều nào, case đó được chạy lại một lần ngay lập tức và lượt thứ hai được tính. Chỉ thay đổi token thì không chạy lại. Chỉ so sánh cùng một spec runtime.

## Cập nhật baseline

`evals/baseline.json` lưu theo từng spec runtime và case: ngày, kết quả từng tiêu chí, số token và số giây. `--update-baseline` in phần so sánh như thường trước, rồi ghi kết quả được tính của mọi case đã chọn cho runtime đó và thoát với mã 0. Các case khác và runtime khác giữ nguyên. Case có lỗi agent không bao giờ được ghi; lệnh liệt kê nó và thoát với mã 1.

Chỉ cập nhật baseline sau khi bạn đã xem kết quả thay đổi và chủ động chấp nhận nó — không bao giờ để xoá dấu vết một tiêu chí bị mất. Ghi từng runtime một.

## Kết quả trên đĩa

Mỗi lượt chạy ghi vào `$XDG_STATE_HOME/qk-eval/<YYYYmmdd-HHMMSS>-<hex>/` (mặc định `~/.local/state/qk-eval/`):

```text
results.json                  runtime, thời điểm bắt đầu, kết quả được tính của từng case, cờ regression
<case>/run-1/events.jsonl     sự kiện thô của runtime trong lượt chạy
<case>/run-1/final.md         câu trả lời cuối của agent
<case>/run-1/check.json       các tiêu chí đã chấm
<case>/run-1/plan.md          chỉ case review: plan đã duyệt và diff đưa cho reviewer
<case>/run-1/review.diff
<case>/run-2/...              chỉ khi case được chạy lại
```

Repo tạm bị xoá sau khi chấm. Codex cũng giữ home riêng của nó trong thư mục lượt chạy.

## Chi phí và giới hạn

Mỗi case là một lượt agent đầy đủ, có thể tốn hàng trăm nghìn token. Chạy một `--case` hoặc `--skill` khi đang thử, và `--all` trước khi chấp nhận một thay đổi. Không có gì chạy trong CI.

Đường dẫn skill trong prompt là đường dẫn tuyệt đối, nên agent vẫn có thể đọc phần còn lại của bản checkout qk, gồm cả `evals/cases/*/check.py` và `hidden/`. Lượt như vậy fail tiêu chí `clean`; agent không sửa được bộ chấm, vì bộ chấm chạy từ bản sao chụp trước lượt. `--update-baseline` không bao giờ ghi một case có lời gọi agent hoặc `check.py` bị lỗi.

Hành vi của harness được phủ bởi [`tests/test_qk_eval.py`](../../tests/test_qk_eval.py), dùng agent giả lập; file này cũng kiểm rằng repo của mỗi case pass test của chính nó và các bộ chấm fail trên bản chưa sửa.
