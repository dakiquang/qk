# Case study: xuất trang task hiện tại ra CSV

[English](../en/case-study-csv-export.md) · [Mục lục](README.md) · [Quy trình](workflows.md)

Đây là **ví dụ triển khai xuyên suốt**, không phải báo cáo tính năng đã ship trong repo này. qk chứa skill, không chứa app quản lý task. App, tên file, số PR và tính năng dưới đây là minh hoạ; khi áp dụng phải thay bằng dữ kiện tìm được từ repo thật. Không có điểm review, output test, URL PR hoặc kết quả deploy giả được trình bày như đã chạy.

Mục tiêu là một vòng làm việc thực tế đủ đầu-cuối, không bắt dùng hết skill. Chọn một agent ghi và một reviewer độc lập; thêm agent cho tính năng nhỏ này chỉ tăng điều phối.

## Bối cảnh và tiêu chí xong

Giả sử dashboard task đã tải một trang dữ liệu được phân quyền, lọc và sắp xếp. Người dùng muốn tải CSV. Trước tiên phải chốt “xuất” nghĩa là trang đang thấy hay toàn bộ bản ghi khớp bộ lọc.

Trong ví dụ, bạn chọn **chỉ trang đang hiển thị**:

- Nút ghi rõ **Export current page**, không khiến người dùng tưởng xuất toàn bộ.
- Đúng hàng và thứ tự đang hiển thị, lấy snapshot lúc bấm. Không tải trang khác hoặc thêm endpoint.
- Chỉ các cột `title`, `status`, `createdAt`, không thêm field ẩn/nội bộ.
- Trang rỗng xuất file chỉ có header. Giữ đúng Unicode, dấu phẩy, dấu nháy và xuống dòng theo encoding CSV đã chọn.
- Giá trị có thể thành công thức spreadsheet phải được vô hiệu hoá theo chính sách chốt trong plan; bọc nháy CSV không tự ngăn formula injection.
- Theo quy ước download/browser có sẵn; nếu tạo object URL tạm thì phải thu hồi.
- Không đổi lọc, sắp xếp, phân quyền hoặc thao tác task hiện tại. Không thêm dependency chỉ vì tính năng này.

Đây là tiêu chí ví dụ, không phải mô tả app đã tồn tại. Xác nhận luật app và yêu cầu spreadsheet thực tế trước khi dùng.

## Vai trò và quyền

| Vai trò | Giữ trách nhiệm | Không được tự làm |
|---|---|---|
| Bạn | Chọn sản phẩm, duyệt plan, cấp quyền ra ngoài, quyết ship | Phải trả lời lại dữ kiện đã có trong repo |
| Coordinator | Đọc nguồn, giữ plan, giao hợp đồng, kiểm bằng chứng, đề xuất tích hợp | Coi worker báo xong là đã chứng minh |
| Writer | Triển khai nhỏ nhất và kiểm chứng trong một checkout được giao | Refactor ngoài việc, suy ra quyền push/merge |
| Reviewer độc lập | Finding chỉ đọc đúng revision | Sửa, chạy test có ghi file, đăng hoặc merge ở mode review |

Phiên hiện tại làm coordinator. Chỉ chọn đường worker đáp ứng đúng model/quyền được yêu cầu. Hết quota hoặc lỗi đăng nhập là **blocked**, không phải quyền đổi model.

Prompt bên dưới dùng cú pháp Claude Code. Codex dùng `$qk-…`, omp dùng `/skill:qk-…`. Skill đồng hành tên **pr-orchestrator**, không phải `pr-orchestration` hay một skill qk mới; gọi theo cú pháp skill đã cài của runtime.

## 1. Brainstorm: chốt ý nghĩa sản phẩm

```text
/qk-brainstorm Người dùng muốn xuất CSV từ dashboard task. So sánh xuất trang đang thấy, toàn bộ task khớp bộ lọc và giữ copy/paste thủ công. Đọc data flow thật trước. Muốn thay đổi nhỏ, không background job hoặc hạ tầng mới. Chưa triển khai, chưa ghi file.
```

