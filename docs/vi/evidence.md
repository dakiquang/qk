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

## Đo prompt review

**14/11/2026, Claude Opus 5.5.** Bài mẫu cố định và bộ chấm bằng code nằm trong [`evals/`](../../evals/). Baseline dùng prompt review cũ. `bundle-malformed` đạt cả sáu tiêu chí trên hai runtime. Với `waf-bundle-review`, diff 1.200 dòng dựng lại từ PR WAF thật, cả hai runtime đều bắt 0/8 lỗi ở mức blocker hoặc important. Một lần chạy baseline omp bị chốt chặn MCP dừng khi reviewer gọi AWS MCP trong bước chỉ đọc; lần chạy lại hợp lệ đã được ghi vào `baseline.json`.

Với prompt đề xuất yêu cầu soát theo loại lỗi và định nghĩa mức độ cho đầu vào ngoài sai cấu trúc:

| Runtime và bài | Baseline | Kết quả mới | Token |
|---|---:|---:|---:|
| omp, `waf-bundle-review` | 0/8 | 5/8, giữ nguyên ở lần chạy lại bắt buộc | 812.971 → 754.188 (−7,2%) |
| omp, `bundle-malformed` | 6/6 | 6/6 | 60.361 → 82.257 (+36,3%) |
| Claude Code, `bundle-malformed` | 6/6 | 6/6 | 99.628 → 81.643 (−18,1%) |
| Claude Code, `waf-bundle-review` | 0/8 | 3/8 ở lần chạy hợp lệ đầu; lần chạy lại chưa xong | 614.717 → đang chờ |

Mức tăng token của bài nhỏ trên omp vượt ngưỡng thụt lùi 10% đã chốt. Lần chạy lại WAF bắt buộc trên Claude Code bị dừng do giới hạn phiên năm giờ, nên chưa có kết quả cuối. Những lần chạy đơn lẻ này chưa chứng minh cải tiến chung hay đủ điều kiện phát hành. Kết quả thô trên máy: `~/.local/state/qk-eval/20261114-222849-9139/` (omp) và `~/.local/state/qk-eval/20261114-223619-0024/` (Claude Code).

## Số đo thiết lập gọn nhẹ

Các lệnh trong [Thiết lập gọn nhẹ](lean-setup.md) được kiểm một lần trên Claude Code 2.1.322, Codex 0.160.0 và omp 18.18.3 ngày 13/11/2026. Qwen Code chưa kiểm.
