# qk

[English](README.md) · [Tài liệu](docs/vi/README.md) · [Changelog](CHANGELOG.md)

Bộ agent skill cho Claude Code, Codex và omp, thêm một nhóm nhỏ cách làm việc có kỷ luật lên runtime bạn đang dùng: so sánh hướng đi, lập plan, triển khai có kiểm chứng, debug, kiểm thử, bàn giao giữa các phiên, phối hợp với model thứ hai, commit và soạn nháp release notes.

qk mở rộng runtime, không thay thế nó. Mỗi skill chỉ chạy khi bạn gọi đích danh, theo thiết lập đã kiểm trên Claude Code, Codex và omp. Yêu cầu thường, plan mode, subagent, cấu hình model, quyền và luật repo vẫn do runtime giữ.

> **Trạng thái.** Dự án cá nhân, không liên quan tới công ty nào, công bố nguyên trạng. Tác giả duy trì cho công việc của chính mình và đánh phiên bản bằng tag, nhưng không cam kết hỗ trợ. Issue và pull request đều được đón nhận; không hứa sẽ phản hồi.

## Vì sao có qk

Agent lập trình làm tốt việc tạo ra thay đổi, nhưng kém ổn định ở các bước xung quanh: thống nhất thế nào là xong, chứng minh điều đó, và không coi quyền sửa code là quyền phát hành. qk viết các bước đó thành những quy trình ngắn, gọi đích danh.

- **Mỗi skill nêu rõ kết quả, quyền hạn và khi nào là xong.** Sửa code không bao giờ kéo theo commit, push, merge, tag, deploy hay publish.
- **Báo cáo không phải bằng chứng.** Skill kiểm hành vi hoặc nguồn, và nói rõ phần nào chưa kiểm.
- **Không có pipeline.** Skill không gọi nhau; mỗi skill nêu lệnh tiếp theo và bạn quyết định có chạy hay không.
- **Mọi báo cáo kết thúc giống nhau:** Đã làm, Bằng chứng, Chưa kiểm chứng, Cần bạn quyết định.
- **Cố ý giữ nhỏ.** Bộ kit dừng ở mười hai skill và khoảng 50 KB instruction. Muốn thêm skill thì phải thay hoặc gộp một skill.

## Skill

| Skill | Kết quả |
|---|---|
| [qk/brainstorm](docs/vi/skills/qk-brainstorm.md) | Hai đến bốn hướng đi, đánh đổi của từng hướng và một khuyến nghị |
| [qk/research](docs/vi/skills/qk-research.md) | Câu hỏi quyết định được trả lời từ nguồn chính và thí nghiệm có đối chứng |
| [qk/plan](docs/vi/skills/qk-plan.md) | Plan được tạo, audit hoặc sửa, với tiêu chí xong kiểm được |
| [qk/cook](docs/vi/skills/qk-cook.md) | Yêu cầu rõ hoặc plan đã duyệt được triển khai, kiểm chứng và tự review |
| [qk/debug](docs/vi/skills/qk-debug.md) | Cách tái hiện, nguyên nhân gốc đã kiểm và cách sửa nhỏ nhất được đề xuất |
| [qk/test](docs/vi/skills/qk-test.md) | Kiểm độc lập, phân loại lỗi và chỉ ra chỗ chưa kiểm |
| [qk/handoff](docs/vi/skills/qk-handoff.md) | Lưu ngữ cảnh phiên, hoặc nhận lại kèm kiểm độ lệch |
| [qk/agent-coord](docs/vi/skills/qk-agent-coord.md) | Một việc có giới hạn chạy trên đúng agent và model bạn nêu, kết quả được kiểm |
| [qk/commit](docs/vi/skills/qk-commit.md) | Commit đúng phạm vi; chỉ push và mở PR khi được yêu cầu, sau bước kiểm account |
| [qk/release-notes](docs/vi/skills/qk-release-notes.md) | Nháp release notes và changelog truy được nguồn, không bao giờ tự đăng |
| [qk/dogfood](docs/vi/skills/qk-dogfood.md) | Đề xuất cải thiện instruction dựa trên bằng chứng, không bao giờ tự áp dụng |
| [qk/prefs](docs/vi/skills/qk-prefs.md) | Duyệt từng đề xuất sở thích đã ghi; chỉ ghi những mục được duyệt |

Hai công cụ tuỳ chọn đi kèm:

- **[qk-run](docs/vi/runner.md)** đưa một việc từ yêu cầu tới pull request ready-for-review: một cổng duyệt plan, chạy lệnh kiểm của chính plan, review bởi một họ model khác, và không bao giờ merge.
- **[Hook ghi nhận sở thích](docs/vi/preference-hook.md)** biến câu "từ nay…" thành đề xuất để bạn duyệt bằng `qk/prefs`.

Review và chấm điểm pull request nằm ở dự án đồng hành [pr-orchestrator](https://github.com/dakiquang/pr-orchestrator).

## Bắt đầu nhanh

Cài cho các runtime bạn dùng bằng một lệnh (cần Node.js):

```bash
npx skills add dakiquang/qk -g -a claude-code codex qwen-code -y
```

[Bắt đầu](docs/vi/getting-started.md) có cách cố định bản phát hành, cập nhật, gỡ, và cách cài thủ công không cần Node.js. Sau đó mở phiên mới và gọi một skill:

| Runtime | Ví dụ |
|---|---|
| Claude Code | `/qk-brainstorm Should the app read its configuration from environment variables or a TOML file?` |
| Codex | `$qk-brainstorm …` |
| omp | `/skill:qk-brainstorm …` (đã kiểm ở chế độ RPC; chế độ tương tác chưa kiểm) |

Tài liệu ghi tên skill dạng `qk/brainstorm`; đó là tên quy trình, không phải lệnh để gõ. Mức hỗ trợ khác nhau theo runtime và Qwen Code chưa được kiểm; xem [Runtime](docs/vi/runtimes.md).

## Tài liệu

- [Bắt đầu](docs/vi/getting-started.md): cài, gọi, cập nhật, cố định bản phát hành, gỡ.
- [Quy trình](docs/vi/workflows.md): dùng skill nào cho ý tưởng mơ hồ, thay đổi đã rõ, lỗi, chuyển phiên hoặc phát hành.
- [Case study](docs/vi/case-study-csv-export.md): một tính năng từ ý tưởng tới pull request đã merge.
- [Runtime](docs/vi/runtimes.md) và [Bằng chứng kiểm thử](docs/vi/evidence.md): mỗi runtime hỗ trợ gì và thực tế đã kiểm những gì.
- [Mục lục đầy đủ](docs/vi/README.md).

Instruction của skill viết bằng tiếng Anh. Tài liệu cho người đọc có cả tiếng Anh và tiếng Việt. Báo cáo theo ngôn ngữ bạn dùng.

## Kiểm tra

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests
```

Validator kiểm metadata của skill, thiết lập gọi đích danh, link nội bộ, cặp trang tiếng Anh và tiếng Việt, đường dẫn cá nhân và chuỗi giống secret; kiểm tĩnh không chứng minh runtime cô lập skill; các giới hạn khác nằm ở [Bắt đầu](docs/vi/getting-started.md#6-kiểm-bộ-kit). CI chạy cả hai lệnh và quét gitleaks.

## Giấy phép

[MIT](LICENSE). Tác giả: [Quang Dang](https://quangdk.com).
