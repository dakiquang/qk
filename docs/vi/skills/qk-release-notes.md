# qk/release-notes

[English](../../en/skills/qk-release-notes.md) · [Mục lục](../README.md) · [Nguồn skill](../../../skills/qk-release-notes/SKILL.md)

## Khi nào dùng

Dùng để chuyển khoảng tag, danh sách PR đã merge hoặc phiên bản sắp ra thành ghi chú cho người dùng. Đây là soạn nháp, không phải lệnh phát hành.

## Ví dụ đầu vào

```text
/qk-release-notes Soạn EN và VI cho v0.1.0..HEAD, lưu plans/release-notes-next.md. Nêu rủi ro nâng cấp, không đổi version, tag hay đăng.
```

Thay bằng khoảng thật trong repo. Muốn sửa changelog thì yêu cầu rõ mục `[Unreleased]`. Không yêu cầu song ngữ thì theo ngôn ngữ repo.

## Nhận được gì

Nhóm theo người đọc: thêm mới, thay đổi, sửa lỗi, lưu ý nâng cấp (breaking, dependency, biến môi trường, migration). Mỗi dòng truy được commit/PR; đọc diff khi tiêu đề không đủ. Commit nội bộ không ảnh hưởng người dùng được bỏ kèm lý do ngắn.

Mục đã kiểm chỉ chứa CI/lệnh/thử runtime có bằng chứng thật. PR merge không chứng minh đã kiểm; không có bằng chứng thì bỏ mục. Giữ định dạng changelog hiện tại và không nêu khách hàng/hệ thống nội bộ.

## Quyền và tiêu chí xong

Đọc Git/PR bằng lệnh chỉ đọc; được ghi nháp hoặc mục `[Unreleased]` đã yêu cầu. Không tăng version, tạo tag, `gh release`, đăng hoặc deploy.

Xong khi nháp truy được nguồn và sẵn cho bạn duyệt, còn quyết định version/breaking được nêu rõ. Phát hành riêng qua quy trình repo hoặc chế độ release của `pr-orchestrator`, cần quyền rõ.

Chỉ dẫn cấp cao hơn, luật runtime và repo luôn thắng. Skill không đổi model, quyền, hook hay cấu hình và không tự gọi skill qk khác.
