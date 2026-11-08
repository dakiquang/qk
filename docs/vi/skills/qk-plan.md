# qk/plan

[English](../../en/skills/qk-plan.md) · [Mục lục](../README.md) · [Nguồn skill](../../../skills/qk-plan/SKILL.md)

## Khi nào dùng

Dùng trước thay đổi cần chốt phạm vi, quyết định và tiêu chí xong kiểm được. Việc nhỏ có plan ngắn; chỉ chia giai đoạn khi độ phức tạp thật sự cần.

## Chế độ và ví dụ

```text
/qk-plan create Thêm health endpoint. Không yêu cầu đăng nhập, không lộ secret, theo quy ước repo.
/qk-plan audit plans/health-endpoint.md
/qk-plan revise plans/health-endpoint.md Áp các finding tôi đã chấp nhận trong chat; giữ nguyên phạm vi.
```

`create` là mặc định khi chưa có plan: ghi `plans/<slug>.md` hoặc nơi repo quy định, không ghi đè plan cũ khi chưa được yêu cầu. `audit` đối chiếu với nguồn hiện tại, không sửa file. `revise` chỉ áp quyết định/finding bạn đã chấp nhận và loại mâu thuẫn trong toàn plan.

## Nhận được gì

Mục tiêu và ngoài phạm vi, hiện trạng có bằng chứng, quyết định và hướng đã bác, giao diện/file dự kiến, các bước có tiêu chí xong, kiểm chứng, rủi ro và câu hỏi mở. Khẳng định có nguồn hoặc nhãn suy đoán. Finding audit gồm mức `blocker`/`important`/`nit`, vị trí, bằng chứng và đề xuất; lo ngại chưa có bằng chứng là câu hỏi, không phải lỗi.

## Quyền và tiêu chí xong

Chỉ được ghi file plan. Không sửa code sản phẩm, cài đặt hay tự triển khai. Quyết định quan trọng không tìm được từ nguồn thì hỏi một lần, không đoán. Báo đường dẫn, thay đổi và điều còn cần quyết.

Xong khi bạn có thể duyệt một plan có phạm vi rõ và mỗi tiêu chí xong đều kiểm được. Duyệt plan không cấp quyền commit, push, merge hay phát hành. Sau khi duyệt, bạn tự gọi `qk/cook <path>`.

Chỉ dẫn cấp cao hơn, luật runtime và repo luôn thắng. Skill không đổi model, quyền, hook hay cấu hình và không tự gọi skill qk khác.
