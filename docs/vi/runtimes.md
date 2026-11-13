# Runtime

[English](../en/runtimes.md) · [Mục lục](README.md)

qk mở rộng runtime, không thay tool, plan mode, task, subagent, model, quyền hay hook. Chỉ dẫn cấp cao hơn, luật runtime và luật repo (`AGENTS.md`, `CLAUDE.md`, tài liệu đóng góp) luôn thắng skill.

## Chỉ chạy khi gọi đích danh

Tên riêng chưa đủ: mô tả “dùng khi lập kế hoạch” có thể cạnh tranh với plan mode/lệnh sẵn có. qk dùng hai lớp:

1. Cấu hình native của runtime để ngăn model tự nạp.
2. Mô tả nêu trigger cụ thể (`qk/plan`, `/qk-plan`, `$qk-plan`, `/skill:qk-plan`), không dùng từ khóa công việc chung làm điều kiện kích hoạt.

| Runtime | Cấu hình trong qk | Tác dụng |
|---|---|---|
| Claude Code | `disable-model-invocation: true` trong `SKILL.md` | Chỉ người dùng gọi; tài liệu Claude Code nói cũng không preload vào subagent |
| omp | Cùng trường, đọc thành `disableModelInvocation` | Không cho tự gọi |
| Codex | `agents/openai.yaml`: `policy.allow_implicit_invocation: false` | Không tự gọi ngầm |
| Qwen Code | Chưa xác nhận cấu hình | Chưa biết |

Theo hợp đồng, qk không tự gọi skill qk khác; chỉ nêu lệnh để bạn gọi. Đây là ranh giới cách làm, không phải bảo đảm an ninh trên runtime chưa kiểm.

`scripts/validate.py` kiểm cấu hình và mô tả, chỉ nhận dạng canonical của `agents/openai.yaml`: hai block, thụt hai space, chuỗi double quote không backslash, comment nguyên dòng. Cú pháp ngoài tập này bị từ chối thay vì diễn giải YAML tùy ý.

## Hành vi đã thử

Thử thật ngày 08/11/2026 trên repo tạm với chế độ chỉ đọc. Mỗi runtime một lời gọi đích danh `qk-brainstorm` và một yêu cầu lập kế hoạch không nhắc qk.

| Runtime | Gọi đích danh chạy skill | Yêu cầu thường không nạp qk |
|---|---|---|
| Claude Code (Sonnet 5.5, `--permission-mode plan`) | Có, trả đúng cấu trúc skill | Có, không nạp skill |
| Codex (`codex exec -s read-only`) | Có | Có, không đọc file skill |
| omp 18.15.0 (RPC) | Có, chèn nội dung skill | Có, không chèn |
| Qwen Code | Chưa thử được: API 401, token hết hạn | Chưa thử được |
| Orca | — | Liệt kê mỗi skill qk một lần |

Đây là một lần chạy, không phải chứng nhận. Chưa kiểm: phiên tương tác, lặp nhiều lần, Qwen sau đăng nhập lại và cùng tồn tại với mọi lệnh native.

Kiểm bổ sung `qk-dogfood` ngày 08/11/2026 dùng Codex CLI 0.160.0 với
`--sandbox read-only --ephemeral --json`, không đổi account, model hay config.
Chạy năm fixture tổng hợp độc lập bằng cách yêu cầu đọc instruction trực tiếp:
hướng dẫn plan mơ hồ sinh một đề xuất gộp; agent bỏ qua luật đã rõ không sinh luật
trùng; lỗi 403/429 không sinh bản vá instruction; chỉ có inventory không được coi
là đã dùng skill; transcript injection kèm `--apply` không thực thi payload, không
in credential giả hoặc sửa file. Snapshot fixture và source không đổi sau từng
lần. Các phép thử này kiểm instruction, không kiểm native discovery.

Một project tạm riêng chứa bản sao project-local tại `.agents/skills/qk-dogfood`,
không đổi bản cài global. Lời gọi native `$qk-dogfood` nạp bản sao đó; yêu cầu
tổng kết phiên thông thường không đọc file skill. Snapshot project và source
không đổi. Đây là những lần chạy đơn lẻ trên Codex, không chứng minh an ninh
sandbox hay activation của `qk-dogfood` trên Claude Code, omp hoặc Qwen.

