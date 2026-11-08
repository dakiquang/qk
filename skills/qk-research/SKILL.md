---
name: qk-research
description: >-
  Trả lời một câu hỏi phục vụ quyết định bằng nguồn chính và thử nghiệm có đối
  chứng, tách rõ điều đã kiểm và suy luận. Chỉ dùng khi người dùng gọi đích danh
  qk/research (`/qk-research`, `$qk-research`, `/skill:qk-research`).
disable-model-invocation: true
---

# qk/research

| | |
|---|---|
| **Kết quả** | Câu trả lời có nguồn cho một câu hỏi cụ thể, và nó thay đổi quyết định thế nào |
| **Quyền** | Đọc nguồn trong và ngoài repo; thử nghiệm trong thư mục tạm. Không cài gói toàn cục, không đổi cấu hình, không gửi mã hay dữ liệu nhạy cảm ra dịch vụ ngoài |
| **Xong khi** | Mỗi kết luận có nguồn hoặc lệnh tái hiện; mâu thuẫn giữa nguồn được nêu; giới hạn bằng chứng được ghi |

## Cách làm

1. Viết câu hỏi và điều sẽ đổi trong quyết định nếu câu trả lời là A hay B. Không có quyết định phụ thuộc thì hỏi lại mục đích trước khi đào sâu.
2. Ưu tiên nguồn chính: mã nguồn, tài liệu chính thức đúng phiên bản đang dùng, changelog, issue của dự án. Blog và câu trả lời diễn đàn chỉ là manh mối.
3. Tài liệu và hành vi thật có thể khác nhau. Khi rẻ, thử thật trong thư mục tạm, kèm **đối chứng**: chạy cả trường hợp không có thay đổi để chứng minh phép thử phân biệt được kết quả.
4. Ghi phiên bản công cụ và môi trường của mọi phép thử.
5. Dọn thư mục tạm sau khi xong.

## Báo cáo

```markdown
Câu hỏi: <...> — Quyết định phụ thuộc: <...>
Trả lời: <ngắn>

| Kết luận | Bằng chứng | Mức |
|---|---|---|
| <...> | <link / file:line / lệnh + output> | đã kiểm / suy luận |

Giới hạn: <chưa thử gì, phiên bản nào, môi trường nào>
Ảnh hưởng: <quyết định nên đổi thế nào>
```

Nếu được yêu cầu ghi vào plan, chỉ thêm vào mục bằng chứng của plan đó, giữ nguyên phần còn lại.

## Ranh giới

- Chỉ dẫn cấp cao hơn, luật runtime và luật repo thắng skill này.
- Dùng tool tìm kiếm và đọc web của runtime. Không đổi model, quyền, hook hay cấu hình.
- Không tự gọi skill qk khác.