Kết quả cần so semantics, chi phí và khả năng quay đầu. Ví dụ này bạn chọn trang hiện tại vì đã có dữ liệu, không cần đường server mới. Đồng thời chấp nhận giới hạn có chủ ý: không gồm các trang khác.

Nếu chưa rõ helper download đang có, nghiên cứu một câu hỏi hẹp là đủ:

```text
/qk-research Repo đã có helper download và xử lý CSV/formula chưa? Đọc code và nguồn chính đúng phiên bản, nêu phần tái dùng được. Không cài package hay sửa file.
```

**Cổng:** bạn duyệt “chỉ trang hiện tại”. Nếu người dùng thực sự cần toàn bộ kết quả lọc, sửa quyết định/plan trước khi triển khai; không âm thầm ship tính năng hẹp hơn.

## 2. Planning: biến ý định thành hợp đồng có giới hạn

```text
/qk-plan create Triển khai Export current page as CSV theo tiêu chí trên. Tìm đường dẫn và lệnh kiểm thật từ repo. Tái dùng trang task đã tải và quy ước download. Chốt chính xác escape CSV, vô hiệu hoá công thức gồm whitespace/control character ở đầu ô và encoding. Không backend, dependency mới hay refactor. Lưu plans/task-page-csv.md. Chưa triển khai.
```

Plan chỉ ra component danh sách, formatter/helper, test và docs thật. Chia việc minh hoạ:

1. Formatter CSV thuần từ field đã chọn; kiểm output với trang rỗng, ký tự đặc biệt và ô giống công thức.
2. Nối snapshot trang hiện tại với nút theo pattern UI/download sẵn có.
3. Thử browser: lọc/sort, sang trang không phải trang đầu, tải CSV, đọc nội dung file và kiểm thao tác task cũ.

Không thêm test chỉ để xác nhận nút gọi mock helper. Biên người dùng quan sát là file CSV tải xuống và các hàng có trong đó.

Nếu cần audit plan bởi model khác:

```text
/qk-agent-coord Nhờ Codex model gpt-6.1-sol audit plans/task-page-csv.md theo repo. Chỉ đọc. Kiểm semantics trang/toàn bộ, field nhạy cảm, CSV/formula và độ phủ kiểm chứng. Nêu bằng chứng và giả thuyết đã loại. Không sửa hoặc đổi cấu hình.
```

Đường chạy không đáp ứng thì báo lý do để bạn quyết. Áp finding được chấp nhận qua `/qk-plan revise plans/task-page-csv.md …`, sau đó bạn duyệt rõ plan. Duyệt là cho phép triển khai đúng phạm vi, không cấp quyền GitHub về sau.

## 3. Orchestration: một writer là đủ

Hai cách hợp lệ; chọn một, không cho cả hai cùng ghi checkout:

- **Đơn giản nhất:** phiên hiện tại gọi `/qk-cook plans/task-page-csv.md`, là writer duy nhất.
- **Giao worker:** phiên hiện tại giữ coordinator, worker chỉ định triển khai trong worktree/branch riêng. Worker áp hợp đồng triển khai kiểu cook ngay trong prompt, không tự nạp `qk/cook`.

Với đường worker, cấp quyền tạo worktree/branch trước. Coordinator ghi đường dẫn và base revision thật; không đoán base hoặc ghi đè worktree cũ.

```text
/qk-agent-coord Giao triển khai cho Codex model gpt-6.1-sol. Tôi cho phép tạo worktree và feature branch riêng cho việc này; tìm base từ repo. Triển khai plans/task-page-csv.md đã duyệt tại đó. Phạm vi: xuất trang, formatter, test hành vi và docs tính năng. Giữ nguyên việc không liên quan. Chạy kiểm đã tìm từ repo và browser smoke; báo lệnh/kết quả/khoảng trống thật. Không commit, push, PR, merge, tag hoặc deploy. Không tích hợp về checkout chính. Model hoặc browser tool cần thiết không chạy được thì báo blocker, không âm thầm đổi đường.
```

