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

## Số đo thiết lập gọn nhẹ

Các lệnh trong [Thiết lập gọn nhẹ](lean-setup.md) được kiểm một lần trên Claude Code 2.1.322, Codex 0.160.0 và omp 18.18.3 ngày 13/11/2026. Qwen Code chưa kiểm.
