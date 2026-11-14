# Tài liệu qk

[English](../en/README.md) · [Về README dự án](../../README.vi.md)

qk là bộ skill mở rộng Claude Code, Codex và omp. Mỗi skill là một cách làm việc có kết quả, ranh giới quyền và tiêu chí xong rõ ràng. Bạn gọi đích danh; skill không giành lấy yêu cầu thông thường.

## Bắt đầu từ đây

- [Triết lý](philosophy.md): ý tưởng lõi và ba nguyên tắc đứng sau mọi skill.
- [Bắt đầu](getting-started.md): cài, gọi skill, cập nhật, cố định bản phát hành, gỡ.
- [Quy trình](workflows.md): ghép skill cho ý tưởng mơ hồ, thay đổi đã rõ, lỗi, chuyển phiên và phát hành.
- [Case study: xuất CSV](case-study-csv-export.md): một tính năng mẫu từ brainstorm và plan qua worker cô lập, PR review, merge đến ship.

## Hướng dẫn

- [Runner qk-run](runner.md): tự động hoá tuỳ chọn từ yêu cầu đến PR ready-for-review, với một cổng duyệt plan.
- [qk-eval](evals.md): kiểm trước/sau chấm bằng code khi bạn sửa một skill hoặc bước review của runner.
- [Hook ghi nhận sở thích](preference-hook.md): hook tuỳ chọn biến câu "từ nay…" thành đề xuất chờ bạn duyệt.
- [Thiết lập gọn nhẹ](lean-setup.md): đo và cắt bớt phần runtime nạp vào mỗi phiên, dùng chung với các bộ skill khác.

## Tham khảo

- [Runtime](runtimes.md): mức hỗ trợ, thiết lập chỉ-gọi-đích-danh, nơi đăng ký hook, đặc điểm đã thấy và cách chọn model.
- [Bằng chứng kiểm thử](evidence.md): bản ghi theo ngày về những gì đã kiểm, trên phiên bản nào, kèm checklist kiểm thủ công.

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
| [qk/prefs](skills/qk-prefs.md) | Duyệt đề xuất sở thích đã ghi và áp dụng mục bạn đồng ý |
| [qk/commit](skills/qk-commit.md) | Commit đúng phạm vi; chỉ push và mở PR khi được yêu cầu |

Review/chấm điểm PR dùng skill đồng hành [pr-orchestrator](https://github.com/dakiquang/pr-orchestrator), một dự án riêng.

## Nguyên tắc

**Đủ hiểu để quyết.** Mọi skill theo ba nguyên tắc: tách ba vai (làm, kiểm, quyết), bằng chứng thay cho lời khẳng định, và kiểm vừa đủ. Trang [triết lý](philosophy.md) giải thích từng nguyên tắc.
