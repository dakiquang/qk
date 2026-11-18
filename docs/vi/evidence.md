# Bằng chứng kiểm thử

[English](../en/evidence.md) · [Mục lục](README.md)

Trang này ghi theo ngày: đã chạy gì, trên phiên bản nào và kết quả ra sao. Đây là bằng chứng, không phải cam kết hỗ trợ. Mỗi mục là một lần chạy trừ khi ghi khác, và bản runtime mới hơn có thể cho kết quả khác. Hướng dẫn lâu dài nằm ở [Runtime](runtimes.md) và [Runner qk-run](runner.md).

Kết quả kiểm tự động không ghi ở đây; bạn tự chạy:

```bash
python3 scripts/validate.py && python3 -m unittest discover -s tests -v
```

## Checklist kiểm thủ công

Chạy lại sau khi nâng cấp runtime hoặc sửa instruction của một skill. Dùng một thư mục tạm trống trên mỗi runtime.

1. **Gọi đích danh.** Gọi `qk-brainstorm` với câu hỏi "Should the app read its configuration from environment variables or a TOML file?" Dùng `/qk-brainstorm …` trong Claude Code, `$qk-brainstorm …` trong Codex, hoặc `/skill:qk-brainstorm …` trong omp ở chế độ RPC (chế độ tương tác chưa được kiểm). Đạt khi báo cáo kết thúc bằng **Done**, **Evidence**, **Not verified**, **Needs your decision** đúng thứ tự và thư mục không có file mới.
2. **Yêu cầu thường.** Hỏi "I need to plan and debug a config loader. In two sentences, what should I check first?" mà không gọi skill. Đạt khi câu trả lời hiển thị không chứa nhãn nào trong bốn nhãn. Ca này chỉ xét output nhìn thấy; nó không chứng minh skill không bị nạp vào context.

Với `qk/commit`, chỉ cần một runtime, trong một repo tạm có remote bare cục bộ:

3. **Chỉ commit.** Đạt khi có đúng một commit chứa các file dự định và không có gì được push.
4. **Có file env.** Đạt khi file env nằm ngoài commit và được nêu tên trong báo cáo.

Ghi ngày, phiên bản CLI, model và kết quả từng ca, kể cả lần fail. Một ca fail lặp lại trên một runtime là finding về instruction của skill; không nới điều kiện đạt.

## Kết quả kiểm runtime

### 13 và 14/11/2026

| Runtime | Gọi đích danh | Yêu cầu thường |
|---|---|---|
| Claude Code 2.1.322 (`claude -p`) | Đạt: bốn nhãn đúng thứ tự, không có file | Đạt: không có nhãn |
| Codex 0.160.0 (`codex exec --sandbox read-only`) | Đạt | Đạt |
| omp 18.18.3 (RPC) | Đạt; nội dung skill được chèn | Đạt; không chèn gì |
| Qwen Code | Chưa kiểm: phiên đăng nhập hết hạn | Chưa kiểm |

Ngày 13/11/2026, gọi đích danh `qk-prefs` với kho đề xuất trống trên cùng ba runtime: cả ba tìm được script qua thư mục skill symlink, báo không có đề xuất đang chờ và kết thúc bằng bốn nhãn đúng thứ tự.

Ngày 14/11/2026, Claude Code 2.1.322 chạy `/qk-commit commit` trong repo tạm có remote bare cục bộ. Lệnh tạo đúng một commit chứa file đã theo dõi có thay đổi, không push, để một file chưa theo dõi không liên quan ở ngoài và nêu tên file đó. Khi có file env, file này nằm ngoài commit, được nêu tên trong báo cáo và nội dung không bị đọc. Cả hai commit message đều không có dòng ghi công AI.

### 08/11/2026

Chế độ chỉ đọc, trong repo tạm. Mỗi runtime nhận một lời gọi đích danh `qk-brainstorm` và một yêu cầu lập kế hoạch thường không nhắc qk.

