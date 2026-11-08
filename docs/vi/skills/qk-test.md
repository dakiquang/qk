# qk/test

[English](../../en/skills/qk-test.md) · [Mục lục](../README.md) · [Nguồn skill](../../../skills/qk-test/SKILL.md)

## Khi nào dùng

Dùng để kiểm độc lập hoặc rộng hơn: trước merge, sau thay đổi của agent khác hoặc ở môi trường khác. Không thay kiểm chứng trong cook và không bắt buộc sau mọi thay đổi.

## Ví dụ đầu vào

```text
/qk-test Kiểm thay đổi health endpoint hiện tại. Tìm lệnh từ repo, chạy kiểm tập trung trước rồi bộ liên quan rộng hơn. Không sửa code hay cài dependency.
```

## Nhận được gì

Bảng lệnh thật, exit code và kết quả; lỗi mới, baseline có bằng chứng, kết quả chập chờn và hành vi/môi trường chưa kiểm. CI từ xa ghi là CI, không nhận thành chạy local.

Tìm lệnh từ docs repo, CI và script manifest, không mặc định package manager. Chỉ kết luận baseline khi có bằng chứng CI base hoặc worktree base tạm đã được cho phép. Không có bằng chứng thì ghi chưa biết baseline. Lỗi chập chờn chạy lại tối đa hai lần, giữ mọi kết quả; pass về sau không xoá lần lỗi đầu.

## Quyền và tiêu chí xong

Chỉ chạy kiểm của repo; không sửa code, cấu hình test, cài dependency mới hay commit. Tiến trình test có thể sinh output bình thường; đây không phải sandbox bất biến filesystem.

Xong khi kết quả/phân loại có bằng chứng và kiểm bị chặn có lý do. Muốn đào nguyên nhân lỗi thì tự gọi `qk/debug`; không nới assertion hoặc đổi cấu hình cho xanh.

Chỉ dẫn cấp cao hơn, luật runtime và repo luôn thắng. Skill không đổi model, quyền, hook hay cấu hình và không tự gọi skill qk khác.
