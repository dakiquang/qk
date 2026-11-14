# Triết lý

[English](../en/philosophy.md) · [Mục lục](README.md)

> **Đủ hiểu để quyết.** Code chạy giờ đã dễ; thứ còn khó là người dùng thấy rõ để quyết định. qk chỉ tối ưu cho việc đó.

Phần lớn bộ kit giúp AI tự làm được nhiều việc hơn, hoặc thêm một lớp điều phối bên trên agent. qk đi hướng khác: mỗi skill làm một việc rồi trả lại cho bạn những gì cần để quyết, không hơn.

## Ba nguyên tắc

| # | Nguyên tắc | Nghĩa là | Không có nghĩa là |
|---|---|---|---|
| 1 | **Tách ba vai: làm, kiểm, quyết** | Bên làm không là bên kiểm cuối cùng của chính việc mình làm. Quyền commit, push, merge, tag, deploy hay phát hành thuộc về bạn, và không truyền sang phiên khác. Gặp quyết định mới hoặc cần quyền mới thì dừng lại hỏi | Việc nào cũng cần hai model. Việc nhỏ, dễ quay lui thì một lệnh kiểm chạy được đã là bên kiểm |
| 2 | **Bằng chứng, không lời khẳng định** | Biết thế nào là xong trước khi bắt đầu. Báo cáo tách điều đã thấy (lệnh đã chạy, file đã đọc), điều bên khác đã xét, và điều mới chỉ nghe nói; phần chưa kiểm được nói ra. Quyết định được ghi vào plan hay file bàn giao, không chỉ nằm trong chat | Mọi câu đều phải kèm chứng cứ. Chỉ kết luận dùng để quyết mới cần |
| 3 | **Vừa đủ** | Chỉ kiểm điều có thể làm đổi quyết định, mỗi điều một lần, bằng cách rẻ nhất đủ tin; dùng lại điều đã thấy trong phiên; phần còn lại ghi là chưa kiểm rồi đi tiếp. Tối đa một vòng review và một vòng sửa; còn bất đồng thì đưa bạn quyết. Chọn quy trình theo điều còn thiếu, không có pipeline bắt buộc. Bộ kit giữ nhỏ, không nạp gì thường trực, và để runtime giữ tool, model, quyền cùng luật repo | Bỏ qua việc kiểm. Điều làm đổi quyết định thì vẫn phải được thấy |

Nguyên tắc 3 là phanh của hai nguyên tắc đầu: tách vai và đòi bằng chứng mà không có giới hạn thì sẽ thành kiểm đi kiểm lại, tốn token mà không thêm hiểu biết.

Mọi báo cáo kết thúc bằng bốn dòng theo đúng thứ tự: **Đã làm**, **Bằng chứng**, **Chưa kiểm chứng**, **Cần bạn quyết định**. Dòng cuối là chỗ duy nhất bạn buộc phải đọc.

## Vai của từng skill

| Vai | Skill |
|---|---|
| Đưa lựa chọn và bằng chứng, không tự chọn | [brainstorm](skills/qk-brainstorm.md), [research](skills/qk-research.md) |
| Làm | [cook](skills/qk-cook.md), [plan](skills/qk-plan.md) (create, revise), [release-notes](skills/qk-release-notes.md) |
| Kiểm | [test](skills/qk-test.md), [plan](skills/qk-plan.md) (audit), [debug](skills/qk-debug.md), [dogfood](skills/qk-dogfood.md) |
| Chuyển giao việc, không chuyển quyền | [handoff](skills/qk-handoff.md), [agent-coord](skills/qk-agent-coord.md) |
| Thực thi quyền bạn đã cấp | [commit](skills/qk-commit.md), [prefs](skills/qk-prefs.md) |

Skill không gọi nhau; mỗi skill nêu lệnh tiếp theo để bạn tự quyết có chạy hay không.

## Khi muốn tự động hơn

[`qk-run`](runner.md) nối các vai cho một việc: một agent làm, runner tự chạy lệnh kiểm của plan, một model khác họ review, tối đa một vòng sửa, rồi mở PR. Bạn duyệt plan ở đầu và tự merge ở cuối. Lớp tự động nào thêm sau này cũng giữ đúng ba nguyên tắc trên: được tự động việc làm và việc kiểm, không tự động việc quyết.

## Ghi chú

Khung này hình thành từ thói quen làm việc hằng ngày: ghi rõ cái gì đã làm, cái gì đã kiểm, cái gì còn là giả thuyết. Về sau mới nhận ra nó trùng với vài ý trong đạo Phật: nghe, xét rồi tự thấy; nói đúng sự thật và nói rõ điều chưa biết; không thái quá về bên nào.
