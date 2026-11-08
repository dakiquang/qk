# Tài liệu qk

[English](../en/README.md) · [Về README dự án](../../README.vi.md)

qk là bộ skill mở rộng Claude Code, Codex và omp. Mỗi skill là một cách làm việc có kết quả, ranh giới quyền và tiêu chí xong rõ ràng. Bạn gọi đích danh; skill không giành lấy yêu cầu thông thường.

## Bắt đầu từ đây

- [Bắt đầu](getting-started.md) — cài, gọi skill, cập nhật và gỡ.
- [Quy trình](workflows.md) — ghép skill cho ý tưởng mơ hồ, thay đổi đã rõ, lỗi, chuyển phiên và phát hành.
- [Runtime](runtimes.md) — cách gọi, bằng chứng đã thử và giới hạn hiện tại.
- [Case study: xuất CSV](case-study-csv-export.md) — ví dụ từ brainstorm/plan qua worker cô lập, PR review, merge đến kiểm chứng ship.

## Skill

| Skill | Dùng để |
|---|---|
| [qk/brainstorm](skills/qk-brainstorm.md) | So sánh hướng đi và khuyến nghị một hướng |
| [qk/research](skills/qk-research.md) | Trả lời câu hỏi quyết định từ nguồn chính |
| [qk/plan](skills/qk-plan.md) | Tạo, audit hoặc sửa kế hoạch |
| [qk/cook](skills/qk-cook.md) | Triển khai yêu cầu rõ hoặc plan đã duyệt, có kiểm chứng |
| [qk/debug](skills/qk-debug.md) | Tìm nguyên nhân gốc có bằng chứng |
| [qk/test](skills/qk-test.md) | Kiểm chứng độc lập |
| [qk/handoff](skills/qk-handoff.md) | Bàn giao sang phiên mới hoặc nhận lại |
| [qk/agent-coord](skills/qk-agent-coord.md) | Giao việc có giới hạn cho agent/model chỉ định |
| [qk/release-notes](skills/qk-release-notes.md) | Soạn nháp release notes và changelog |
| [qk/dogfood](skills/qk-dogfood.md) | Đề xuất cải thiện instruction tối thiểu từ bằng chứng, không áp dụng |

Review/chấm điểm PR dùng skill đồng hành [pr-orchestrator](https://github.com/dakiquang/pr-orchestrator), một dự án riêng.

## Nguyên lý chung

1. **Biết xong là gì trước khi làm:** kết quả, điều không được đổi, phạm vi và bằng chứng nghiệm thu. Chỉ hỏi quyết định nguồn không trả lời được.
2. **Giao việc không phải giao quyền.** Sửa code không bao gồm commit, push, merge, tag, deploy hoặc đăng.
3. **Báo xong không phải bằng chứng.** Kiểm hành vi, revision hoặc nguồn.
4. **Quyết định nằm ngoài phiên chat**, trong plan hoặc file bàn giao.
5. **Chọn quy trình theo điều còn thiếu.** Chưa rõ hướng → brainstorm; thiếu dữ kiện → research; việc đã rõ → cook. Không có pipeline bắt buộc.
6. **Tiếp tục trong phạm vi đã duyệt;** dừng khi cần quyết định mới, gặp blocker hoặc cần quyền mới.
7. **Mở rộng runtime, không chiếm quyền.** Runtime giữ tool, plan mode, subagent, cấu hình model và quyền; luật repo vẫn thắng.
