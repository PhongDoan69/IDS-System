# Kết quả CIC-UNSW-NB15

[VERIFIED FROM EXPERIMENTS] Chỉ tạo sau khi tất cả phase thành công. Nguồn: comparison.json và metrics.json từng phase.

Primary khóa từ CICIDS2017: XGB latent gate 0,5 → latent_plus_pattack_xgb. Huấn luyện lại trên native dataset, KHÔNG zero-shot.

Native features: 76; rows: 306173; partial dataset: False.

## Stage 1

| Model | Val F1 | Test F1 | P | R | FPR | FNR | AUROC | AP | Brier |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| xgboost_latent | 0.955619 | 0.952804 | 0.921236 | 0.986612 | 0.030430 | 0.013388 | 0.992963 | 0.975039 | 0.021137 |
| xgboost_scaled | 0.959684 | 0.956951 | 0.928004 | 0.987762 | 0.027644 | 0.012238 | 0.994524 | 0.981313 | 0.018924 |
| mlp_scaled | 0.953964 | 0.951509 | 0.919746 | 0.985544 | 0.031022 | 0.014456 | 0.991559 | 0.967833 | 0.021800 |
| mlp_latent | 0.947976 | 0.944319 | 0.896626 | 0.997372 | 0.041481 | 0.002628 | 0.989447 | 0.957601 | 0.026079 |

## Stage 2/cascade

| Variant | Val attack macro-F1 | Oracle test macro-F1 | E2E accuracy | Balanced accuracy | E2E macro-F1 | Weighted-F1 |
|---|---:|---:|---:|---:|---:|---:|
| latent_only | 0.449950 | 0.465915 | 0.873903 | 0.595156 | 0.493479 | 0.883896 |
| latent_plus_pattack_xgb | 0.469817 | 0.479138 | 0.880000 | 0.561862 | 0.507540 | 0.887136 |
| latent_only_mlp | 0.287741 | 0.289709 | 0.820054 | 0.537990 | 0.346268 | 0.824348 |
| latent_plus_pattack_mlp | 0.296729 | 0.298895 | 0.822537 | 0.544013 | 0.352974 | 0.828052 |

## LOACO

NOT RUN: không chỉ định lớp heldout trước training; không có kết quả unknown.

## Giới hạn

- native schemas/class ontologies differ; scores not directly comparable tasks
- random split may retain conflicting-label feature overlap; see preparation_report
- native X+label dedup differs from CICIDS2017 full-row dedup
- one seed, no proof of novelty, no independent temporal/group test
- subprocess time is not inference latency; no standalone deployment entrypoint

Per-class support, confusion matrices, error decomposition và score-only/final unknown nằm đầy đủ trong comparison.json.
Không suy ra tính mới hoặc ưu thế thống kê từ một seed; không xếp hạng độ khó dataset bằng macro-F1 của các ontology khác nhau.