Trước giao, coordinator đọc lại hợp đồng: mục tiêu, ngoài phạm vi, file/checkout được ghi, tiêu chí xong, model, quyền, kiểm chứng và điều kiện dừng. Worktree không phải sandbox; giới hạn quyền runtime vẫn áp dụng. Không có kiểm UI thật thì ví dụ này còn bị chặn ship, không được nhận là pass.

Worker trả kết quả thì coordinator tự đọc diff và bằng chứng. Xác nhận model thật từ output runtime hoặc ghi chưa xác minh. Đọc nội dung CSV, không chỉ nhận câu “download thành công”. Chỉ tích hợp về checkout chính khi bạn cấp quyền riêng, hoặc tiếp tục tạo PR từ feature worktree mà không tích hợp. Không biến cả hai checkout thành writer cho cùng việc.

## 4. Kiểm chứng và tạo PR

Writer đã tự kiểm phần làm. Có thể gọi `/qk-test` để kiểm rộng hơn; lệnh đó không tự thay tương tác browser hoặc lấp bằng chứng UI còn thiếu.

Trước tạo PR, gom:

- Base/head revision thật; thay đổi tính năng tách khỏi việc không liên quan.
- Bảng tiêu chí ↔ bằng chứng: output formatter, kiểm file theo trang/lọc/sort và smoke thao tác cũ.
- Lệnh local và exit code thật tìm từ repo; phân loại lỗi bằng bằng chứng, không mặc định baseline.
- Bằng chứng UI nếu có, che dữ liệu riêng; giới hạn còn lại.

Sau đó cấp quyền ra ngoài cụ thể, ví dụ:

```text
Tôi cho phép commit đúng thay đổi tính năng này trên feature branch của nó, push branch đó lên repo này và mở một PR vào base tìm được. Theo convention commit repo. Body PR ghi plan đã duyệt và bằng chứng kiểm chứng. Không merge, release, deploy, force-push hoặc xoá branch. Báo trước nếu push/mở PR sẽ tạo preview có dữ liệu nhạy cảm hoặc tác động ngoài workflow repo đã biết.
```

Coordinator kiểm automation push/PR trước khi làm. Chỉ ghi “mọi kiểm đã pass” khi có kết quả thật. Lưu **URL PR và head SHA thật**; không dùng số PR minh hoạ cho bước tiếp.

## 5. Chạy pr-orchestrator review đúng PR

Cài companion riêng rồi dùng URL thật vừa tạo:

```text
/pr-orchestrator review <URL-PR-thật>
```

Hợp đồng hiện tại của companion:

- `review` chỉ đọc: không checkout/fetch, sửa, worktree, lệnh test ghi cache, comment hoặc merge. Đọc trạng thái CI từ xa, không nhận thành test local.
- Dual audit mặc định là parent và một auditor khác họ model: vòng đầu ghi finding độc lập, vòng hai audit chéo phương pháp, parent kiểm lại dòng ở head SHA PR và đối chiếu base.
- Hai lần cùng model không phải dual audit. Không có họ model thứ hai thì dừng phần điểm dual audit, nêu đường thiếu; không gọi single-model pass là review hoàn tất.
- Chỉ finding đã kiểm và do PR gây ra được vào điểm. Luật repo/cổng companion quyết điều kiện; không chép hoặc nới rubric trong qk.

Với tính năng này, reviewer cần chất vấn “trang hiện tại”, thời điểm snapshot, field ẩn, escape/formula, thu hồi URL và bằng chứng browser. Đây là câu hỏi cần kiểm, không phải finding đã có sẵn.

