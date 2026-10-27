# Chỉ mục kết quả đã chọn công bố cùng mã nguồn

Ngày chuẩn bị: 27/10/2026. Repository: `PhongDoan69/IDS-System`, nhánh `codex/model-training-pipeline`.

Theo yêu cầu mới, commit bao gồm **các kết quả dạng JSON/CSV/Markdown hiện có** để truy vấn và đối chiếu. Chính sách này bổ sung phạm vi source/config/docs của bản kiểm kê trước đó; không biến tệp model/data/log thành nội dung cần đưa vào Git.

`.gitattributes` tắt chuyển đổi line-ending cho `results/**` để giữ nguyên byte của bằng chứng khi stage/checkout. File kết quả không được tính lại hoặc sửa metric trong quá trình công bố. Source allowlist được bổ sung tệp chính sách và chỉ mục này; số lượng 135 trong bản kiểm kê trước là snapshot trước bước công bố.

## Đọc kết quả nào trước?

1. [NOVELTY_R3_FINDINGS.md](NOVELTY_R3_FINDINGS.md): phân tích và giới hạn kết luận của đợt mới nhất.
2. [R3 summary.csv](../../results/novelty_confirmation/novelty_r3_20261027/summary.csv): bảng phẳng 54 dòng, thuận tiện so sánh held-out × seed × gate × detector.
3. [R3 summary.json](../../results/novelty_confirmation/novelty_r3_20261027/summary.json): mean/SD/min/max và paired delta kNN trừ baseline cùng seed.
4. [R3 comparison.json](../../results/novelty_confirmation/novelty_r3_20261027/comparison.json): metric đầy đủ của 54 evaluation, gồm per-class/confusion matrix, Stage 1, Stage 2, score-only và final cascade.
5. [R3 protocol_lock.json](../../results/novelty_confirmation/novelty_r3_20261027/protocol_lock.json), [status.json](../../results/novelty_confirmation/novelty_r3_20261027/status.json): protocol, cấu hình, nguồn dữ liệu, checksum và 120 command/exit codes.

Các đường dẫn bên dưới tương đối với root repository. Khi truy vấn từ Prism hoặc công cụ khác, cần chọn/import đúng repository và nhánh; việc push Git **không tự xác nhận** công cụ bên ngoài đã đồng bộ hoặc có quyền truy cập.

## Các đợt nghiên cứu và vai trò

| Study / tập dữ liệu | Trạng thái ghi nhận | Nguồn file trong repository | Cách sử dụng |
|---|---|---|---|
| CICIDS2017 `novelty_r3_20261027` | Completed, 120 steps; 3 held-out × 3 seed | `results/novelty_confirmation/novelty_r3_20261027/` | Nguồn chính cho matched MCP/Mahalanobis/kNN; 54 dòng summary + 9 reference không novelty |
| CICIDS2017 `knn_v1` | Completed; một seed, grid 12 biến thể | `results/knn_studies/knn_v1/` | Lịch sử ablation k/normalization/reference policy; primary ban đầu natural_l2_k50, balanced_l2_k1 là ứng viên đề xuất sau khi xem test |
| CICIDS2017 `mahalanobis_v1` | Completed; reuse frozen upstream | `results/mahalanobis_studies/mahalanobis_v1/` | Đối chứng pooled Ledoit–Wolf vs MCP, fixed/recall gate |
| CICIDS2017 `recall_gate_v1_20261027` | Completed | `results/recall_gate_studies/recall_gate_v1_20261027/` | Fresh LOACO chain và so sánh fixed/recall gate trước R3 |
| CICIDS2017 `loaco_more_v2_20261027` | Completed | `results/loaco_finetune/loaco_more_v2_20261027/` | Hai held-out bổ sung; profile selection theo validation, không chọn profile theo test |
| CICIDS2017 `round2_20261027_fp32_s42` | Completed | `results/research_rounds/round2_20261027_fp32_s42/` | FP32 encode, bốn Stage 1/bốn Stage 2 và LOACO DDoS lịch sử |
| CICIDS2017 `round1_20261026_s42` | Completed, historical | `results/research_rounds/round1_20261026_s42/` | Đối chiếu lịch sử/precision policy; không trộn thành cùng một thí nghiệm R3 |
| CIC-UNSW `cicunsw_r2_20261026_iofix` | Completed cho closed-set | `results/research_rounds/cicunsw_r2_20261026_iofix/` | Không xem closed-set completion là zero-day success |
| CIC-UNSW `cicunsw_zero_day_v2` | Failed tại LOACO Stage 1; phần main có kết quả | `results/research_rounds/cicunsw_zero_day_v2/` | Chỉ dùng phần main đã hoàn tất; không báo LOACO đã thành công |
| `cicunsw_r1`, `loaco_more_v1` | Failed | `results/research_rounds/cicunsw_r1/`, `results/loaco_finetune/loaco_more_v1/` | Giữ status/protocol để tránh bỏ qua lịch sử lỗi; không đưa vào bảng mô hình hoàn tất |

