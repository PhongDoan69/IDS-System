# Kết quả đợt 1 — CICIDS2017

[VERIFIED FROM EXPERIMENTS] Các số dưới đây đọc từ metrics.json của run mới; xem comparison.json và logs để truy vết.

## Stage 1 — binary detection

| Cấu hình | Val F1 | Test F1 | Precision | Recall | FPR | FNR | AUROC | AP | Brier |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| xgboost_latent | 0.999352 | 0.999313 | 0.999339 | 0.999287 | 0.000215 | 0.000713 | 0.999995 | 0.999986 | 0.000288 |
| xgboost_scaled | 0.999851 | 0.999857 | 0.999806 | 0.999909 | 0.000063 | 0.000091 | 1.000000 | 1.000000 | 0.000053 |
| mlp_scaled | 0.999132 | 0.999086 | 0.998821 | 0.999352 | 0.000383 | 0.000648 | 0.999959 | 0.999890 | 0.000378 |
| mlp_latent | 0.997214 | 0.997156 | 0.996492 | 0.997822 | 0.001142 | 0.002178 | 0.999880 | 0.999710 | 0.001160 |

## Stage 2 và cascade — cùng gate XGB latent 0,5

| Biến thể | Val attack macro-F1 | Test attack macro-F1 | E2E accuracy | Balanced accuracy | Macro-F1 | Weighted-F1 |
|---|---:|---:|---:|---:|---:|---:|
| latent_only | 0.891745 | 0.917161 | 0.995307 | 0.833635 | 0.845273 | 0.995322 |
| latent_plus_pattack_xgb | 0.892170 | 0.917275 | 0.995285 | 0.842691 | 0.843216 | 0.995295 |
| latent_only_mlp | 0.742360 | 0.748540 | 0.990188 | 0.811596 | 0.716103 | 0.990337 |
| latent_plus_pattack_mlp | 0.630567 | 0.671336 | 0.982147 | 0.741850 | 0.615989 | 0.982644 |

[VERIFIED FROM EXPERIMENTS] Stage 2 được khóa bằng validation: `latent_plus_pattack_xgb`. Không đổi lựa chọn theo test.

## LOACO 26 — unknown sau gate

| Method | Unknown precision | Recall | F1 | Known attack false rejection | Benign → unknown | Unknown bị gate chặn | E2E macro-F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| max_probability | 0.535785 | 0.248108 | 0.339160 | 0.048545 | 16.000000 | 209.000000 | 0.791559 |
| one_class_svm | 0.152838 | 0.039238 | 0.062444 | 0.049166 | 13.000000 | 209.000000 | 0.627171 |
| isolation_forest | 0.102198 | 0.025084 | 0.040281 | 0.049691 | 21.000000 | 209.000000 | 0.571738 |

## Hiệu ứng meta-feature cùng họ classifier

| So sánh | Δ validation attack macro-F1 | Δ test E2E macro-F1 |
|---|---:|---:|
| latent_plus_pattack_xgb − latent_only | +0.000425 | -0.002057 |
| latent_plus_pattack_mlp − latent_only_mlp | -0.111794 | -0.100114 |

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