Có finding xác minh được thì cấp quyền sửa rõ: `/pr-orchestrator fix <URL-PR-thật>` hoặc cook có phạm vi trên feature branch. Không để hai flow sửa cùng lúc. Kiểm lại hành vi sửa; cấp quyền commit/push sửa nếu quyền cũ chưa bao gồm. Head PR đổi thì bằng chứng review cũ không áp cho diff mới: review revision cập nhật, đợi check của nó. Không merge chỉ từ điểm của SHA trước.

## 6. Duyệt, merge và ship: không gộp thành tác động ẩn

Cổng ship thêm của ví dụ yêu cầu **mọi check bắt buộc của repo xanh**, không còn finding đúng đắn/bảo mật chưa giải, verdict companion đủ điều kiện, head đã review vẫn hiện tại và có bằng chứng browser smoke. Đây là lựa chọn chặt hơn của ví dụ, không phải nói companion mặc định luôn bắt CI xanh. Điểm cao không bù thiếu bằng chứng.

Tìm merge method, trigger deploy và quy trình release **trước** khi cấp quyền merge. Nếu merge tự deploy production, chỉ coi quyền merge bao gồm tác động production khi bạn xác nhận rõ; chưa có thì dừng.

Muốn companion thực hiện merge qua mode nó hỗ trợ:

```text
/pr-orchestrator full <URL-PR-thật>
Chỉ PR này. Kiểm lại head hiện tại và cổng merge. Mọi CI bắt buộc phải xanh, browser smoke phải có bằng chứng. Có việc mới hoặc head mới thì trình bày trước khi tiếp. Không tạo release/tag, xoá branch hoặc deploy ngoài workflow merge-triggered hiện có đã được duyệt rõ.
```

`full` có thể sửa, test, đăng điểm và merge đúng PR theo hợp đồng; rộng hơn `review`. Nếu chỉ muốn merge thủ công, không tự sửa/comment, tự merge theo tài liệu repo thay vì bịa mode companion `merge`.

Sau khi tìm release trước và revision đã merge thật, soạn notes:

```text
/qk-release-notes Soạn EN và VI cho <tag-trước-thật>..<revision-đã-merge-thật>. Nêu rõ chỉ xuất trang hiện tại và lưu ý spreadsheet. Lưu nháp theo chỗ repo quy định. Không tăng version, tag, đăng hoặc deploy.
```

Chưa có tag trước thì dùng danh sách PR đã merge thật. Duyệt nháp, rồi cấp quyền riêng cho hành động release/deploy cụ thể, version, revision và môi trường nếu cần. qk không bịa lệnh deploy chung. Nếu merge đã deploy app, kiểm đợt deploy đó, không kích thêm một lần.

**Chỉ gọi là ship xong khi:** revision merge đúng revision được deploy, pipeline hiện có báo thành công, smoke export tại môi trường đích bằng dữ liệu thử không nhạy cảm tạo đúng hàng/nội dung. App lỗi tại đó thì dừng promotion, theo rollback đã được cho phép của repo; merge hoặc tag không tự chứng minh đã ship.

## 7. Đóng việc bằng bằng chứng hoặc bàn giao đúng trạng thái

Báo cáo cuối ghi PR thật, revision merge/deploy, môi trường, kiểm local, URL CI/deploy, smoke runtime, giới hạn và release/tag nào đã được cấp quyền. Không điền giá trị minh hoạ như thể đã quan sát.

Bị chặn hoặc đổi phiên thì `/qk-handoff write` lưu trạng thái thật và quyết định tiếp. Phiên mới resume chỉ đọc, xin lại quyền ra ngoài. Không cần retry ẩn, thêm agent hoặc framework mới.

## Cốt lõi cần giữ

Không phải số skill, mà là: **gỡ mơ hồ → duyệt thay đổi có giới hạn → một writer → PR review độc lập có bằng chứng → cấp quyền tác động ra ngoài → kiểm revision đã ship**. Chỉ bỏ bước khi câu hỏi nó giải quyết đã có đáp án, không phải vì khó lấy bằng chứng.
