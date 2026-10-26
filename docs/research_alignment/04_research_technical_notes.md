# Ghi chú kỹ thuật cho viết luận văn và bảo vệ

Ngày 26/10/2026. Đọc cùng [ma trận](01_alignment_matrix.md), [validity](03_experiment_validity_report.md) và [hướng dẫn chạy](PIPELINE_REPRODUCTION_GUIDE.md). Mọi claim về code mới phải ghi protocol `revised_v1`; mọi metric lịch sử phải ghi legacy run.

## 1. Kiến trúc và vai trò thuật toán

[VERIFIED FROM IMPLEMENTATION] Hệ thống xử lý bản ghi flow offline. StandardScaler học trung bình/phương sai; dense AE được huấn luyện đồng thời toàn mạng, nén 84→16 bằng MSE. Stage 1 là bộ phân loại nhị phân XGBoost hoặc MLP; Stage 2 là XGBoost hoặc MLP chỉ học các lớp tấn công đã biết. Nhánh novelty tùy chọn dùng `1 − max(probability)`, `−OCSVM.decision_function` hoặc `−IF.score_samples`. Không thêm Transformer, PCA, SMOTE, greedy pretraining hoặc từ chối bằng reconstruction error trong đợt này.

[TECHNICAL INTERPRETATION] AE học tái tạo, không trực tiếp tối ưu khả năng phân biệt lớp tấn công hiếm. Giảm chiều không chứng minh tăng F1, giảm tổng độ trễ hoặc ngăn overfitting. XGBoost/MLP cần được so sánh với cùng biểu diễn và ngân sách lựa chọn siêu tham số; một run không xác lập ưu thế tổng quát.

## 2. Năm khái niệm cần giải thích chắc

1. **Phạm vi fit và leakage:** train-only không đủ cho strict LOACO nếu scaler còn thấy lớp unknown; OOF không đủ nếu nhãn của outer holdout được dùng để chọn checkpoint. Phân biệt test leakage, lựa chọn mô hình có phụ thuộc nhãn và việc preprocessing nhìn thấy X không nhãn.
2. **Nested OOF và calibration:** hàng outer holdout phải nằm ngoài fit/stop/calibration sinh p của chính nó. `revised_v1` chia 80/10/10 bên trong outer-training; chỉ scalar p được ghép lại, không trộn tọa độ latent của nhiều encoder. Final Platt fit trên raw OOF và chỉ áp vào final validation/test; chất lượng calibration vẫn phải đo.
3. **Phân loại có điều kiện và lan truyền lỗi:** Stage 2 không học BENIGN nhưng benign false positives vẫn đi vào Stage 2 khi vận hành cascade. Metric trên true-attack subset không phải metric cuối. Trong closed-set, tổng lỗi bằng benign qua gate + attack bị chặn + attack qua gate nhưng phân lớp sai.
4. **Macro metrics, mất cân bằng và support:** accuracy/weighted-F1 có thể cao dù F1 của lớp hiếm bằng 0. Macro-F1 nhạy khi lớp chỉ có 1–5 mẫu; cần báo cáo per-class và độ bất định. AP là average precision, không đồng nhất với diện tích đường PR tính bằng quy tắc hình thang; AUROC cao không bảo đảm recall tốt tại một ngưỡng.
5. **LOACO khác tổng quát hóa thực tế:** giữ lại một lớp chú giải mô phỏng unseen trong benchmark, không chứng minh phát hiện zero-day thực tế. Unknown ở đầu ra cuối phải qua gate; benign bị từ chối nhầm cũng phải tính vào precision/F1 của unknown. Huấn luyện lại trên dữ liệu ngoài khác chuyển miền zero-shot.

Các mục trên là [VERIFIED FROM IMPLEMENTATION] về cơ chế; phần hệ quả là [TECHNICAL INTERPRETATION], chưa phải kết quả mới.

## 3. Vai trò p_attack và quyết định cuối

[VERIFIED FROM IMPLEMENTATION] `p_attack` có hai vai trò: gate cho mọi cascade và cột thứ 17 trong các biến thể latent+p. Latent-only/latent_only_mlp không thêm cột p. Stage 2 training dùng p OOF; validation/test dùng p từ final model, đã calibration nếu bật. p tại heldout train/validation bị loại có thể là NaN theo thiết kế; mọi index thực sự được tiêu thụ phải có giá trị hữu hạn.

```text
p < 0,5                         → BENIGN (0)
p ≥ 0,5 và score ≥ ngưỡng novelty → UNKNOWN (-1), nếu bật novelty
p ≥ 0,5 còn lại                  → class_ids[argmax(Stage 2 probabilities)]
```

