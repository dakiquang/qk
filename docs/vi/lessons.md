# Lesson: quy tắc về sai sót AI, đo trước khi dùng

[English](../en/lessons.md) · [Mục lục](README.md) · [CLI](../../scripts/qk.py) · [Store](../../scripts/qk_ledger.py)

Lesson là một câu mệnh lệnh, viết ra sau khi agent AI mắc cùng một lỗi ít nhất hai lần. Lesson nằm trong [sổ bằng chứng](ledger.md) dưới dạng bản ghi `lesson` chỉ ghi nối tiếp; bản ghi mới nhất của một ID là trạng thái hiện tại. Lesson chỉ đến được agent khi bạn truyền `--lessons`, và chỉ sau khi một lần đo cho thấy nó có ích.

## Vì sao phải đo trước

Viết quy tắc thì rẻ; biết nó có tác dụng hay không thì không. Một nghiên cứu [được dẫn ở đây](https://levelup.gitconnected.com/stop-teaching-your-ai-agent-the-wrong-lessons-c1a6c980e713) thấy tệp chỉ dẫn do máy viết không nâng đáng kể tỉ lệ giải việc trên hai benchmark mà còn tăng chi phí suy luận 20–23% (chúng tôi chưa đọc bài gốc; kết quả chỉ áp dụng cho các agent và việc trong nghiên cứu đó). Tính năng ghi nhớ và học ở các công cụ khác kiểm lesson còn khớp với code, hoặc để người duyệt, nhưng chưa bên nào chúng tôi tìm được đo xem lesson có làm agent bớt sót hay không trước khi bật.

qk đo việc đó bằng công cụ sẵn có: một [eval case](evals.md) chấm bằng code tái hiện lỗi, chạy có và không có lesson. Lesson không giúp là một kết quả hợp lệ, không phải quy trình thất bại.

[Lesson đầu tiên](evidence.md#bài-học-đầu-tiên) của qk là ví dụ: trên Codex, có lesson sót 1/2 lượt, không có lesson cũng sót 1/2, nên đã bị dismiss.

## Vòng đời

| Bước | Lệnh | Ai làm |
|---|---|---|
| Tìm lỗi lặp lại | `qk lesson suggest` (chỉ đọc) | code |
| Đề xuất | `qk lesson propose --class TEXT --rule TEXT --scope stage:review --evidence ID --evidence ID --case NAME` | model hoặc người; ghi `source: model` |
| Đo | `qk lesson measure ID --runtime SPEC` | code; ghi `source: code` |
| Bật hoặc bỏ | `qk lesson decide ID active` hoặc `dismissed` | bạn; ghi `source: user` |
| Dùng | `qk run start --lessons`, `qk eval --lessons` | bạn chọn theo từng lượt |
| Gỡ hoặc nâng | `qk lesson decide ID retired` hoặc `promoted` | bạn |
| Xem | `qk lesson list` | ai cũng được |

Một đề xuất cần:

- `rule`: một dòng, tối đa 300 ký tự, nói agent phải làm gì. Viết thói quen chung, đừng viết đáp án của eval case, nếu không lần đo chỉ chứng minh agent biết chép gợi ý.
- `scope`: 1–3 mục, ít nhất một trong `stage:review`, `stage:impl`, `stage:plan`; thêm `repo:TÊN` để giới hạn trong một repo.
- `evidence`: ít nhất hai ID `eval` hoặc `finding` khác nhau đã có trong sổ, nơi lỗi xảy ra.
- `case`: một thư mục có sẵn trong `evals/cases/` tái hiện lỗi.

## Lần đo quyết định thế nào

`qk lesson measure` chạy case của lesson 2 lần không có và 2 lần có lesson, rồi mỗi case khác cùng bước 1 lần có lesson để đối chứng. Đối chứng được so với baseline của runtime; khi baseline chưa có mục cho runtime đó, 1 lần chạy không có lesson thay vào. Tiêu chí đích là các tiêu chí mà bằng chứng của lesson đã trượt trên case đó.

Lesson chỉ được coi là có ích khi:

- cả 2 lần có lesson đều đạt mọi tiêu chí đích;
- ít nhất 1 lần không có lesson trượt một tiêu chí đích;
- không case đối chứng nào mất tiêu chí hay vượt luật token (vượt cả 10% lẫn 25.000 token).

Kết luận, lý do và mọi ID eval được ghi nối tiếp vào sổ. Hai lần chạy mỗi ô là bằng chứng mỏng; đọc lý do và câu trả lời trong thư mục kết quả trước khi quyết.

## Bật một lesson

`qk lesson decide ID active` bị từ chối trừ khi lần đo mới nhất chưa quá 60 ngày và cho thấy lesson có ích. Chuyển trạng thái được phép: proposed → active hoặc dismissed, rồi active → retired hoặc promoted.

Lesson active vẫn chỉ được nạp khi bạn yêu cầu: `--lessons` thêm tối đa 5 lesson active đúng bước của lượt đó (và đúng repo, nếu có ghi), tổng khoảng 800 token. Không có cờ thì prompt giữ nguyên từng byte. State của runner và kết quả eval ghi lại ID các lesson đã dùng.

## Gỡ hoặc đo lại

- `qk lesson decide ID retired` dừng nạp lesson. Bản ghi không bao giờ bị xoá; lịch sử còn nguyên.
- Lesson active có lần đo có ích gần nhất quá 60 ngày được gắn nhãn `needs-remeasure` trong `qk lesson list` và bị `--lessons` bỏ qua cho tới khi đo lại.
- Lesson có eval case đã bị xoá thì bị bỏ qua.
- `promoted` ghi nhận quy tắc nay đã nằm ở chỗ được ép buộc (test, kiểm tra trong runner hay một dòng skill); bạn làm thay đổi đó trong một PR bình thường.

CLI ghi lại ai nó cho là đã thao tác, nhưng không chứng minh được ai đã chạy lệnh. [Test của store](../../tests/test_qk_ledger.py) và [test eval](../../tests/test_qk_eval.py) giữ các kiểm tra cho những luật này.