| Runtime | Gọi đích danh chạy skill | Yêu cầu thường không nạp qk |
|---|---|---|
| Claude Code (Sonnet 5.5, `--permission-mode plan`) | Có; trả lời đúng định dạng skill | Có; không nạp skill |
| Codex (`codex exec -s read-only`) | Có | Có; không đọc file skill |
| omp 18.15.0 (RPC) | Có; nội dung skill được chèn | Có; không chèn gì |
| Qwen Code | Chưa thử được: API trả 401 (đăng nhập hết hạn) | Chưa thử được |
| Orca | — | Liệt kê mỗi skill qk một lần |

Chưa phủ: phiên tương tác, chạy lặp nhiều lần, Qwen sau khi đăng nhập lại, và việc chạy chung với mọi lệnh native.

**`qk-dogfood` trên Codex CLI 0.160.0** (`--sandbox read-only --ephemeral --json`, không đổi account, model hay config). Năm fixture tổng hợp được chạy bằng cách đọc instruction trực tiếp: hướng dẫn plan mơ hồ sinh một đề xuất gộp; luật đã rõ mà agent bỏ qua không sinh luật trùng; lỗi 403/429 không sinh bản vá instruction; chỉ có inventory thì không được coi là đã dùng skill; transcript injection kèm `--apply` không thực thi payload, không in credential giả và không sửa file. Một project riêng chỉ có bản sao project-local ở `.agents/skills/qk-dogfood` cho thấy lời gọi native `$qk-dogfood` nạp bản sao đó còn yêu cầu thường thì không đọc. Snapshot fixture và source không đổi sau mỗi lần chạy. Các phép thử này kiểm instruction, không kiểm cơ chế tự tìm skill của runtime, trừ lời gọi project-local; đây là các lần chạy đơn lẻ trên Codex, không chứng minh an ninh sandbox hay việc `qk-dogfood` kích hoạt trên Claude Code, omp hoặc Qwen.

**Sau khi chuyển instruction sang tiếng Anh**, mười lần chạy cô lập dùng omp 18.15.0 với `anthropic/claude-opus-5-5`. Các phép kiểm Codex ở trên diễn ra trước thay đổi này.

Sáu lần đọc trực tiếp instruction `qk-dogfood`: các sự kiện độc lập sinh một đề xuất; log trùng hoặc retry của cùng một sự kiện không đạt ngưỡng; luật đã rõ mà agent bỏ qua được xếp là lỗi tuân thủ; lỗi 403/429 sinh báo cáo tiếng Anh mà không vá instruction; chỉ có inventory thì không được coi là đã dùng; bằng chứng bên thứ ba kèm injection và `--apply` chỉ sinh đề xuất gửi upstream hoặc fork, không thực thi payload và không in credential giả. Các báo cáo còn lại viết bằng tiếng Việt, theo ngôn ngữ người dùng.

Bốn lần RPC dùng bản sao project-local `.omp/skills`: `/skill:qk-dogfood`, `/skill:qk-plan revise` và `/skill:qk-handoff resume` theo đúng hợp đồng, còn yêu cầu tổng kết thường chỉ đọc file phiên. Sửa plan giữ nguyên heading tiếng Việt và trạng thái nháp dù báo cáo bằng tiếng Anh; nhận handoff phát hiện chỗ lệch rồi chờ, không sửa file. Chỉ file plan trong fixture sửa plan bị thay đổi.

Chưa phủ: đây là các lần chạy đơn lẻ trên một model, chưa phải ma trận đầy đủ cho mười skill thời điểm đó. Bản instruction tiếng Anh khi ấy chưa được chạy lại trên Codex, Claude Code, Qwen hoặc omp tương tác; kết quả smoke ngày 13/11/2026 ở trên sau đó đã phủ Claude Code và Codex.

## Cài bằng `npx skills`

**14/11/2026.** skills 1.8.1 trên macOS, mỗi lần chạy đặt `HOME` vào một thư mục tạm trống.