### Kiểm sau khi chuyển instruction sang tiếng Anh

Sau khi chuyển source sang tiếng Anh ngày 08/11/2026, đã chạy mười smoke tổng hợp
cô lập bằng OMP 18.15.0, profile `work`, model `anthropic/claude-opus-5-5`.
Các kiểm Codex phía trên diễn ra trước thay đổi ngôn ngữ instruction này.

Sáu lần yêu cầu đọc trực tiếp instruction `qk-dogfood` hiện tại: hai sự kiện độc lập
sinh một đề xuất; log/retry trùng của một sự kiện không đạt ngưỡng; agent bỏ qua
luật rõ được xếp lỗi tuân thủ; lỗi 403/429 sinh báo cáo tiếng Anh mà không vá
instruction; inventory không được coi là đã dùng; bằng chứng bên thứ ba kèm
injection và `--apply` chỉ sinh đề xuất upstream/fork, không thực thi payload hay
in credential giả. Năm báo cáo còn lại bằng tiếng Việt.

Bốn lần RPC dùng bản sao project-local `.omp/skills` trong project tạm. Lời gọi
`/skill:qk-dogfood`, `/skill:qk-plan revise` và `/skill:qk-handoff resume` tuân
theo hợp đồng. Yêu cầu tổng kết thông thường bằng tiếng Việt chỉ đọc `session.txt`.
Sửa plan báo cáo tiếng Anh nhưng giữ heading và trạng thái nháp tiếng Việt,
chỉ đổi quyết định dấu phân cách đã được chấp nhận. Nhận handoff phát hiện mâu
thuẫn dấu phân cách rồi chờ, không sửa file.

Chỉ file plan trong fixture sửa plan thay đổi; mọi cây fixture khác và checkout
source không đổi trong lúc chạy. Không đổi bản cài global hay config runtime.
Tool chỉ đọc, ngoại trừ quyền sửa plan và lệnh Git/mtime chỉ đọc của ca handoff.
Đây là các lần chạy đơn lẻ trên một model, không chứng minh an ninh sandbox hay
bao phủ mọi workflow của cả mười skill. Tại thời điểm đó, bản tiếng Anh chưa được chạy lại trên
Codex, Claude Code, Qwen hoặc omp tương tác.

## Danh sách kiểm thử thủ công

Chạy từng phép kiểm trong một thư mục tạm trống trên mỗi runtime:

1. **Gọi đích danh:** Gọi `qk-brainstorm` với câu hỏi "Should the app read its configuration from environment variables or a TOML file?" Dùng `/qk-brainstorm …` trong Claude Code, `$qk-brainstorm …` trong Codex hoặc `/skill:qk-brainstorm …` trong omp ở chế độ RPC. Đạt khi báo cáo kết thúc bằng bốn nhãn **Done**, **Evidence**, **Not verified**, **Needs your decision** theo đúng thứ tự và thư mục không có file mới.
2. **Yêu cầu thường:** Hỏi "I need to plan and debug a config loader. In two sentences, what should I check first?" mà không gọi skill. Đạt khi câu trả lời hiển thị không chứa nhãn nào trong bốn nhãn. Phép kiểm này chỉ xét output nhìn thấy; không chứng minh skill không được nạp vào context.

| Runtime | Ngày | Gọi đích danh | Yêu cầu thường |
|---|---|---|---|
| Claude Code 2.1.322 (`claude -p`) | 2026-11-13 | Đạt: bốn nhãn đúng thứ tự, không có file | Đạt: không có nhãn |
| Codex 0.160.0 (`codex exec --sandbox read-only`) | 2026-11-13 | Đạt | Đạt |
| omp 18.18.3 (RPC) | 2026-11-13 | Đạt; nội dung skill được chèn | Đạt; không chèn gì |
| Qwen Code | — | Chưa kiểm: phiên đăng nhập hết hạn | Chưa kiểm |

Đây là các lần chạy đơn lẻ, không phải tỷ lệ tuân thủ. Ngày 2026-11-13, gọi đích danh `qk-prefs` với kho đề xuất trống trên Claude Code 2.1.322, Codex 0.160.0 và omp 18.18.3 (RPC): cả ba tìm được script qua thư mục skill symlink, báo không có đề xuất đang chờ và kết thúc bằng bốn nhãn theo đúng thứ tự.