[TECHNICAL INTERPRETATION] Khi p là hàm xác định của cùng z, nó không thêm quan sát giao thông độc lập; nó có thể giúp bộ học hữu hạn nhờ cách biểu diễn. Lợi ích này phải được kiểm bằng đối chứng cùng classifier. Không gọi mọi kiến trúc hai tầng là stacking.

## 4. Chi tiết protocol phải ghi khi viết chương phương pháp mới

- [VERIFIED FROM IMPLEMENTATION] Target/split giữ nguyên; global test không dùng để fit. Scaler LOACO chỉ fit known train theo run. Fold-local preprocessing chỉ sinh OOF p; Stage 2 dùng z chung.
- [VERIFIED FROM IMPLEMENTATION] AE dùng MSE/AdamW; Stage 1 dùng weighted BCE hoặc `scale_pos_weight`; Stage 2 dùng balanced sample weights hoặc weighted CE. XGB early stopping theo metric cuối trong config: Stage 2 hiện dùng `merror`, không phải macro-F1.
- [VERIFIED FROM IMPLEMENTATION] Weighted CE validation lấy tổng loss có trọng số chia tổng trọng số target; gradient training vẫn tính theo weighted batch mean. Sửa aggregation có thể đổi checkpoint tốt nhất và lịch điều chỉnh learning rate.
- [VERIFIED FROM IMPLEMENTATION] Gate vẫn cố định 0,5. Ngưỡng novelty là phân vị 95 trên known-attack validation, tương ứng mục tiêu từ chối 5%; các giá trị bằng nhau và dịch chuyển miền có thể làm tỷ lệ quan sát khác 5%.
- [VERIFIED FROM IMPLEMENTATION] Manifest lưu checksum source/input, bản chụp config và môi trường lúc run. Seed không bảo đảm CUDA tái lập bitwise; các cờ TF32/benchmark/deterministic được giữ và ghi nhận. Cần đóng băng phiên bản source/config trước chuỗi chạy; checksum được lưu không đồng nghĩa tự khóa mọi thay đổi source về sau.
- [REQUIRES FURTHER VERIFICATION] Tỷ lệ inner 80/10/10 và ngân sách tính toán cần công bố/chốt trước corrective full runs, không điều chỉnh sau khi xem test. Chưa có sổ đăng ký lựa chọn bất biến trước test; script train còn sinh test metrics, nên nhà nghiên cứu phải khóa thiết kế và không chọn model theo những số đó.

## 5. Đóng góp nào được phép trình bày?

| Loại phát biểu | Có căn cứ hiện tại | Chưa được khẳng định |
|---|---|---|
| Engineering | Pipeline, contracts, adapters và kiểm thử unit/integration/replay | Sẵn sàng triển khai production hoặc real-time |
| Correctness | NaN fail-closed; weighted CE đúng; kiểm scopes/ancestry | “Không còn leakage” khi split overlap chưa xử lý |
| Thực nghiệm | Kết quả legacy và replay có điều kiện | Corrective model tốt hơn hoặc meta-feature làm tăng F1 |
| Unknown | Cơ chế từ chối; LOACO 26 lịch sử mang tính sơ bộ | Thành công strict multi-heldout hoặc zero-day thực tế |
| Tổng quát hóa | Khảo sát schema dữ liệu ngoài có sẵn local | Chuyển miền tốt hoặc huấn luyện lại là zero-shot |
| Tính mới | Câu hỏi và nghiên cứu so sánh có thể phát triển | Ghép thuật toán sẵn có tự động tạo đóng góp mới |

## 6. Câu hỏi chốt với người hướng dẫn

1. Định nghĩa target cuối cho Attempted và nguồn/phiên bản dataset được chấp nhận là gì?
2. Đơn vị độc lập là nhóm feature-vector, phiên flow, host hay ngày; xử lý lớp quá ít nhóm thế nào mà không nhân bản mẫu?
3. Câu hỏi nghiên cứu cần những đối chứng flat/no-AE/MLP latent-only nào; ngân sách tuning và tiêu chí chọn trước test là gì?
4. Giữ gate 0,5 hay chọn theo FPR budget trên validation; open-set là kết quả chính hay mở rộng; những lớp heldout nào đủ điều kiện?
5. Dữ liệu ngoài chỉ dùng khảo sát khả thi, intra-dataset replication hay zero-shot transfer; đã đủ bằng chứng về đơn vị đo, ontology nhãn, shared features và nguồn lực thực hiện chưa?

Không chỉnh kết luận luận văn trước khi có các run/evidence đáp ứng protocol đã chốt; negative findings vẫn là kết quả nghiên cứu hợp lệ.