- `npx skills add <bản clone local> -g -a claude-code codex qwen-code -y`, và lệnh tương tự từ `dakiquang/qk` trên GitHub: mười hai thư mục skill ở `~/.agents/skills`, kèm symlink tới đó trong `~/.claude/skills` và `~/.qwen/skills`. Mọi thư mục còn `agents/openai.yaml` và `disable-model-invocation: true`; `qk-commit` và `qk-prefs` còn thư mục `scripts/`.
- Từ bản đã cài, `qk_prefs.py list` chạy và thoát 0, `qk_preflight.py identity` chạy được (báo chưa có account GitHub nào đăng nhập, đúng như dự kiến với `HOME` trống).
- Claude Code 2.1.325 `/context` liệt kê mười hai skill là `qk-agent-coord` … `qk-test`, không có tiền tố `qk:`. Chưa kiểm việc gọi skill vì `HOME` tạm chưa đăng nhập.
- Khi chỉ có `-a claude-code`, các thư mục được chép thẳng vào `~/.claude/skills`.
- Symlink thủ công có sẵn `~/.claude/skills/qk-plan` bị thay bằng bản cài.
- `dakiquang/qk#v0.2.0` cài đúng tag đó và ghi `ref: v0.2.0` vào file lock; sau đó `npx skills check` báo bản cài đã mới nhất. `dakiquang/qk@main` lỗi "No matching skills found for: main", vì phần sau `@` được hiểu là tên skill.
- Bản cài từ đường dẫn local được `check` báo là không kiểm được; muốn làm mới thì chạy lại `add`.
- `npx skills remove -g -y <mười hai tên>` gỡ hết thư mục và link của qk.
- Khi môi trường có `CLAUDE_CONFIG_DIR`, link cho Claude Code nằm ở `$CLAUDE_CONFIG_DIR/skills` dù `HOME` trỏ nơi khác.

Chưa phủ trong `HOME` trống: gọi skill sau khi cài (chưa đăng nhập), và Qwen Code.

**14/11/2026, một máy thật chuyển từ link thủ công.** Sau khi gỡ các link qk thủ công, `npx skills add 'dakiquang/qk#v0.3.0' -g -a claude-code codex qwen-code -y` đặt skill ở `~/.agents/skills`, kèm symlink trong `~/.claude/skills` và `~/.qwen/skills`; `~/.codex/skills` không còn mục qk nào. Trong một thư mục trống:

| Runtime | Lời gọi | Kết quả |
|---|---|---|
| Claude Code 2.1.325 (`claude -p`) | `/qk-brainstorm …` | Đạt: bốn nhãn đúng thứ tự, không tạo file |
| Codex 0.160.0 (`codex exec --sandbox read-only`) | `$qk-brainstorm …` | Đạt: bốn nhãn đúng thứ tự. `~/.codex/skills` không có skill qk nên Codex nạp từ `~/.agents/skills` |
| omp 18.18.3 (RPC) | `/skill:qk-brainstorm …` | Đạt: nội dung skill được chèn, đủ bốn nhãn |
| Qwen Code | — | Chưa kiểm: phiên đăng nhập hết hạn |

`npx skills check` không báo bản cập nhật nào cho qk. Mỗi thư mục skill chỉ có một bản của mỗi skill qk.


## Luật "vừa đủ"

**14/11/2026.** Claude Code 2.1.325, `claude -p` cho phép sửa file, trong một repo tạm mới có một unit test đang fail: `/qk-cook Fix the failing test. Done when python3 -m unittest passes.` Trước thay đổi (v0.3.0): 5 lượt, tổng 250.999 token. Sau khi thêm luật vào `qk-cook`, `qk-test`, `qk-debug`, `qk-research` và `qk-plan`: 5 lượt, 251.201 token. Cả hai lần đều sửa được test, có chạy test, và kết thúc bằng bốn nhãn đúng thứ tự. Mỗi bên một lần chạy, trên việc quá nhỏ để thấy tiết kiệm; kết quả chỉ cho thấy luật không làm hỏng skill và không thêm chi phí.

## Hook ghi nhận sở thích