## Cấp metric và nguồn bằng chứng

| Câu hỏi | Nguồn nên đọc |
|---|---|
| Hệ thống thực sự phát hiện unknown bao nhiêu? | `results/pipeline/<evaluation>/metrics.json` → `final_unknown_metrics`; population gồm toàn test sau gate |
| Nếu bỏ qua gate, detector nhận ra unknown bao nhiêu? | `score_only_unknown_metrics` / legacy `open_set_metrics`; **không** thay thế recall toàn hệ thống |
| Stage 1 bỏ sót bao nhiêu? | `stage1_test_metrics`, `error_decomposition`, `unknown_blocked_by_stage1` |
| Stage 2 phân loại known tốt không? | `stage2_oracle_known_attack_metrics`; conditional admitted-known có population khác |
| Lớp hiếm bị ảnh hưởng thế nào? | `end_to_end_metrics/per_class` + support, và `*_class_rejection.json` dưới study R3 |
| Lựa chọn ngưỡng/seed/method có dùng test không? | `protocol_lock.json`, `gate_h*_s*.json`, threshold/validation metadata, tài liệu findings; không suy từ điểm số cao |
| Stage 1/Stage 2 riêng lẻ | `results/stage1/<run>/*/metrics.json`, `results/stage2/<run>/*/metrics.json` |
| AE và novelty riêng lẻ | `results/autoencoder/<run>/history.json`, `results/novelty/<run>/.../metrics.json` |
| Label/split trước huấn luyện | `results/split_summary.csv`, `results/label_distribution.csv`, raw audit JSON/CSV trong research rounds |

## Quy tắc so sánh và trích dẫn

- Ghi đúng study/run ID, dataset, held-out, seed, gate và novelty method; dẫn file cùng JSON key hoặc dòng CSV, không chỉ dẫn tên repository chung.
- So sánh detector trên cùng upstream/held-out/seed/gate. Nếu khác protocol phải ghi khác biệt; không coi mọi bảng historical là matched comparison.
- R3 giữ cùng split, đổi fitting/reference seed. Ba seed không tạo ba tập test độc lập. Unknown = `-1`, không phải hệ thống tự dự đoán đúng tên lớp chưa train.
- `balanced_l2_k1` được đề xuất sau khi xem test `knn_v1`; R3 chưa là test độc lập. Còn overlap/provenance/Attempted/shared-validation và các giới hạn đã nêu trong findings.
- Trong R3, kNN unknown recall sau gate trung bình theo seed: Hulk 93,28%, Portscan 55,39%, DDoS 99,61%; gộp theo support từng seed 80,13 ± 2,72%. Đây là tóm tắt theo đúng protocol, không suy rộng zero-day thực tế hoặc tính mới thuật toán.
- Giữ cả các đối chứng kém hơn và run failed với nhãn trạng thái; không chọn bỏ kết quả âm khi tổng hợp luận văn.

## Những gì Git không chứa

Raw CSV datasets, prepared arrays, `.npy` scores/probabilities/indices, `.npz`/`.csv.gz` predictions, `.pt`/`.joblib` weights/indexes, môi trường `.venv` và training logs không được thêm vào commit này. Các tệp đó vẫn giữ tại máy theo chính sách lưu trữ hiện tại.

Artifact contracts/checksum và các đường dẫn Windows trong JSON được giữ nguyên như bằng chứng local, **không** là cam kết có thể replay model chỉ từ clone Git. Một số artifact lịch sử đã cold-archive; Git giữ kết quả để đọc/đối chiếu, không giả mạo lineage hoặc tự sửa absolute paths. Training R3 từ clone sạch vẫn cần tạo lại các prerequisites theo hướng dẫn.

Các 19 file kết quả legacy từng tracked nhưng đang thiếu ở working tree do lần cleanup trước **không bị stage deletion trong commit này**; bản đã có ở Git vẫn được bảo toàn. Chúng là lịch sử, không được dùng thay số liệu R3.

Để tái tạo bảng chính, đọc `summary.csv` hoặc tính mean và sample SD trên ba seed từ `final_unknown_metrics` của đúng held-out/method/gate trong `comparison.json`. Không tự cộng mẫu lặp theo seed hay dùng score-only recall làm final recall.
