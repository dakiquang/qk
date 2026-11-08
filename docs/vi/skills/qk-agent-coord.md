# qk/agent-coord

[English](../../en/skills/qk-agent-coord.md) · [Mục lục](../README.md) · [Nguồn skill](../../../skills/qk-agent-coord/SKILL.md)

## Khi nào dùng

Dùng để lấy ý kiến thứ hai, review, triển khai cô lập hoặc chẩn đoán bằng **agent và model bạn chỉ định**. Coordinator giữ quyết định và kiểm chứng; output worker chưa phải sự thật đã kiểm.

## Ví dụ đầu vào

```text
/qk-agent-coord Nhờ Codex model gpt-6.1-sol audit plans/health-endpoint.md theo repo hiện tại. Chỉ đọc, mỗi finding phải có bằng chứng. Không sửa plan hay cài/đổi cấu hình.
```

Thiếu agent/model thì hỏi, không tự chọn. Với việc ghi, nêu phạm vi và tiêu chí xong; worker cần worktree/branch riêng, tích hợp về checkout chính cần bạn đồng ý.

## Hợp đồng chạy

Chọn đường nhỏ nhất có sẵn đáp ứng đúng agent/model và quyền: subagent native có binding phù hợp, terminal Orca quan sát được hoặc CLI headless. Đọc help của CLI đang cài trước khi dựa vào cờ lệnh. omp có thể tắt override model từng lời gọi; agent/role cấu hình sẵn là cách native khác, không phải cớ tự đổi cấu hình.

Không có đường phù hợp, chưa đăng nhập, hết quota hoặc model không có thì báo **blocked** kèm lý do. Không âm thầm đổi model/provider mặc định. Không cài tool, đăng nhập hoặc sửa cấu hình runtime. Xem [mẫu prompt worker](../../../skills/qk-agent-coord/references/prompt-templates.md).

## Cô lập và bằng chứng

Một checkout chỉ một agent ghi. Worktree tránh va chạm Git, không phải sandbox network/credential/filesystem. Việc chỉ đọc lấy giới hạn quyền native làm lớp chính. So revision, status đầy đủ và nội dung tracked/untracked trước/sau là bằng chứng bổ sung, không chứng minh bất biến tuyệt đối: không phủ nội dung file ignored có sẵn hoặc file ngoài repo, cùng các giới hạn khác.

Đổi ngoài dự kiến thì báo, không revert hay stash. Timeout không chứng minh worker đã dừng; chưa biết đã kết thúc thì không giao lại vùng ghi, không tự retry tác động ra ngoài.

## Kết quả và tiêu chí xong

Báo model yêu cầu và model thật (hoặc chưa xác minh), đường chạy/lệnh, output, finding chấp nhận có bằng chứng đã kiểm, finding loại có lý do và trạng thái checkout. Finding review phải tái hiện được, đúng phạm vi. Triển khai phải đọc diff và kiểm chứng liên quan trước khi đề xuất tích hợp. Hai model đồng ý không thay cho bằng chứng.

Xong khi output đã được coordinator phân loại độc lập. Đường chạy bị chặn phải báo blocked, không báo giao thành công. Bạn quyết tích hợp hoặc lời gọi tiếp theo.

Chỉ dẫn cấp cao hơn, luật runtime và repo luôn thắng. Skill không đổi model, quyền, hook hay cấu hình và không tự gọi skill qk khác.
