---
name: qk-agent-coord
description: >-
  Giao một việc có giới hạn cho agent và model được người dùng chỉ định (review,
  triển khai cô lập, chẩn đoán, ý kiến thứ hai) rồi kiểm kết quả trước khi chấp
  nhận. Chỉ dùng khi người dùng gọi đích danh qk/agent-coord (`/qk-agent-coord`,
  `$qk-agent-coord`, `/skill:qk-agent-coord`).
disable-model-invocation: true
---

# qk/agent-coord

Phiên đang chạy là **coordinator**: giữ quyết định, kiểm kết quả, tích hợp. Agent được giao là **worker**: kết quả của nó là bằng chứng chưa kiểm.

| | |
|---|---|
| **Kết quả** | Việc được giao đúng agent/model, đúng quyền; kết quả đã được coordinator kiểm và phân loại chấp nhận / loại |
| **Quyền** | Khởi chạy worker qua đường có sẵn trên máy. Worker chỉ có quyền ghi trong worktree riêng khi việc cần ghi. Không cài, đăng nhập hay sửa cấu hình runtime để chạy worker. Tích hợp diff của worker vào checkout chính chỉ khi người dùng đồng ý |
| **Xong khi** | Có output của worker, model thật đã chạy (hoặc ghi "chưa xác minh"), kết luận của coordinator cho từng điểm |

## 1. Chốt việc giao

- Chỉ giao cho agent/model người dùng nêu. Không nêu thì hỏi, không tự chọn.
- Chọn hình thức nhỏ nhất đủ dùng: một lần chạy headless cho ý kiến thứ hai; terminal hoặc worktree riêng cho việc ghi; tuần tự có cổng cho chuỗi nhiều bước.
- Viết hợp đồng theo [references/prompt-templates.md](references/prompt-templates.md). Không đưa secret, `.env`, token hay dữ liệu cá nhân vào prompt; bảo worker tự đọc repo.

## 2. Chọn đường chạy theo khả năng

Một đường chỉ hợp lệ khi nó chạy **đúng agent và model đã chỉ định**, **đúng quyền**, và **cô lập ghi** nếu việc cần ghi.

| Đường | Khi dùng | Lưu ý |
|---|---|---|
| Subagent của runtime hiện tại | Model chỉ định chọn được trong runtime này | omp: agent gắn role qua `modelRoles` hoặc `task.agentModelOverrides`, gọi theo tên agent; không phụ thuộc override model theo từng lần gọi |
| Terminal Orca | Việc dài, việc ghi, cần quan sát | Dùng worktree riêng cho việc ghi; Orca không tự ép read-only |
| CLI headless | Agent khác runtime hiện tại, việc đọc | Prompt qua stdin, có timeout, ghi lại lệnh đã chạy |

Cờ CLI đã thấy trong `--help` (kiểm lại trên phiên bản đang dùng trước khi chạy):

| CLI | Model | Không tương tác | Giới hạn quyền |
|---|---|---|---|
| `claude` | `--model` | `-p` | `--permission-mode plan` |
| `codex exec` | `-m` | `exec` | `-s read-only` |
| `qwen` | `-m` | prompt vị trí, stdin nối vào | `--approval-mode plan` |
| `omp` | `--model` | `-p` | `--tools` giới hạn tool |

Không đường nào đáp ứng → báo **blocked** kèm lý do. Không âm thầm đổi sang model mặc định, provider khác hay agent khác.

## 3. Bảo vệ checkout

- Mỗi checkout chỉ một agent ghi. Việc ghi của worker chạy trong worktree riêng, nhánh riêng.
- Worktree tránh va chạm Git, **không phải sandbox**: network, credential và file ngoài repo vẫn do quyền của runtime quyết định.
- Việc chỉ đọc: dùng chế độ giới hạn quyền của runtime ở bảng trên — đó là lớp chặn chính. Thêm bằng chứng bằng cách chạy ba lệnh sau trước và sau khi worker chạy rồi so output:

  ```bash
  git rev-parse --verify -q HEAD
  git status --porcelain --ignored --untracked-files=all
  git ls-files -z -co --exclude-standard | xargs -0 shasum
  ```

  Bộ này bắt được commit mới, file mới (kể cả file ignored và file trong thư mục untracked), xoá file, sửa file tracked hay untracked kể cả khi file đó đã bẩn sẵn, và chạy được trên repo chưa có commit. `git status --porcelain` đơn thuần bỏ sót phần lớn các trường hợp này. Vẫn **không** bắt được việc sửa file ignored có sẵn và file ngoài repo; ghi giới hạn này khi báo cáo.
- Có thay đổi ngoài dự kiến → dừng, báo file thay đổi. Không tự revert, không stash.
- Timeout không chứng minh worker đã dừng. Không giao lại việc ghi cho cùng vùng khi chưa chắc worker cũ đã kết thúc. Không tự chạy lại việc có tác động ra ngoài.

## 4. Kiểm kết quả

- Review: chỉ nhận finding tái hiện được, trong phạm vi, có bằng chứng `file:line` mà coordinator đã đọc lại.
- Triển khai: đọc diff trong worktree của worker, chạy kiểm chứng liên quan, rồi mới đề xuất tích hợp.
- Hai model cùng đồng ý không thay cho việc đọc lại bằng chứng.
- Sửa tiếp: gửi một prompt ngắn chỉ gồm điểm đã chấp nhận và điều kiện dừng.

## Báo cáo

```text
Worker:       <agent> / model yêu cầu <...> / model thật <... hoặc chưa xác minh>
Đường chạy:   <subagent / orca / headless — lệnh>
Kết quả:      <tóm tắt>
Chấp nhận:    <điểm — bằng chứng đã kiểm>
Loại:         <điểm — lý do>
Checkout:     <không đổi / thay đổi ngoài dự kiến: ...>
Tiếp theo:    <việc cần người dùng quyết>
```

## Ranh giới

- Chỉ dẫn cấp cao hơn, luật runtime và luật repo thắng skill này.
- Dùng cơ chế task, subagent và model binding có sẵn của runtime. Không đổi model, quyền, hook hay cấu hình.
- Không tự gọi skill qk khác.
