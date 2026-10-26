# Tổng hợp căn chỉnh phương pháp và triển khai

Ngày: 26/10/2026. Root: `D:\CAO HOC\IDS System`. Trạng thái: đã sửa code và kiểm chứng nhẹ; **chưa huấn luyện lại trên CICIDS2017**. Ma trận được tạo trước source edits; lịch sử kỹ thuật ở [IMPLEMENTATION_CHANGELOG.md](IMPLEMENTATION_CHANGELOG.md).

## 1. Phương pháp có căn cứ

[VERIFIED FROM IMPLEMENTATION / THESIS] Bản PDF được đối chiếu là `main (3).pdf`, SHA256 trong [ma trận](01_alignment_matrix.md), cùng review 25/10 và tám audit reports 24/10. §3.2–3.7 xác định IDS offline trên flow CSV: cleaning → fixed class-aware split → standardization → dense AE → binary XGBoost/MLP → attack-only Stage 2 → optional novelty → quyết định cuối. AE joint 84→64→32→16→32→64→84, không greedy SAE; không feature selector học từ dữ liệu. Reconstruction error không phải novelty score hiện hành.

[VERIFIED FROM IMPLEMENTATION] Giữ nguyên 5 daily CSV, 27 nhãn local, Attempted=preserve, 84 predictors và split 70/15/15 có xử lý lớp hiếm. Không sửa raw, ground truth, các mảng Phase 2 hay model/results lịch sử. Giữ gate 0,5 theo §3.4.1, không gọi ngưỡng cố định này là ngưỡng đã tối ưu trên validation.

[TECHNICAL INTERPRETATION] Cần nghiên cứu khả năng phân biệt BENIGN/ATTACK, nhận diện known attack và từ chối unknown sau gate; không coi việc ghép AE/XGB/MLP là bằng chứng tính mới. RQ về representation, model family, meta-feature và unknown rejection vẫn được giữ, không mặc định kết quả tích cực.

## 2. Trước và sau sửa

| Thành phần | Trước sửa | Đã triển khai ở revised_v1 | Trạng thái bằng chứng |
|---|---|---|---|
| Scaler LOACO | Fit toàn train gồm lớp giữ lại | Scaler per-run chỉ known train, lưu fit indices + checksum | Synthetic mean test PASS; check-only trên dữ liệu thật đúng 1.401.162 hàng khi giữ ID 26; chưa tạo scaler thật mới |
| OOF selection | Outer fold làm early stopping | Inner fit/stop/calibration 80/10/10 bên trong outer training | Unit/integration với model mock PASS; full GPU training chưa chạy |
| OOF representation | Shared scaler/AE | Fold-local scaler/AE chỉ sinh scalar p | Nhánh latent được kiểm orchestration bằng mock; không ghép latent khác encoder |
| Calibration | Fit và áp lại cùng OOF labels | Calibrator inner-calibration mỗi fold; final calibrator dùng raw OOF, chỉ áp final val/test | Actual logistic calibrator chạy trên fixture; chưa reliability benchmark |
| Stage 2 | 3 variants; gộp weighted CE sai | Giữ 3 variants, thêm optional latent_only_mlp; tính đúng weighted numerator/denominator | CPU weighted CE regression PASS; chưa có kết quả control mới |
| Evaluation | Check length; NaN→BENIGN; unknown score-only | Fail-closed; composition thật trong check-only; per-class/confusion/error decomposition/final unknown | 37 tests PASS; 4 legacy prediction replays khớp từng hàng |
| Artifacts | Paths dễ overwrite, lineage yếu | Từ chối overwrite; hashes/config/environment/parents; strict consumers | Tamper/heldout tests PASS; không tạo lineage hồi tố cho old runs |
| External | Script khám phá chưa thành adapter | 2 native adapters; kiểm header/alignment/invalid; mapping template fail-closed | CSE prefix audit + UNSW full read; chưa train/transfer |

Đây là trạng thái chức năng, không phải kết quả phân loại đã được cải thiện.

## 3. Corrective protocol và thay đổi có ảnh hưởng so sánh

[VERIFIED FROM IMPLEMENTATION] `--protocol revised_v1` là xác nhận tường minh cho scripts 02–05. Trước AE/Stage 1 phải chạy 01b tạo scaler riêng. Artifacts main/loaco_26 cũ không được dùng tiếp cho training mới; evaluation cũ chỉ replay với `--allow-legacy-artifacts`, gắn nhãn lineage chưa xác minh.

[TECHNICAL INTERPRETATION] Inner partition 80/10/10 và encoder fold-local khắc phục phụ thuộc đã xác nhận, nhưng giảm số hàng fit mỗi fold và tăng chi phí tính toán. Đây là phiên bản phương pháp mới cần mô tả trong luận văn; không so chênh metric với legacy như chỉ thay một tham số. Final classifier vẫn dùng toàn known train, external validation cho early stopping; final calibration dùng raw OOF train. Phân phối score giữa fold/final có thể khác; cần đo chất lượng calibration.

[VERIFIED FROM IMPLEMENTATION] Stage 2 nhận z từ một encoder chung fit train; chỉ p là nested OOF khi train. Validation/test p từ final model. BENIGN không vào Stage 2 fitting; inference gate dựa prediction, không ground truth. Số chiều 16/17 được giữ với config hiện tại.

## 4. Nội dung chưa được phép đổi ngầm

Các mục sau là **REQUIRES RESEARCHER APPROVAL**:

1. Xác nhận archive/version và ngữ nghĩa Attempted; nếu đổi target policy phải có mapping/version riêng.
2. Đổi random split sang feature-group/session/time split, quy định class coverage/rare-class exceptions; không xóa test duplicates hậu nghiệm.
3. Đổi gate 0,5 thành threshold chọn theo validation/FPR budget; đổi early-stop metric XGB hoặc tuning budget cũng phải chốt trước khi xem test.
4. Thêm flat multiclass/raw+latent/feature-ablation như đối chứng mới hoặc thu hẹp RQ; control MLP latent-only đã có code nhưng chưa chạy và chưa có kết luận.
5. External common-feature/units/extractor/label ontology; chọn intra-dataset replication hay source→target không retrain. Không coi native adapters là phê duyệt protocol chuyển miền.

[REQUIRES FURTHER VERIFICATION] Chưa tìm thấy biên bản supervisor chấp thuận mới trong nguồn đọc được. Review kỹ thuật không thay thế phê duyệt học thuật. Không thay nội dung/kết luận PDF để khớp code.

## 5. Phán định sẵn sàng

[TECHNICAL INTERPRETATION] Mức căn chỉnh đã tăng ở **tính đúng của logic, phạm vi fit và contract artifact**, được hỗ trợ bằng unit/integration/replay. Chưa thể kết luận kết quả luận văn cuối có độ tin cậy khoa học: split overlap, provenance/target semantics, test đã xem, support hiếm, một seed/heldout và thiếu đối chứng vẫn còn.

Ưu tiên tiếp theo: chốt target/split và ngân sách lựa chọn → chạy corrective main controls → strict multi-heldout nếu giữ RQ4 → uncertainty/benchmark đầy đủ → cập nhật luận văn bằng evidence mới. Không cần thêm thuật toán phức tạp trước những bước này.
