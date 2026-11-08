# Mẫu prompt giao việc

Mỗi lần giao dùng một mẫu. Thay phần trong ngoặc nhọn, bỏ dòng không cần. Gửi qua stdin.

## Gói ngữ cảnh chung

```text
Bạn là agent được giao việc. Coordinator ở phiên khác giữ quyết định cuối.

Vai trò: {reviewer | implementer | tester | debugger | advisor}
Repo: {tên hoặc đường dẫn}
Việc: {một câu}
Phạm vi: {file, tính năng, commit hoặc diff}
Không được đổi: {hành vi, API, file}
Tiêu chí xong:
- {điều kiện}

Luật dự án: đọc AGENTS.md, CLAUDE.md và tài liệu đóng góp nếu có trước khi làm.
Giữ kiến trúc và quy ước đặt tên hiện có. Không mở rộng phạm vi.

Quyền: {chỉ đọc | sửa file trong phạm vi, trong worktree {path}}
Không commit, push, comment hay merge trừ khi dòng quyền ở trên cho phép.
Điều kiện dừng: {khi nào dừng và báo thay vì đoán}
Không hỏi hay in secret, credential, token, nội dung .env.
```

## Review chỉ đọc

Thêm vào gói ngữ cảnh:

```text
Review thay đổi, không sửa file, không tạo commit.
Xét: đúng đắn, bảo mật, hồi quy, edge case, test còn thiếu.

Trả về đúng các mục:
1. Verdict: APPROVE hoặc NEEDS_CHANGES
2. Finding theo mức P0, P1, P2
3. Mỗi finding: file:line, vấn đề, hệ quả, cách sửa cụ thể, bạn đã đọc hoặc chạy gì để kết luận
4. Lệnh đã chạy và kết quả
5. Model id thật bạn đang chạy, nếu biết
6. Giả định hoặc câu hỏi

Không coi sở thích style là blocker. Không có finding thì nói đã kiểm những gì.
```

## Triển khai cô lập

```text
Làm việc trong worktree được giao, không ra ngoài nó.
- Chỉ sửa file cần cho phạm vi.
- Không đụng thay đổi không liên quan.
- Không commit trừ khi được yêu cầu.
- Chạy test, lint hoặc kiểm tra phù hợp với thay đổi.

Trả về:
1. Tóm tắt thay đổi
2. File đã đổi và lý do
3. Lệnh đã chạy và kết quả
4. Rủi ro còn lại
5. Danh sách để coordinator kiểm lại
```

## Chẩn đoán

```text
Chẩn đoán trước khi đề xuất sửa. Tái hiện nếu được.
Không sửa file trừ khi dòng quyền cho phép.

Trả về:
1. Trạng thái tái hiện và lệnh
2. Hành vi thấy được so với mong đợi
3. Nguyên nhân gốc kèm file:line
4. Cách sửa nhỏ nhất
5. Cách kiểm sau khi sửa
```

## Sửa tiếp sau review

```text
Coordinator chỉ chấp nhận các điểm sau:
- {file:line} {điểm}

Chỉ xử lý các điểm này trong worktree hiện tại.
Không quay lại điểm đã bị loại, không mở rộng phạm vi, không commit.
Chạy kiểm chứng tập trung, báo file đã đổi và kết quả.
Dừng và hỏi nếu cách sửa mâu thuẫn với luật dự án hoặc tiêu chí xong.
```