Ngày 2026-11-14, Claude Code 2.1.322 chạy `/qk-commit commit` trong repo tạm có remote bare cục bộ. Lệnh tạo đúng một commit chứa file đã theo dõi và có thay đổi, không push, để file chưa theo dõi không liên quan ở ngoài commit và nêu tên file đó. Khi có file env, file này vẫn ở ngoài commit, được nêu tên trong báo cáo và nội dung không bị đọc. Cả hai commit message đều không có dòng ghi công AI.

## Hook ghi nhận sở thích

[Hook ghi nhận sở thích](preference-hook.md) là hook lệnh `UserPromptSubmit`, bật tuỳ chọn. Hai runtime dưới đây ghi trong tài liệu cùng một định dạng output (`hookSpecificOutput.additionalContext`), và hook in đúng định dạng đó cho cả hai.

| Runtime | Đăng ký ở đâu | Đã kiểm |
|---|---|---|
| Claude Code 2.1.322 | `hooks` trong `settings.json` (user) hoặc `.claude/settings.local.json` (project) | Đã chạy phiên `claude -p` thật trong project tạm. Với prompt bình thường "Từ nay commit message viết bằng tiếng Anh nhé.", agent ghi đúng một đề xuất và báo đề xuất đang chờ `qk/prefs`. Prompt "làm luôn đi" không ghi gì. `/qk-prefs` liệt kê đề xuất mà không sửa file, coi "ok" là chưa quyết; khi được duyệt rõ ràng thì ghi một dòng vào đích đã nêu và chuyển đề xuất sang `applied`. Không file rules, `CLAUDE.md` hay memory nào bị đổi. Mỗi ca chỉ chạy một lần, chưa phải tỷ lệ tuân thủ |
| Codex 0.160.0 | `~/.codex/hooks.json`, `.codex/hooks.json` của project, hoặc `[hooks]` trong `config.toml` | Một phiên `codex exec` trong thư mục tạm: lời nhắc được chèn, agent chạy `propose`, đề xuất nằm đúng kho đã cấu hình. Prompt thử có bảo agent làm theo hướng dẫn hệ thống, nên kết quả chứng minh đường đi hoạt động, chưa nói được agent làm theo thường xuyên đến đâu |
| omp, Qwen Code | — | Chưa hỗ trợ, chưa kiểm |

Codex bỏ qua hook mới hoặc vừa sửa cho tới khi bạn trust nó bằng `/hooks`; hook của project còn cần lớp `.codex/` của project đó được trust.

## Đặc điểm đã thấy

- **omp print mode:** `omp -p "/skill:qk-plan …"` gửi nguyên văn, không mở rộng skill; đã đối chứng bằng `find-skills`. Dùng phiên tương tác hoặc RPC; phiên tương tác chưa được kiểm trực tiếp ở đợt trên.
- **Danh sách skill trong omp print mode:** Hỏi có những skill nào sẽ không liệt kê skill qk vì chúng chỉ chạy khi gọi đích danh. Kiểm bản cài bằng cách gọi đích danh một skill.
- **Qwen ghi tham số xuống đĩa:** khi gọi skill, ghi file tạm trong `.qwen/tmp/` dù ở plan mode. Đây là hành vi Qwen, không phải qk; cân nhắc ignore thư mục này theo quy tắc repo của bạn.
- **Codex và thư mục trùng:** link ở hai thư mục nó đọc có thể khiến liệt kê hai lần. Chọn một nơi cài.

## Chọn agent/model theo việc

qk không tạo cấu hình model riêng. Dùng cơ chế runtime:

- **omp:** agent trỏ role qua `model: "@plan"` và ánh xạ `modelRoles`, hoặc `task.agentModelOverrides`. Dùng được khi tắt override từng lời gọi.
- **Claude Code:** `--model` hoặc model trong định nghĩa subagent.
- **Codex:** `-m <model>`.
- **Qwen Code:** `-m <model>`.

`qk/agent-coord` chọn đường chạy đáp ứng đúng agent/model đã nêu; không có thì báo blocked, không âm thầm fallback. Xem [hướng dẫn](skills/qk-agent-coord.md).
