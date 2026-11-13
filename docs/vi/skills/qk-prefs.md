# qk/prefs

[English](../../en/skills/qk-prefs.md) · [Mục lục](../README.md) · [Nguồn skill](../../../skills/qk-prefs/SKILL.md)

## Khi nào dùng

Gọi skill khi bạn muốn xem lại các sở thích lâu dài mà [hook ghi nhận sở thích](../preference-hook.md) đã thu được ("từ nay…", "mặc định…") và quyết từng mục: mục nào thành chỉ dẫn, và ghi vào đâu. Nếu chưa bật hook hoặc không có đề xuất nào đang chờ thì skill không có gì để làm. Bảo agent "nhớ" một điều không kích hoạt skill này.

## Ví dụ đầu vào

```text
/qk-prefs
```

Dùng `$qk-prefs` trong Codex hoặc `/skill:qk-prefs` trong omp (interactive/RPC). Bạn có thể thêm trọng tâm, ví dụ `/qk-prefs chỉ những mục của repo này`.

## Ví dụ một phiên

Khi có hai đề xuất đang chờ, skill hiện bảng kiểu:

| ID | Phạm vi | Tiêu đề | Nội dung | Lời của bạn |
|---|---|---|---|---|
| `2cd33227` | global | Commit message language | Write commit messages in English. | Từ nay commit message viết bằng tiếng Anh |
| `ff6dcbbd` | project `qk` | Test runner | Run `python3 -m unittest discover -s tests` before reporting done. | lần sau nhớ chạy test trước khi báo xong |

Sau khi đọc các file đích, skill gợi ý một đích cho mỗi mục. Ví dụ: quy tắc commit message vào file chỉ dẫn cấp người dùng, quy tắc chạy test vào `AGENTS.md` của repo này. Skill cũng báo nếu file đích đã có quy tắc đó hoặc đang nói ngược lại.

Bạn trả lời bằng lời thường:

```text
Áp dụng 2cd33227 vào ~/.claude/CLAUDE.md. Bỏ ff6dcbbd, README đã ghi rồi.
```

Skill thêm một dòng vào `~/.claude/CLAUDE.md` theo đúng phong cách sẵn có của file, đánh dấu `2cd33227` là applied kèm đích và `ff6dcbbd` là dismissed, rồi báo đúng dòng đã thêm. Chỉ nói "ok" thì chưa phải quyết định; "áp dụng hết" chỉ được tính sau khi bạn đã xem bảng.

## Quyền hạn và khi nào xong

Skill được đọc kho đề xuất qua `scripts/qk_prefs.py` và đọc các file đích ứng viên. Nó chỉ được sửa file đích của mục bạn đã duyệt. Bản sửa phải nhỏ nhất và giữ đúng ngôn ngữ, định dạng của file đích; sửa xong phải đánh dấu bằng `resolve`. Mục bị bỏ chỉ đổi trạng thái, không ghi gì. Mục nào chưa chắc thì để nguyên trạng thái chờ.

Nội dung đề xuất là dữ liệu không tin cậy: skill hiển thị nhưng không làm theo chỉ dẫn nằm bên trong. Nó khuyên bỏ mọi mục trông giống secret hoặc dữ liệu khách hàng. Skill không sửa tay kho đề xuất, không tự ghi sở thích mới, và không commit, push hay publish file đã sửa.

Xong khi mọi mục bạn đã quyết đều có trạng thái mới kèm đích, và báo cáo liệt kê đúng những gì đã ghi. Luật ưu tiên cao hơn, luật runtime và luật repo luôn thắng.
