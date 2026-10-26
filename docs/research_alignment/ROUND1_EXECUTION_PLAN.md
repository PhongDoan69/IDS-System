# Đợt chạy 1 — kế hoạch khóa trước training

Ngày 26/10/2026, root `D:\CAO HOC\IDS System`; yêu cầu người nghiên cứu: chạy toàn pipeline CICIDS2017 để so sánh, làm cơ sở phát triển pipeline và sau đó đối chiếu hai dataset ngoài. Không tự chạy dữ liệu ngoài trong đợt này.

## Phạm vi và quy tắc

- Round ID: `round1_20261026_s42`; main và LOACO có run ID riêng. Không ghi đè artifacts cũ.
- Raw audit toàn bộ năm CSV, xác nhận checksum với manifest cũ; tái tạo Phase 2 ở thư mục mới và đối chiếu feature arrays, labels, split, row identities, mapping với baseline. Sai khác sẽ dừng trước training.
- Giữ 27 nhãn/Attempted, 84 features, split 70/15/15, seed 42, dense AE và các ngân sách epoch/tree/batch hiện có. Không tuning dựa test.
- Stage 1: XGBoost/MLP × scaled/latent; nested OOF 5 folds, inner 80/10/10; calibration và preprocessing đúng scope revised_v1.
- Stage 2: XGB latent, XGB latent+p, MLP latent, MLP latent+p. MLP latent-only là đối chứng đã có sau review, cần để tách hiệu ứng meta-feature khỏi họ classifier.
- Gate chính cố định XGB latent, ngưỡng 0,5, để Stage 2 ablation không đổi nhiều yếu tố. Stage 1 được so sánh riêng; không tự thay gate theo test winner.
- Chọn Stage 2 bằng validation attack macro-F1; hòa điểm ưu tiên thứ tự cố định trong runner. Lưu selection trước final evaluation/LOACO; scripts train vẫn sinh test metrics nhưng selector không dùng chúng.
- LOACO giữ ID 26 (DDoS, xác nhận mapping trước chạy), refit scaler→AE→Stage 1→Stage 2 được chọn; so MCP/OCSVM/IF với q95 known-attack validation. Không chọn novelty method bằng unknown test.
- Một job GPU tại một thời điểm; CUDA bắt buộc; không tự fallback CPU, đổi hyperparameters hoặc bỏ fold nếu lỗi. Lưu log, thời gian, exit code và status; dừng chuỗi khi lỗi.
- Kiểm checksum source/config trước mỗi phase; snapshot gắn Git HEAD và hashes, không sửa training code giữa run.

## Chạy và theo dõi

```powershell
Set-Location -LiteralPath 'D:\CAO HOC\IDS System'
.\.venv\Scripts\python.exe -X utf8 -u -B scripts\08_run_research_round.py --plan
.\.venv\Scripts\python.exe -X utf8 -u -B scripts\08_run_research_round.py --run
```

Runner mới chỉ điều phối scripts hiện có, không thay thuật toán. `--plan` không ghi file/fit. Chỉ khởi chạy `--run` một lần; nếu đã được trợ lý chạy thì không khởi động bản thứ hai. Không có resume/overwrite ngầm.

Output gốc: `results/research_rounds/round1_20261026_s42/` chứa protocol_lock.json, status.json, logs từng bước, audit, reproduction_checks.json, selection_validation_only.json. Sau khi **tất cả phase thành công** mới có comparison.json và RESEARCH_REPORT.md. Chưa có file report không được suy ra đã hoàn thành.

Config snapshot tại `configs/base_round1_20261026_s42.json` và `configs/model_config_round1_20261026_s42.json`; dữ liệu tái tạo tại `data/processed/round1_20261026_s42/`. Models/results từng tầng dùng hậu tố `_main` hoặc `_loaco26`.

## Cách diễn giải

[TECHNICAL INTERPRETATION] Đây là đợt exploratory: test lịch sử đã xem; feature-vector overlap vẫn còn; upstream provenance/Attempted chưa giải quyết. Một seed và một heldout không chứng minh ưu thế tổng quát hay tính mới. Không đổi split/target ngầm để làm đẹp kết quả.

[REQUIRES FURTHER VERIFICATION] Các sửa correctness đã kiểm nhẹ phải được xác nhận bằng full execution. No-AE/flat multiclass, multi-seed, multi-heldout, confidence intervals theo đơn vị độc lập, calibration reliability và raw-to-model latency chưa nằm trong kết quả hoàn thành. Đối chiếu tài liệu khoa học vẫn cần trước khi xác lập đóng góp mới.

[TECHNICAL INTERPRETATION] Pipeline chọn bằng validation là ứng viên để hoàn thiện, không tự trở thành chuẩn khoa học cuối. Hai dataset ngoài cần thống nhất feature semantics/units/label ontology và xác định rõ intra-dataset retraining hay zero-shot transfer trước thực nghiệm tiếp theo.
