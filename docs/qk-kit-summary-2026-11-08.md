# Tổng kết qk và so sánh với các bộ kit

Ngày: 2026-11-08. Snapshot triển khai: `d23ab292e979595b55066d4398b77e36e2f078dc`.

## Kết luận

qk là bộ workflow cá nhân gọn, ưu tiên bằng chứng và ranh giới quyền; chưa phải nền tảng agent hoặc bộ kit doanh nghiệp. Điểm khác biệt là không giành quyền của omp/Claude/Codex, không tự nối skill và không coi quyền sửa code là quyền push/merge/deploy. Đây là sự phù hợp với nhu cầu cá nhân, không phải bằng chứng tạo code tốt hơn mọi kit khác.

## Những gì đã hoàn tất

### 10 skill

| Nhóm | Skill | Kết quả |
|---|---|---|
| Quyết định | qk/brainstorm, qk/research | So hướng đi; kiểm câu hỏi bằng nguồn và đối chứng |
| Lập và thực hiện | qk/plan, qk/cook | Create/audit/revise plan; triển khai có phạm vi và kiểm chứng |
| Chất lượng | qk/debug, qk/test | Chẩn đoán trước sửa; kiểm độc lập, tách baseline và lỗi mới |
| Phối hợp | qk/agent-coord, qk/handoff | Giao đúng agent/model, kiểm output; bàn giao ngữ cảnh nhưng không chuyển quyền |
| Phát hành | qk/release-notes | Nháp truy được commit/PR, không tự publish |
| Học từ công việc | qk/dogfood | Phân loại nguyên nhân, đề xuất instruction tối thiểu, không tự áp dụng |

### Source và tài liệu

- Đã chuyển 10 SKILL.md và một file prompt template sang tiếng Anh.
- Báo cáo giữ ngôn ngữ người dùng; sửa artifact đã có giữ ngôn ngữ/định dạng hiện tại.
- README, guide từng skill, workflow và runtime evidence có EN/VI.
- Case study CSV là ví dụ xuyên suốt, không phải app đã ship trong repo này.
- Validator kiểm metadata, explicit-only policy, link, cặp docs và một số mẫu path/secret. CI có gitleaks.
- pr-orchestrator là companion riêng, không nằm trong 10 skill hoặc engine tích hợp của qk.
- Commit d23ab29 đã push lên origin/main. GitHub báo cả validate và gitleaks thành công tại đúng SHA.

### Kiểm chứng đã quan sát

- Validator trong đợt triển khai trả `OK: 10 skills checked`.
- Sau chuyển tiếng Anh: 10 smoke tổng hợp trên OMP 18.15.0 / profile work / Opus 5.5. Bao gồm Việt/Anh, log trùng, inventory, quota/provider, injection, native invocation, plan tiếng Việt và handoff có drift.
- Các lần chạy đơn lẻ không phải chứng nhận tương thích. Bản tiếng Anh chưa chạy lại trên Codex, Claude Code, Qwen hoặc omp tương tác.

| Tokenizer offline | Trước | Sau | Thay đổi |
|---|---:|---:|---:|
| claude-v5 | 16.994 | 13.299 | Giảm 21,7% |
| o200k_base | 9.199 | 8.763 | Giảm 4,7% |
| qwen3 | 8.896 | 9.081 | Tăng 2,1% |

Phạm vi: cả 11 file instruction, gồm policy mới và các làm rõ. Không phải chi phí mỗi hội thoại, token tính phí API hoặc benchmark với kit khác.

## So sánh với các kit tiêu biểu

Dựa trên source qk và tài liệu chính của đối chiếu; chưa benchmark cùng một task trên cả bốn bộ.

| Trục | qk | Superpowers | GitHub Spec Kit | AgentKit / SkillX |
|---|---|---|---|---|
| Cách dùng | Gọi đích danh từng workflow | Skill tự trigger theo methodology được mô tả | Process, template, lệnh và workflow có cấu trúc | Kit và hệ sinh thái CLI/dịch vụ rộng |
| Runtime | Không thêm hook/router/engine riêng | Bootstrap và tích hợp theo harness | CLI, integrations, extension hooks/workflows | CLI và nhiều sản phẩm liên quan |
| Tự động | Chủ ý thấp, người dùng giữ cổng chuyển bước | TDD, plan, subagent-driven development | Spec → plan → tasks → implement/converge | Khả năng orchestration, marketplace, deploy/sandbox tùy sản phẩm |
| Phụ thuộc | Markdown + Git/symlink; Python để validate | Plugin/extension/package tùy harness | Specify CLI; tài liệu yêu cầu Python và uv | CLI/auth/dịch vụ tùy thành phần |
| Phân phối | Một Git source; chưa có registry/version pinning riêng | Marketplace và nhiều harness | Catalog, preset, bundle, overlay, private catalog | SkillX marketplace; một số personal-kit/private-sync còn preview |

