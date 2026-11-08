---
name: qk-release-notes
description: >-
  Soạn nháp release notes và mục CHANGELOG từ commit, PR và bằng chứng đã kiểm,
  một hoặc hai ngôn ngữ; không tag, không phát hành. Chỉ dùng khi người dùng gọi
  đích danh qk/release-notes (`/qk-release-notes`, `$qk-release-notes`,
  `/skill:qk-release-notes`).
disable-model-invocation: true
---

# qk/release-notes

Đầu vào: khoảng tag (`v0.1.0..HEAD`), danh sách PR, hoặc phiên bản sắp phát hành. Ngôn ngữ mặc định theo repo; yêu cầu song ngữ thì viết cả hai.

| | |
|---|---|
| **Kết quả** | Nháp release notes và/hoặc mục CHANGELOG người dùng duyệt được |
| **Quyền** | Đọc git và PR (chỉ lệnh đọc). Ghi file nháp, hoặc mục `[Unreleased]` của CHANGELOG khi được yêu cầu. Không tạo tag, không `gh release`, không đăng, không đổi phiên bản |
| **Xong khi** | Mỗi dòng truy được về commit hoặc PR; mục "đã kiểm chứng" chỉ chứa điều có bằng chứng thật |

## Cách làm

1. Lấy nguồn: `git log` trong khoảng, PR đã merge, CHANGELOG hiện có. Đọc diff khi tiêu đề commit không đủ nói thay đổi.
2. Nhóm theo người đọc: Thêm mới, Thay đổi, Sửa lỗi, Lưu ý khi nâng cấp (breaking, phụ thuộc, biến môi trường, migration). Bỏ commit nội bộ không ảnh hưởng người dùng.
3. Viết theo hành vi người dùng thấy, không theo tên file.
4. CHANGELOG theo định dạng repo đang dùng (thường Keep a Changelog). Không đổi định dạng sẵn có.
5. Mục "đã kiểm chứng" chỉ ghi kiểm chứng có thật: CI, lệnh đã chạy, thử trên môi trường thật. Không có thì bỏ mục, không suy ra từ việc PR đã merge.
6. Không nhắc tên khách hàng, dữ liệu hay hệ thống nội bộ.

## Báo cáo

Đường dẫn file nháp, các thay đổi bị bỏ (một dòng lý do), điều cần người dùng xác nhận (phiên bản, breaking change). Việc tag và phát hành thuộc quy trình phát hành của repo hoặc chế độ release của `pr-orchestrator`, cần yêu cầu riêng.

## Ranh giới

- Chỉ dẫn cấp cao hơn, luật runtime và luật repo thắng skill này.
- Không đổi model, quyền, hook hay cấu hình. Không tự gọi skill qk khác.