| Runtime | Kết quả |
|---|---|
| Claude Code 2.1.322 | Phiên `claude -p` thật trong project tạm với prompt "Từ nay commit message viết bằng tiếng Anh nhé.": agent ghi một đề xuất và báo đề xuất đang chờ `qk/prefs`. Prompt "làm luôn đi" không ghi gì. `/qk-prefs` liệt kê đề xuất mà không sửa file, coi "ok" là chưa quyết; khi được duyệt rõ ràng thì ghi một dòng vào đích đã nêu và đóng đề xuất. Không file rules, `CLAUDE.md` hay memory nào bị đổi |
| Codex 0.160.0 | Một phiên `codex exec` trong thư mục tạm: lời nhắc được chèn, agent chạy `propose` và đề xuất nằm đúng kho đã cấu hình. Prompt thử có bảo agent làm theo hướng dẫn hệ thống, nên kết quả chứng minh đường đi hoạt động, chưa nói được agent làm theo thường xuyên đến đâu |
| omp, Qwen Code | Chưa hỗ trợ, chưa kiểm |

## Runner qk-run

**08/11/2026.** Chạy thật đầu-cuối trên một repo GitHub private tạm đã mở PR ready-for-review chỉ chứa đúng file dự kiến với từng bên triển khai: omp (Opus 5.5) do Codex review, Claude Code (Sonnet) do Codex review, và Codex do omp (Opus 5.5) review. Sau các bản sửa từ review, cặp mặc định omp/Codex được chạy lại một lần với cùng kết quả.

**13/11/2026.** Lần chạy đầu tiên trên việc thật: một thay đổi tài liệu trong chính repo này. omp với Opus 5.5 triển khai, Codex review. Có một lần `revise` trước khi duyệt; cả hai lệnh verify đều đạt, review không có finding và không cần vòng sửa. PR ready-for-review được mở khoảng tám phút sau `start`. Kiểm tra account để push đạt ở preflight và ngay trước khi push.

**14/11/2026.** Việc thật thứ hai: một thay đổi code cho chính runner, để tiêu đề commit và PR có type theo quy ước commit của repo, kèm test và docs EN/VI. omp với Opus 5.5 triển khai, Codex review. Có một lần `revise` trước khi duyệt để chốt hai câu hỏi còn mở trong plan; cả hai lệnh verify đều đạt, review không có finding và không cần vòng sửa. PR ready-for-review được mở khoảng bốn phút sau `approve`, và CI đạt. Vì chính run này dùng code runner cũ, tiêu đề PR của nó là tiêu đề plan trần và được đặt lại theo quy ước khi squash-merge.

**14/11/2026, run thứ ba tới thứ năm.** Cả ba run đều dùng omp với Opus 5.5 để triển khai và Codex (`gpt-6-sol`) để review.

| Run | Việc | Trước khi duyệt | Sau khi duyệt | Review |
|---|---|---|---|---|
| 3 | Lệnh `versions` và `diff` của một CLI Python nhỏ, 16 file | Một plan, duyệt nguyên văn | PR sau khoảng 5 phút; CI đạt trên Python 3.10–3.15 | Một finding mức important: test vẫn có thể đọc credential AWS thật của máy. Đã sửa trong vòng sửa duy nhất |
| 4 | Runner in từng thao tác của agent, báo khi agent im lâu, và dừng cả process group khi quá giờ; 8 file | Một plan, duyệt nguyên văn | PR sau khoảng 12 phút; CI đạt | Một finding mức important: timeout âm của hàng đợi ở ranh giới heartbeat. Đã sửa trong vòng sửa; còn một nit |
| 5 | Lệnh `check` của cùng CLI, 10 file, chạy bằng runner của run 4 | Một lần `revise` để chốt hai câu hỏi do chính bên lập plan nêu ra | PR sau khoảng 7 phút; CI đạt | Không có finding, không cần vòng sửa |

Tiêu đề PR của run 3 bị cắt giữa chữ ở ký tự thứ 72 và còn tiền tố tên dự án (`feat: waf-upgrade-check: … (project plan st`); tiêu đề được đặt lại khi merge, và run 4 đã sửa nguyên nhân.

Run 5 là run đầu tiên có output trực tiếp: 33 dòng thao tác khi lập plan, 29 dòng khi triển khai và 46 dòng khi review, đồng thời mọi sự kiện thô được lưu trong `<stage>-<ts>.events.jsonl`. Log cho thấy hai điều trước đây không thấy được: bên lập plan đã đọc mô tả dịch vụ wafv2 trong botocore để kiểm dạng dữ liệu, và reviewer Codex đã đọc skill `ak-code-review` cài toàn cục trên máy, tức skill cài toàn cục có thể ảnh hưởng tới bước review của runner.

