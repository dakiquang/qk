# qk/brainstorm

[English](../../en/skills/qk-brainstorm.md) · [Mục lục](../README.md) · [Nguồn skill](../../../skills/qk-brainstorm/SKILL.md)

## Khi nào dùng

Dùng khi chưa chốt hướng đi, không phải khi đã biết chính xác cần triển khai gì. Skill so sánh 2–4 hướng khả thi dựa trên repo và ràng buộc thật; luôn xét hướng đơn giản nhất và phương án không làm hoặc làm thủ công.

## Ví dụ đầu vào

```text
/qk-brainstorm Hai developer cần setup local lặp lại được. So sánh shell script, container và giữ checklist thủ công. Không thêm dịch vụ hosted; ưu tiên chi phí bảo trì thấp.
```

Ví dụ dùng cú pháp Claude Code. Xem [Bắt đầu](../getting-started.md) để đổi sang Codex hoặc omp.

## Nhận được gì

Một câu xác định vấn đề; bảng các hướng với lợi, hại và chi phí quay đầu; giả định then chốt đã kiểm/chưa kiểm; một khuyến nghị và điều kiện khiến khuyến nghị đổi. Hướng vi phạm ràng buộc bị loại kèm lý do. Bạn vẫn là người chọn.

## Quyền và tiêu chí xong

Mặc định chỉ đọc. Chỉ ghi khi bạn yêu cầu và đưa đường dẫn; không triển khai. Xong khi mỗi hướng có đánh đổi cụ thể và giả định kiểm được từ nguồn sẵn có đã được kiểm, không phải khi một hướng nghe có vẻ thuyết phục.

Thiếu dữ kiện quyết định thì tự gọi `qk/research`. Chọn xong hướng thì tự gọi `qk/plan` nếu công việc cần kế hoạch.

Chỉ dẫn cấp cao hơn, luật runtime và repo luôn thắng. Skill không đổi model, quyền, hook hay cấu hình và không tự gọi skill qk khác.
