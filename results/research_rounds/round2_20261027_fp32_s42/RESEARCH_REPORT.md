# Kết quả đợt 1 — CICIDS2017

[VERIFIED FROM EXPERIMENTS] Các số dưới đây đọc từ metrics.json của run mới; xem comparison.json và logs để truy vết.

## Stage 1 — binary detection

| Cấu hình | Val F1 | Test F1 | Precision | Recall | FPR | FNR | AUROC | AP | Brier |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| xgboost_latent | 0.999306 | 0.999242 | 0.999274 | 0.999209 | 0.000236 | 0.000791 | 0.999995 | 0.999986 | 0.000308 |
| xgboost_scaled | 0.999851 | 0.999857 | 0.999806 | 0.999909 | 0.000063 | 0.000091 | 1.000000 | 1.000000 | 0.000053 |
| mlp_scaled | 0.999132 | 0.999086 | 0.998821 | 0.999352 | 0.000383 | 0.000648 | 0.999959 | 0.999890 | 0.000378 |
| mlp_latent | 0.997220 | 0.997350 | 0.996956 | 0.997744 | 0.000990 | 0.002256 | 0.999890 | 0.999751 | 0.001146 |

## Stage 2 và cascade — cùng gate XGB latent 0,5

| Biến thể | Val attack macro-F1 | Test attack macro-F1 | E2E accuracy | Balanced accuracy | Macro-F1 | Weighted-F1 |
|---|---:|---:|---:|---:|---:|---:|
| latent_only | 0.890735 | 0.896850 | 0.995333 | 0.832742 | 0.844330 | 0.995347 |
| latent_plus_pattack_xgb | 0.883603 | 0.917160 | 0.995199 | 0.851510 | 0.844752 | 0.995212 |
| latent_only_mlp | 0.739820 | 0.745497 | 0.989883 | 0.807050 | 0.720496 | 0.990022 |
| latent_plus_pattack_mlp | 0.636933 | 0.657256 | 0.983365 | 0.754212 | 0.629927 | 0.983945 |

[VERIFIED FROM EXPERIMENTS] Stage 2 được khóa bằng validation: `latent_only`. Không đổi lựa chọn theo test.

## LOACO 26 — unknown sau gate

| Method | Unknown precision | Recall | F1 | Known attack false rejection | Benign → unknown | Unknown bị gate chặn | E2E macro-F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| max_probability | 0.501131 | 0.217349 | 0.303196 | 0.048943 | 11.000000 | 229.000000 | 0.792861 |
| one_class_svm | 0.152717 | 0.039378 | 0.062611 | 0.049404 | 12.000000 | 229.000000 | 0.642086 |
| isolation_forest | 0.066487 | 0.015555 | 0.025212 | 0.049309 | 17.000000 | 229.000000 | 0.591836 |

## Hiệu ứng meta-feature cùng họ classifier

| So sánh | Δ validation attack macro-F1 | Δ test E2E macro-F1 |
|---|---:|---:|
| latent_plus_pattack_xgb − latent_only | -0.007132 | +0.000421 |
| latent_plus_pattack_mlp − latent_only_mlp | -0.102888 | -0.090569 |

[TECHNICAL INTERPRETATION] Delta là quan sát của một seed/split, không phải kiểm định ý nghĩa thống kê. Đọc per_class, support, confusion_matrix và error_decomposition trong comparison.json trước khi kết luận.

[REQUIRES FURTHER VERIFICATION] Kết hợp thuật toán có sẵn và điểm số cao không tự chứng minh tính mới. Cần đối chứng no-AE/flat theo kế hoạch duyệt, multi-seed, split độc lập, multi-heldout và đối chiếu tài liệu khoa học.

[TECHNICAL INTERPRETATION] Pipeline được chọn là ứng viên thăm dò cho giai đoạn tiếp theo, chưa là chuẩn đã xác nhận. CSE-CIC-IDS2018/CIC-UNSW-NB15 chưa chạy; phải chốt feature semantics, units, ontology và phân biệt retrain với zero-shot.

## Giới hạn đã chốt trước run

- exploratory: historical test already inspected
- fixed random split retains feature-vector overlap
- Attempted preserved; provenance/target semantics unresolved
- one seed and one heldout; no superiority/significance/novelty proof
- Stage 1 family comparison separate from fixed-gate Stage 2 ablation
- no raw-to-model latency benchmark; no flat/no-AE Stage 2 control

Thời gian từng subprocess ở status.json gồm I/O/checksum/metrics, không phải độ trễ inference. Không có kết quả model-reload latency trong đợt này.
