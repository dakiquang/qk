# Sổ bằng chứng và CLI `qk`

[English](../en/ledger.md) · [Mục lục](README.md) · [CLI](../../scripts/qk.py) · [Kho lưu](../../scripts/qk_ledger.py)

Sổ gom bằng chứng đứng sau một quyết định về một nơi trên máy. Nó không phải hệ thống bộ nhớ thứ hai hay quyền merge. `qk brief` sắp xếp run theo quy tắc cố định được in ra, không phải điểm số hay phán đoán của model. Không có daemon, hook mới hoặc instruction tự nạp vào runtime.

## Cài từ bản clone

Trình cài skill chỉ chép thư mục skill, không kèm CLI. Giữ một bản clone qk và đưa lệnh vào shell không tương tác mà agent dùng:

```bash
mkdir -p ~/.local/bin
ln -s /path/to/qk/scripts/qk.py ~/.local/bin/qk
qk --help
```

Chọn đích chưa tồn tại; không ghi đè lệnh khác. Đưa `~/.local/bin` vào `PATH` của agent. Alias dùng được trong terminal tương tác của bạn nhưng có thể không tồn tại trong shell của agent. Cần Python 3.9+; sync PR còn cần `gh` đăng nhập tài khoản có quyền đọc repo. Script runner và eval cũ vẫn dùng được.

Bắt đầu bằng `qk show --help`, `qk sync --help` hoặc `qk brief --help`. `qk run --help` và `qk eval --help` chuyển tới [runner](runner.md) và [bộ đo](evals.md) hiện có.

## Nơi lưu và dữ liệu riêng

Sổ là `ledger.jsonl` trong `$QK_STATE_DIR`, hoặc `$XDG_STATE_HOME/qk`, hoặc `~/.local/state/qk`. Để ngoài mọi repo, kể cả repo riêng. Bản ghi nằm trên máy và file chỉ dành cho user hiện tại. Bằng chứng gốc của run/eval vẫn ở thư mục state cũ; tham chiếu có thể mất hiệu lực khi bạn xoá hoặc di chuyển chúng.

Sổ chỉ giữ tóm tắt và tham chiếu, không chép code, diff, prompt hay log thô. Mỗi lượt kiểm chỉ lưu vị trí và mã thoát; nội dung lệnh vẫn nằm trong `state.json` của run được tham chiếu. Tên repo, đường dẫn và claim vẫn có thể là dữ liệu riêng. Không công bố sổ. Dùng `qk stats --public` để lấy số đếm tổng hợp không mang nhãn riêng tuỳ ý; vẫn đọc lại trước khi công bố.

Dòng cuối bị ghi dở do crash hoặc đầy đĩa sẽ khiến các lần đọc và ghi sau cố ý báo lỗi; `qk-run` và `qk_eval` chỉ ghi cảnh báo ledger. Để khôi phục, bảo đảm không có lệnh `qk-run`, `qk_eval` hay `qk` nào đang chạy, sao chép `ledger.jsonl` thành bản sao lưu, chỉ xoá dòng cuối chưa hoàn chỉnh, rồi chạy `qk show` để xác nhận file đọc được trở lại.

`source` cho biết ai tạo nội dung; `recorded_by` cho biết ai thu nhận. Finding vẫn do model tạo dù runner ghi lại. `claim` là kết luận chưa được kiểm của model về sự kiện đã có, không phải quan sát mới. Giao diện `log` chỉ nhận claim; đây là ranh giới giao diện, không chống tiến trình khác có cùng quyền user sửa sổ. Code thu nhận một nhận định không chứng minh nhận định đó đúng.

## Lessons

Lesson là quy tắc về sai sót AI có bằng chứng, lưu ở đây dưới dạng bản ghi `lesson` và chỉ được bật sau khi lần đo cho thấy có ích. Xem [Lesson](lessons.md).

## Dùng bằng chứng để quyết