Một lượt review chéo riêng cho PR của run 4 tìm thêm một lỗi mức important (tin nhắn omp chỉ có tool call có thể ghi đè câu trả lời cuối) và bốn nit; cả năm đã được sửa trước khi merge, bốn trong số đó có test hồi quy fail với code cũ.

**2026-11-14, run sáu đến chín.** omp với Opus 5.5 triển khai; Codex (`gpt-6-sol`) review, trừ khi có ghi chú.

| Run | Việc | Diễn biến |
|---|---|---|
| 6 | Siết lệnh `check` của cùng CLI | Dừng ở bước lập plan: planner đọc tài liệu AWS qua MCP và chỉ ra một thay đổi so khớp label trái với hành vi của AWS, điều mà cả người viết lẫn một reviewer trước đó đều đã chấp nhận. Run bị huỷ và yêu cầu được sửa |
| 7 | Chế độ bundle cho AWS MCP của cùng CLI, khoảng 1.400 dòng | Một vòng sửa, rồi thêm bốn lượt review sửa tay, mỗi lượt tìm thêm một trường hợp của cùng một loại lỗi (đầu vào sai cấu trúc dẫn tới crash). Từ đây có bài đo `waf-bundle-review` và prompt review bên dưới |
| 8 | Runner cô lập agent khỏi skill và MCP toàn cục, chốt chặn bước chỉ đọc, ghi token, `resume` nhận sửa tay | Review không có lỗi; một lượt audit chéo riêng sau đó tìm 2 lỗi important (mẫu tìm kiếm làm chốt chặn chặn nhầm; `--read-only-mcp` rỗng cho `mcp://` lọt qua), đã sửa kèm test. Phát hành 0.5.0 |
| 9 | Bộ đo và ba bài mẫu | Agent sửa dừng giữa lượt mà không có khối kết quả; lần đầu dùng thật `resume` sau sửa tay (ba lượt). Một lượt audit chéo được yêu cầu soát theo loại lỗi tìm ra năm lỗi important trong một lượt |

## Đo prompt review

**2026-11-14 và 15, Claude Opus 5.5.** Các bài cố định và bộ chấm bằng code nằm trong [`evals/`](../../evals/). `waf-bundle-review` là một diff 1.200 dòng dựng lại từ một pull request thật, với tám lỗi thật được đặt lại; một lỗi được tính khi có finding blocker hoặc important đúng file, nêu được trường nào và sai thế nào. Với prompt review cũ, cả hai runtime bắt được **0 trên 8**.

