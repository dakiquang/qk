# qk

[English](README.md) · [Tài liệu](docs/vi/README.md) · [Case study đầu-cuối](docs/vi/case-study-csv-export.md)

Bộ kit cá nhân nhỏ để quyết định bằng bằng chứng, lập plan có phạm vi rõ, triển khai có kiểm chứng và bàn giao đáng tin giữa các phiên AI coding.

qk là **cánh tay mở rộng của Claude Code, Codex và omp**, không thay thế chúng. Skill được cấu hình để chỉ chạy khi gọi đích danh; yêu cầu plan hoặc debug thông thường vẫn do runtime xử lý. Tool, plan mode, subagent, lựa chọn model, quyền native và luật repo giữ nguyên.

> Dự án cá nhân, không liên quan công ty nào, không cam kết hỗ trợ. Repo hiện riêng tư; cần quyền truy cập để cài.

## Chọn skill theo việc

| Skill | Kết quả |
|---|---|
| [qk/brainstorm](docs/vi/skills/qk-brainstorm.md) | 2–4 hướng, đánh đổi và một khuyến nghị |
| [qk/research](docs/vi/skills/qk-research.md) | Câu trả lời cho quyết định, có nguồn và thử nghiệm đối chứng |
| [qk/plan](docs/vi/skills/qk-plan.md) | Tạo, audit hoặc sửa plan kiểm chứng được |
| [qk/cook](docs/vi/skills/qk-cook.md) | Triển khai yêu cầu rõ hoặc plan đã duyệt; kiểm và tự review |
| [qk/debug](docs/vi/skills/qk-debug.md) | Tái hiện, nguyên nhân gốc đã kiểm và đề xuất sửa nhỏ nhất |
| [qk/test](docs/vi/skills/qk-test.md) | Kiểm độc lập, phân loại lỗi và khoảng trống kiểm chứng |
| [qk/handoff](docs/vi/skills/qk-handoff.md) | Lưu ngữ cảnh hoặc nhận lại và kiểm độ lệch |
| [qk/agent-coord](docs/vi/skills/qk-agent-coord.md) | Giao việc có giới hạn cho agent/model bạn nêu, rồi kiểm kết quả |
| [qk/release-notes](docs/vi/skills/qk-release-notes.md) | Nháp release notes/changelog truy được nguồn, chưa đăng |
| [qk/dogfood](docs/vi/skills/qk-dogfood.md) | Đề xuất cải thiện instruction từ bằng chứng, chỉ trong chat; không áp dụng |

Mỗi skill ghi kết quả, quyền và tiêu chí xong. Không pipeline bắt buộc, không tự gọi skill khác. Quyền sửa code không bao gồm commit, push, mở PR, merge, tag, deploy hoặc đăng.

Instruction chuẩn của skill và mẫu prompt cho worker được viết bằng tiếng Anh; tài liệu cho người đọc vẫn có EN/VI. Báo cáo theo ngôn ngữ người dùng, trừ khi người dùng hoặc repo chỉ định khác; khi sửa file đã có thì giữ ngôn ngữ và định dạng của file đó. Không dịch lệnh, đường dẫn, identifier hay chuỗi máy đọc cố định.

Review/chấm điểm PR dùng skill đồng hành [pr-orchestrator](https://github.com/dakiquang/pr-orchestrator), vẫn là repo và bản cài riêng.

## Bắt đầu

[Cài một lần, tạo link từng thư mục skill](docs/vi/getting-started.md), rồi mở phiên runtime mới. Không cần cài package hoặc build.

| Runtime | Ví dụ gọi |
|---|---|
| Claude Code | `/qk-plan audit plans/feature.md` |
| Codex | `$qk-plan audit plans/feature.md` |
| omp | `/skill:qk-plan audit plans/feature.md` (tương tác hoặc RPC) |

`qk/plan` là tên khái niệm, không phải cú pháp CLI nguyên văn. Bản omp đã quan sát không mở rộng `/skill:` trong `omp -p`. Chưa kiểm được thực thi và cơ chế chỉ gọi đích danh của Qwen. Xem [bằng chứng runtime và giới hạn](docs/vi/runtimes.md); một lần chạy thành công không phải chứng nhận.

## Đọc thêm

- [Bắt đầu](docs/vi/getting-started.md): cài, gọi, cập nhật và gỡ an toàn.
- [Quy trình](docs/vi/workflows.md): chọn cách làm theo điều còn thiếu.
- [Case study: xuất CSV từ ý tưởng đến PR được ship](docs/vi/case-study-csv-export.md): prompt, hợp đồng coordinator/worker, PR review và cổng phát hành.
- [Runtime](docs/vi/runtimes.md): ranh giới native, chọn model và hỗ trợ đã quan sát.
- [Changelog](CHANGELOG.md).

## Kiểm tra

```bash
python3 scripts/validate.py
```

Kiểm metadata skill, cấu hình gọi đích danh, link nội bộ, cặp docs EN/VI, đường dẫn cá nhân và chuỗi giống secret. `QK_DENYLIST` tùy chọn trỏ file từ cấm. CI chạy thêm gitleaks trên lịch sử. Kiểm tĩnh không chứng minh cô lập runtime.

## Giấy phép

[MIT](LICENSE). Tác giả [Quang Dang](https://quangdk.com).