- `qk sync --backfill` nạp run đã dừng và mọi lượt eval đã lưu từ các thư mục state mà không ghi trùng (lượt chạy lại trước đó lấy điểm từ `check.json`, để thời gian và tổng token không còn dữ liệu ở trạng thái chưa biết), đồng thời cảnh báo một dòng cho mỗi thư mục eval thiếu hoặc sai kết quả.
- `qk sync` chỉ ghi snapshot PR có thay đổi, báo số đã ghi và không đổi, đồng thời giữ thời điểm sync trong `qk brief` ở lần quan sát thấy thay đổi gần nhất. Lệnh chỉ đọc GitHub, không merge, đóng hay comment. Chọn đúng tài khoản qua `GH_TOKEN` cho từng lệnh nếu cần; CLI không đổi tài khoản đang active.
- `qk brief` chỉ đọc bằng chứng cục bộ, không gọi mạng và chỉ in ra, trừ khi cả stdin lẫn stdout là terminal. Trên terminal, lệnh hỏi sau mỗi thẻ: `[y] merge  [n] leave  [d] diff  [s] skip`, hoặc `[a] abort later  [r] resume later  [s] skip` với run bị chặn. `y` đọc lại HEAD của PR bằng `gh`, từ chối khi HEAD khác commit đã ghi, và merge với `--match-head-commit`; merge bị từ chối hoặc thất bại thì không ghi gì. `a` và `r` chỉ ghi ý định, không resume hay abort run. Mọi lựa chọn trừ `s` và `d` được ghi thành `decision` với `source=user`, được `qk stats` đếm là `user_decision`, tách khỏi snapshot sync.
- `qk decide RUN_ID CHOICE [--method M]` ghi một trong các quyết định đó khi không có terminal, cho thẻ mà brief sẽ hiện, với cùng các bước kiểm khi merge; `elapsed_s` để trống.
  Đọc thời điểm sync. Bằng chứng đã cũ khi HEAD của PR khác commit đã ghi; thiếu sync hoặc commit không có nghĩa là an toàn.
  Bao gồm run bị chặn, kèm lệnh resume và abort; dòng lý do được đọc từ `state.json` cục bộ của run, vì sổ chỉ lưu bước bị chặn. Thẻ được xếp theo mức high, medium rồi low.
  - High: bị chặn, còn finding blocker hoặc important (nit không tính; bản ghi cũ không có mức thì tính mọi finding), mã thoát kiểm tra khác 0, hoặc file nhạy cảm (CI, dependency, hạ tầng, migration, xác thực, bí mật, phân quyền hay chính sách).
  - Medium: có vòng sửa, hơn 300 dòng thay đổi hoặc 10 file, HEAD của PR khác commit đã ghi, chưa sync, hoặc chưa biết phạm vi.
  - Low: không khớp quy tắc nào; quy tắc khớp được in cạnh mức. Các quy tắc này không cấp quyền phê duyệt.
- `qk log claim --about ID --text "Một kết luận"` gắn kết luận model vào sự kiện có sẵn. Lấy ID từ `qk show --json`, không tự đặt. Ghi qua skill vẫn phải nằm trong quyền ghi của phiên hiện tại.

Claim mới kế thừa nhãn repo và loại việc của sự kiện được tham chiếu, kể cả khi sự kiện đó là claim khác. Vì vậy bộ lọc repo/loại việc giữ các quan sát liên quan cùng nhau. Không ghi lại bản ghi cũ trong sổ chỉ-thêm; claim cũ có nhãn trống vẫn chưa được phân loại.

Brief gọn tổng hợp mã thoát thành zero/nonzero/unknown và chỉ xem trước một phần claim. Dùng ID bản ghi với `qk show` để đọc đủ bằng chứng; `queued-for-fix` không có nghĩa là đã sửa đúng.

Lịch sử đếm run `done`, không đếm thay đổi đã chứng minh đúng. PR đã merge là hành động của người được quan sát, không chứng minh hết lỗi. Run cũ thiếu lịch sử review đầy đủ; finding không xuất hiện ở vòng sau chưa chứng minh đã sửa đúng. Bản ghi eval giữ mọi lượt thử, kể cả lượt đầu làm phát sinh lần chạy lại.

[Test kho lưu](../../tests/test_qk_ledger.py) và [test CLI](../../tests/test_qk_cli.py) sở hữu các kiểm tra lưu trữ và ranh giới quyết định. Kết quả smoke runtime nằm ở [Bằng chứng kiểm thử](evidence.md), không phải cam kết hỗ trợ.