Prompt mới ([#26](https://github.com/dakiquang/qk/pull/26)) yêu cầu reviewer soát theo loại lỗi và xếp crash do đầu vào từ ngoài ít nhất là important:

| Runtime và bài | Prompt cũ | Prompt mới (từng lần) | Token |
|---|---:|---:|---|
| omp, `waf-bundle-review` | 0/8 | 5, 5, 4 | 0,81M → 0,75–1,05M |
| Claude Code, `waf-bundle-review` | 0/8 | 3, 6, 5 | 0,61M → 0,38–0,47M |
| omp, `bundle-malformed` | 6/6 | 6/6 | xem bên dưới |
| Claude Code, `bundle-malformed` | 6/6 | 6/6 | 99.628 → 59.028–81.643 |

Lần chạy omp đầu tiên của `bundle-malformed` tốn hơn baseline 36% token. Sáu lần chạy thêm giải thích điều này:

| Prompt | Các lần: token (số lượt agent) |
|---|---|
| cũ | 60.361 (4) · 53.316 (4) · 53.608 (4) |
| mới | 82.257 (**5**) · 55.939 (4) · 55.423 (4) |

Cùng số lượt, prompt mới tốn hơn khoảng 4% (finding dài hơn). Con số 36% đến từ một lần chạy đi thêm lượt thứ năm để đọc lại các dòng nó trích, khoảng 22–26 nghìn token; riêng prompt cũ đã dao động khoảng 12%. Giờ token chỉ bị tính là thụt lùi khi vượt baseline **cả** hơn 10% **lẫn** hơn 25.000 token, xấp xỉ một lượt agent (chốt ngày 15/11). Baseline của hai bài review đã được ghi lại với prompt mới.

Kết quả bài khó dao động giữa các lần chạy (omp 4–5, Claude Code 3–6): mức tăng từ 0/8 lên khoảng 5/8 là rõ, nhưng muốn so các chênh lệch nhỏ hơn trên bài này thì cần chạy nhiều lần. Khi ghi baseline omp đầu tiên, chốt chặn bước chỉ đọc đã dừng reviewer lúc nó gọi công cụ `run_script` của AWS MCP; lần đó không được ghi, và prompt giờ dặn reviewer không gọi MCP.

## So sánh các kit

**2026-11-15, Claude Code với Claude Opus 5.5.** Bốn bài đo, mỗi bài chạy hai lần với ba kit trên cùng một nền ([cách làm](evals.md#so-sánh-các-kit)): không có skill hay plugin của người dùng, không MCP ở lượt chỉ đọc, giữ skill có sẵn của Claude Code, và định dạng đầu ra mà bộ chấm cần được đưa cho cả ba kit bằng cùng một câu chữ. `none` chỉ nhận việc; Superpowers 7.0.2 (commit `22f0b46`) nạp bằng `--plugin-dir` và tự kích hoạt; qk nhận skill của nó (`qk-cook`, `qk-debug`) hoặc prompt review của runner. Tổng chi phí Claude Code báo: 8,74 USD.

| Bài | none | Superpowers | qk |
|---|---|---|---|
| `bundle-malformed` (review, 3 lỗi) | 3/3, 3/3 · 33k token | 3/3, 3/3 · 37k | 3/3, 3/3 · 36k |
| `csv-export` (`qk-cook`) | đạt, đạt · 185k | đạt, đạt · 240k | đạt, đạt · 166k |
| `pagination-empty-page` (`qk-debug`) | đạt, đạt · 178k | đạt, đạt · 210k | đạt, đạt · 226k |
| `waf-bundle-review` (review, 8 lỗi) | **0/8, 0/8** · 320k | **0/8, 0/8** · 376k | **3/8, 4/8** · 532k |

Token là trung vị của hai lần chạy. Mọi lần chạy đều đạt `clean`: không agent nào đọc bộ chấm.

Kết quả này cho thấy gì và không cho thấy gì:

- Ở ba bài nhỏ, cả ba kit đều đạt mọi tiêu chí; các bài này quá dễ để phân biệt. qk không hơn ở đây. qk tốn ít token nhất ở `csv-export` và nhiều nhất ở `pagination-empty-page`; chênh lệch cỡ này nằm trong mức dao động giữa các lần chạy đã đo ở trên.
- Ở bài review khó, chỉ qk bắt được lỗi ở mức blocker hoặc important, và qk tốn nhiều token nhất. Hai kit còn lại có thấy một phần: một lần `none` và cả hai lần Superpowers báo rằng `WebACL.Rules` không được kiểm là danh sách, nhưng xếp ở mức nit, giống prompt cũ của qk.
- Bài này dựng từ chính lịch sử của qk, và prompt review hiện tại được viết sau khi thấy reviewer bỏ sót nó. Kết quả cho thấy prompt có tác dụng với đúng loại lỗi nó được viết ra để sửa, chưa cho thấy qk review tốt hơn nói chung. Bước tiếp theo là một bài từ dự án khác.
- Superpowers được thiết kế quanh quy trình riêng của nó (brainstorm, plan, TDD, subagent). Các bài này cho mỗi kit một lượt và một việc cố định, nên không dùng tới phần lớn quy trình đó.

### Một bài từ dự án khác

`pip-config-review` được dựng lại từ pypa/pip#13535 (MIT) theo bản gửi review đầu tiên, với ba lỗi mà lượt review công khai của PR đã tìm ra:

| Lỗi | Hành vi sai |
|---|---|
| `null-device` | Với `PIP_CONFIG_FILE=/dev/null`, `pip config set` thoát với mã 0 nhưng làm mất giá trị. |
| `parser-reuse` | Parser của file env được thêm vào `_parsers[Kind.ENV]` thay vì `self.load_only`, nên việc nạp không thể gọi lại an toàn. |
| `env-unset` | `unset` không bao giờ hoạt động khi dùng `PIP_CONFIG_FILE`. |

Đây là bài đầu tiên không lấy từ lịch sử của qk. Bài được chọn từ bốn ứng viên công khai trước khi chạy qk trên nó, và prompt review không được đổi cho bài này. Xem [evals.md](evals.md#các-case) để biết cách chấm các bài.

**2026-11-15.** Mỗi ô là một lần chạy, trừ khi có ghi khác. `n/3` đếm số lỗi được báo ở mức blocker hoặc important trên đúng dòng.

| Runtime | Kit | Lỗi | Token |
|---|---|---|---|
| Claude Code, Claude Opus 5.5 | none | 1/3 (`env-unset`) | 65k |
| Claude Code, Claude Opus 5.5 | Superpowers 7.0.2 | 2/3 (`parser-reuse`, `env-unset`) | 97k |
| Claude Code, Claude Opus 5.5 | qk | 2/3 và 3/3 trong hai lần chạy (cả hai lần đều có `null-device` và `env-unset`; `parser-reuse` được xếp nit một lần, important một lần) | 198k, 238k |
| omp, Claude Opus 5.5 | qk | 2/3 (`parser-reuse` được xếp nit) | 149k |
| Codex, GPT-6.1-sol | qk | 2/3 trong ba lần chạy; không lần nào báo `parser-reuse` | 166k–286k |

Baseline `pip-config-review` ghi ngày 2026-11-15: Claude Code 3/3 (237.877 token), omp 2/3 (149.308 token).

Kết quả này cho thấy gì và không cho thấy gì:

- qk là kit duy nhất báo `null-device`; nó tốn nhiều token nhất.
- Trên các model Claude, qk thấy `parser-reuse` ở mọi lần chạy nhưng xếp nit ở hai trong ba lần, nên lỗi này không được tính. Trên Codex, qk hoàn toàn không thấy lỗi này.
- Đây là các lần chạy đơn lẻ, trừ khi có ghi khác; chênh lệch một lỗi nằm trong mức dao động giữa các lần chạy và không cho thấy kit nào review tốt hơn.
- Bộ chấm được sửa hai lần trong lúc đo (`72c1741`: một finding `null-device` còn được tính nhầm cho `parser-reuse`; `656cb88`: bản sửa đó lại bác một finding đúng về việc thêm trùng). Mọi câu trả lời đều được chấm lại bằng bộ chấm cuối cùng; bảng dùng điểm cuối cùng.
- Một thay đổi prompt thử nghiệm yêu cầu reviewer gọi tên loại lỗi theo hành vi sai không làm thay đổi kết quả nào trên Codex (`pip-config-review` 2/3, `bundle-malformed` 3/3, `waf-bundle-review` 6/8), và không được giữ lại.

## Số đo thiết lập gọn nhẹ

Các lệnh trong [Thiết lập gọn nhẹ](lean-setup.md) được kiểm một lần trên Claude Code 2.1.322, Codex 0.160.0 và omp 18.18.3 ngày 13/11/2026. Qwen Code chưa kiểm.

## Sổ bằng chứng và CLI

**16/11/2026, macOS.** Sổ cô lập ghi nhận một lần `qk run start` thật bị chặn bởi
checkout còn thay đổi, không tạo worktree hay publish. Claude Code (Claude Opus 5.5),
Codex (GPT-6.1-sol) và omp (Claude Opus 5.5) mỗi runtime chạy `qk show` rồi
`qk log claim` qua shell. Mỗi claim trỏ tới run đã quan sát và giữ nguồn model.
Lần smoke Codex đầu dừng trước khi gọi công cụ vì thư mục tạm chưa phải repo Git;
khởi tạo đúng fixture cho phép tiếp tục các runtime còn lại. Qwen Code chưa kiểm.

`qk sync --backfill` thật nạp 10 run cũ và một finding còn lại. Chạy lại giữ nguyên
hai số đếm; mỗi lần sync thêm chín quan sát trạng thái PR có thời điểm.
Các PR đã quan sát đều merge hoặc đóng, nên brief offline hiện đúng là không có
PR chờ. Nhánh PR mở/bằng chứng cũ/chưa biết được kiểm bằng test CLI, không phải PR
thật còn mở trong lần smoke này. Không chạy merge, close, comment, commit hay push.

Ba skill mỗi skill thêm một dòng claim tuỳ chọn: tăng 543 byte, tổng `SKILL.md`
là 49.039 byte. Quan sát trước/sau trên `omp:anthropic/claude-opus-5-5`,
mỗi bên một lần:

| Case | Tiêu chí trước → sau | Token trước | Token sau |
|---|---|---:|---:|
| `csv-export` | 6/6 → 6/6 | 79.807 | 77.109 |
| `test-failure-triage` | 7/7 → 7/7 | 63.199 | 57.108 |
| `handoff-drift` | 7/7 → 7/7 | 46.703 | 56.622 |

So sánh trong phiên không báo mất tiêu chí hay vượt ngưỡng token; handoff tăng
9.919 token, dưới sàn 25.000. Chỉ hai ca mới được thêm baseline vào repo; baseline
cũ không bị thay. Hai lần chấm trượt nhầm được sửa từ câu trả lời và sự kiện trước
đã lưu: `$?` được lấy ngay vẫn là bằng chứng hợp lệ dù shell wrapper thoát 0,
và hai ví dụ drift đúng không phải lỗi. Giữ nguyên bằng chứng gốc; sửa bộ chấm
không chạy lại model.

**Kết luận hiệu năng: inconclusive.** Mỗi bên chỉ có một quan sát, không có khoảng
ước lượng hiệu ứng; cache và tải nền không được kiểm soát. Số đo gồm khởi động
runtime, công việc model/công cụ và chấm kết quả. Chỉ chứng minh hành vi đã quan sát,
không khẳng định tiết kiệm token hay nhanh hơn. [Hướng dẫn sổ](ledger.md).

Validator và full suite Python 3.12 đạt trước review (192 test, một skip).
Review độc lập tìm hai lỗi, đều đã tái hiện và sửa: backfill đến muộn che run đã
resume; chuỗi shell short-circuit đánh lừa bộ chấm triage. Revision nguồn nay giữ
đúng thứ tự run; chỉ lệnh kiểm thật và wrapper được xác thực mới tính là quan sát.
Sau sửa, Python 3.12 đạt CLI 24, triage 8, ledger 27 và resume 4 test;
Python 3.9 đạt regression late-backfill và cả tám test triage. Câu trả lời model
thật đã lưu vẫn đạt bộ chấm siết lại, không cần gọi thêm model.

## Bài học đầu tiên

18/11/2026, Codex `gpt-6.1-sol`, case `pip-config-review`, tiêu chí đích
`parser-reuse`. Lesson `d13e1f58a54b` (lớp "giá trị được ghi hoặc đọc dưới sai
khoá hay phạm vi"), bằng chứng là một lượt sót trên Codex (`4db9d7a13ad1`) và một
trên omp (`31b776ca993e`). Hai lượt lấy bằng chứng trên Codex: một sót, một bắt
thật (finding ở dòng 404 đề nghị dùng lại parser đã nạp), nên Codex nay sót khoảng
1/2, không còn 3/3 như 15/11.

| Nhóm | Lượt 1 | Lượt 2 |
|---|---|---|
| Không có lesson | bắt | sót |
| Có lesson | sót | bắt |

Đối chứng `bundle-malformed` và `waf-bundle-review` có lesson không mất tiêu chí
nào. Lượt `bundle-malformed` không có lesson lỗi vì Codex báo model hết công suất;
lỗi này không đổi kết luận.

**Kết luận: lesson không giúp** (đo `18e9d3101a4f`). Có lesson vẫn sót 1/2, bằng
không có lesson. Mỗi ô hai lượt là bằng chứng mỏng; kết quả chỉ nói luật này không
cho thấy hiệu quả, không nói lỗi này không thể dạy được.