### Lợi thế của qk

1. **Nhẹ, dễ sở hữu:** đọc và sửa trực tiếp instruction trong Git; không phải duy trì engine cho workflow cá nhân.
2. **Hợp người đã có runtime mạnh:** giữ tool, model, permission, plan mode của runtime; chỉ bổ sung hợp đồng công việc.
3. **Quyền rõ:** phân biệt đọc, sửa, tích hợp worker và hành động ra ngoài. Đây là instruction, không phải sandbox cưỡng chế.
4. **Dogfood bảo thủ:** không quét lịch sử toàn máy, không auto-patch, không thêm luật để che 403/429 hoặc lỗi tuân thủ luật đã rõ.
5. **Không ép pipeline cho việc nhỏ:** yêu cầu rõ có thể cook trực tiếp. Đây không phải đặc điểm độc quyền; Spec Kit hiện cũng có entry point độc lập.

### Điểm thua hoặc chưa có

1. **Ít tự động:** chưa có lifecycle engine, queue, orchestration resume hoặc cổng thực thi riêng.
2. **Nâng cấp còn thô:** symlink theo checkout không tự cung cấp pinning, rollback/version management hoặc quản trị catalog. Git pull có thể đổi nguồn cho mọi runtime cùng liên kết.
3. **Bằng chứng mỏng:** chưa có đánh giá lặp lại đa model/runtime hoặc benchmark tỉ lệ hoàn thành, hồi quy, thời gian và chi phí so với đối thủ.
4. **Tính năng chuyên sâu ít:** chưa có requirements traceability quy mô lớn, domain kit rộng, marketplace, vault, remote executor, renderer hoặc deploy platform. Dùng công cụ ngoài không đồng nghĩa đã tích hợp.
5. **Chưa có bảo đảm vận hành cho team:** thiếu chính sách version/release/support và enforcement riêng. CI cấu trúc xanh không chứng minh agent sẽ tuân thủ.

## Định vị nên giữ

**Personal workflow layer cho người đã dùng runtime tốt; không cố làm AgentKit thu nhỏ.**

- Muốn ít can thiệp và giữ quyết định rõ: qk phù hợp.
- Muốn chạy dài tự động theo methodology/TDD: xem Superpowers.
- Muốn quản lý spec, artifact và process cho team: xem Spec Kit.
- Muốn hệ sinh thái phân phối và dịch vụ rộng: xem AgentKit; kiểm riêng trạng thái và trust model từng thành phần.

Chưa có bằng chứng qk hơn đối thủ về chất lượng code, an toàn thực thi hoặc tổng chi phí. Lợi thế hiện tại là độ gọn và phù hợp với nhu cầu đã chọn.

## Ưu tiên tiếp theo

1. Hoàn tất audit toàn source, rồi chỉ sửa finding được xác minh theo yêu cầu riêng.
2. Giữ fixture tổng hợp tái chạy được cho các ranh giới quan trọng trên runtime thực sự dùng.
3. Có release/tag và hướng dẫn pin phiên bản trước khi chia sẻ rộng.
4. Benchmark vài task thật với cùng input, repo/revision và tiêu chí chấm; tách model cost, skill overhead và chất lượng kết quả.

## Trạng thái tại thời điểm ghi

Triển khai, dịch source, docs và push đã hoàn tất. Audit toàn source hai model đang diễn ra; **chưa có kết luận audit chéo cuối**. Không coi bản tổng kết này là báo cáo audit đã hoàn thành.

File này được tạo sau commit nói trên theo yêu cầu lưu để đọc lại; chưa được commit/push.

## Nguồn đối chiếu

- [Superpowers — README chính thức](https://github.com/obra/superpowers): methodology, automatic triggering và tích hợp harness.
- [GitHub Spec Kit — README chính thức](https://github.com/github/spec-kit): process, CLI, preset, extension, workflow, catalog và bundle.
- [AgentKit — bản đồ hệ sinh thái](https://agentkit.best/blog/agentkit-guides/the-agentkit-ecosystem-what-vault-render-cloudharness-skillx-and-tose-are-and-when-to-use-them): trạng thái shipped/beta/preview. Đây là tài liệu nhà cung cấp, chưa kiểm implementation.
