# 01 — Hiện trạng triển khai và phạm vi bằng chứng

Ngày audit: 24/10/2026. Thư mục dự án duy nhất: D:\CAO HOC\IDS System.
Snapshot Git: 895cc8bbba59497ceda625cf9947fa1828e20724, nhánh codex/model-training-pipeline; working tree sạch trước khi tạo báo cáo.

## 1. Kết luận

Đây là một prototype nghiên cứu offline có pipeline và kết quả thực nghiệm thực sự, không chỉ là bộ script chưa chạy. Đã có dữ liệu chuẩn bị, hai encoder, năm cấu hình Stage 1, bốn cấu hình Stage 2, ba novelty detector/score và bốn báo cáo end-to-end. Các metric kiểm tra lại từ artifact khớp với báo cáo đã lưu.

Tuy nhiên, chưa đủ bằng chứng để kết luận hệ thống đã sẵn sàng cho đánh giá cuối cùng của luận văn. Những điểm chặn chính là chính sách nhãn/nguồn dữ liệu, trùng vector đặc trưng giữa split, scaler LOACO tiếp xúc lớp bị giữ lại, OOF chưa độc lập hoàn toàn, và cách diễn giải metric unknown chưa phải end-to-end. Không sử dụng tỷ lệ phần trăm hoàn thành chủ quan.

Audit chỉ đọc source, dữ liệu và kết quả; chạy unit test, tính lại metric từ prediction có sẵn; không huấn luyện, không cài thư viện, không đổi cấu hình hay ghi đè kết quả. Mọi kết luận về implementation dưới đây chỉ dựa trên thư mục dự án này. Tài liệu ngoài dự án chỉ dùng làm nguồn đối chiếu khoa học, không thay thế bằng chứng thực thi.

## 2. Cách đọc trạng thái

- COMPLETE AND VERIFIED: chức năng trong phạm vi ghi rõ có source và artifact/kiểm tra phù hợp. Không đồng nghĩa toàn bộ protocol đúng.
- IMPLEMENTED BUT NOT VERIFIED: có source nhưng thiếu thực thi kiểm chứng độc lập.
- PARTIALLY IMPLEMENTED: đã có phần hoạt động nhưng thiếu điều kiện quan trọng.
- PLANNED ONLY: mục tiêu trong đề bài/tài liệu, chưa thấy implementation tương ứng.
- NOT IMPLEMENTED: không tìm thấy chức năng trong phạm vi đã khảo sát.
- INSUFFICIENT EVIDENCE: không thể xác nhận bằng chứng cần thiết.

## 3. Ma trận hiện trạng

| Thành phần | Vai trò | Trạng thái | Bằng chứng | Vấn đề còn lại | Ưu tiên |
|---|---|---|---|---|---|---|
| 1. Data ingestion | Đọc CSV theo chunk | COMPLETE AND VERIFIED | E01, E02; 5 file khớp SHA256 manifest | Chưa chứng minh provenance upstream | P0 |
| 2. Preprocessing | Tạo mảng 84 chiều | COMPLETE AND VERIFIED | E02–E04; mảng 2.096.804 × 84 | Cần version hóa label/schema policy | P0 |
| 3. Cleaning | Invalid, infinity, duplicate | PARTIALLY IMPLEMENTED | E03; bỏ 3.167 full-row duplicates, invalid=0 | Còn 2.253 val và 2.213 test trùng feature với train | P0 |
| 4. Feature engineering | Chọn cột/nhãn phụ | COMPLETE AND VERIFIED | E03, E04; loại 5 cột | Ports và đặc trưng theo môi trường chưa ablate | P1 |
| 5. Feature selection học từ dữ liệu | Chọn tập con theo thuật toán | NOT IMPLEMENTED | E03 chỉ drop cột cố định; không thấy selector fit | Không được gọi AE là feature selection | P2 |
| 6. Dataset splitting | Stratified random 70/15/15 | PARTIALLY IMPLEMENTED | E05; số lượng và index khớp | Không group/session/time split | P0 |
| 7. Feature scaling | Standardization | PARTIALLY IMPLEMENTED | E02, E03; scaler fit toàn bộ train | Đúng main train-only, sai strict LOACO và chưa fold-local | P0 |
| 8. Autoencoder | 84 → 16 latent | COMPLETE AND VERIFIED | E06; main/loaco_26 có checkpoint, history, latent | Chưa chứng minh cải thiện; không phải greedy layer-wise SAE | P1 |
| 9. Stage 1 binary | BENIGN/ATTACK | COMPLETE AND VERIFIED | E07, E08; 4 main + 1 LOACO; test metric khớp | Quy trình outer-fold early stopping chưa độc lập | P1 |
| 10. P_attack generation | OOF train, final val/test | PARTIALLY IMPLEMENTED | E07; 5 fold artifacts mỗi cấu hình | OOF có thật nhưng không hoàn toàn leakage-safe | P1 |
| 11. Calibration | Logistic/Platt trên logit | PARTIALLY IMPLEMENTED | E09; calibrator joblib | Self-calibrated OOF; chưa ECE/Brier/reliability | P1 |
| 12. Stage 2 multiclass | Phân lớp attack | COMPLETE AND VERIFIED | E10; 3 main + 1 LOACO; mapping khớp | Oracle attack-only khác end-to-end; nhãn hiếm yếu | P1 |
| 13. Meta-feature | Ghép latent + P_attack | COMPLETE AND VERIFIED | E10; stage2_matrix ghép 17 chiều, hai experiment thật | Chưa chứng minh lợi ích ổn định; upstream OOF cần sửa | P1 |
| 14. Closed-set end-to-end | Ghép gate và class ID | COMPLETE AND VERIFIED | E11, E12; 3 prediction CSV tái ghép khớp | Check-only yếu; thiếu kiểm định sai biệt | P1 |
| 15. LOACO/open-set | Giữ lại một lớp | PARTIALLY IMPLEMENTED | E13, E14; heldout=26 DDoS thực sự có run riêng | Scaler dùng cả unknown; mới một lớp; metric naming | P0 |
| 16. Cross-dataset | Kiểm tra domain shift | PLANNED ONLY | Mục tiêu đề bài; không thấy loader/run/result cho dataset thứ hai | Chưa schema/label compatibility | P3 |
| 17. Reproducibility | Seed, metadata, manifest | PARTIALLY IMPLEMENTED | E02, E15; seed42 và raw hashes | Thiếu run lock, complete config/env/model hashes, fold IDs | P1 |
| 18. Model saving | Lưu model cuối/best | COMPLETE AND VERIFIED | E06–E10; .pt/.json/.joblib thực sự tồn tại | Chưa reload+predict trong clean process | P2 |
| 19. Inference hoàn chỉnh | Raw flow → final decision | PARTIALLY IMPLEMENTED | E11, E12; helper predict và ghép mảng | Chưa entry point deploy/replay từ raw schema | P2 |
| 20. Runtime/latency | Chi phí tính toán | INSUFFICIENT EVIDENCE | E15; elapsed_seconds=0.0; chưa benchmark | Không được tuyên bố nhanh/real-time/tối ưu GPU | P2 |
| 21. Documentation | Hướng dẫn vận hành | PARTIALLY IMPLEMENTED | E16; README, guide, phase report | Tiến độ/version và bảo đảm leakage đã lỗi thời | P1 |
| 22. Unit/integration tests | Contract kiểm thử | PARTIALLY IMPLEMENTED | E17; 16 unit tests PASS | Thiếu negative, lineage, full replay tests | P1 |
| 23. Dependencies/environment | Interpreter và package | COMPLETE AND VERIFIED | E18; Python và package đọc trực tiếp | Chưa benchmark CUDA/driver thực tế trong audit | P2 |
| 24. Statistical robustness | Độ ổn định kết quả | PARTIALLY IMPLEMENTED | E11; bootstrap accuracy 1.000 lần | Không multi-seed, paired macro-F1 CI, cluster CI | P1 |
| 25. Label semantics/provenance | Định nghĩa bài toán | INSUFFICIENT EVIDENCE | E04; 27 nhãn, Attempted policy=preserve | Cần xác minh nguồn và chính sách target; xem báo cáo 02 | P0 |
| 26. Feature importance/explainability | Giải thích quyết định | NOT IMPLEMENTED | Không thấy báo cáo SHAP/permutation trong results | Optional sau correctness; tránh thêm complexity sớm | P3 |

COMPLETE ở model/evaluation là xác minh tính tồn tại và tính nhất quán số học, không xác nhận training đã được tái lập hoặc dữ liệu phản ánh triển khai thực tế.

## 4. Sổ bằng chứng source

Các line dẫn tới vị trí chính; cần đọc cả hàm được nêu, không chỉ một dòng.

| ID | Nguồn | Nội dung |
|---|---|---|
| E01 | [src/data_loader.py](<D:/CAO HOC/IDS System/src/data_loader.py:27>) | inspect_schema, iter_csv_chunks, stable_row_hash (66), raw manifest SHA (70) |
| E02 | [scripts/01_prepare_data.py](<D:/CAO HOC/IDS System/scripts/01_prepare_data.py:29>) | collect_unique_metadata; split 108; arrays 117; scaler 147; save 166 |
| E03 | [src/preprocessing.py](<D:/CAO HOC/IDS System/src/preprocessing.py:27>) | clean_chunk; feature columns 48; TrainOnlyStandardScaler 59 |
| E04 | [configs/base.json](<D:/CAO HOC/IDS System/configs/base.json:1>); [src/labels.py](<D:/CAO HOC/IDS System/src/labels.py:12>); [artifacts/metadata/label_mapping.json](<D:/CAO HOC/IDS System/artifacts/metadata/label_mapping.json>) | Schema/policy và target encoding |
| E05 | [src/split_data.py](<D:/CAO HOC/IDS System/src/split_data.py:13>) | Stratified random split có minimum support |
| E06 | [scripts/02_train_autoencoder.py](<D:/CAO HOC/IDS System/scripts/02_train_autoencoder.py:34>); [src/autoencoder.py](<D:/CAO HOC/IDS System/src/autoencoder.py:12>) | AE và bộ dữ liệu dùng fit |
| E07 | [scripts/03_train_stage1.py](<D:/CAO HOC/IDS System/scripts/03_train_stage1.py:86>) | Outer folds, early stopping, OOF calibration 124, final model 130 |
| E08 | [src/stage1_xgboost.py](<D:/CAO HOC/IDS System/src/stage1_xgboost.py:15>); [src/stage1_mlp.py](<D:/CAO HOC/IDS System/src/stage1_mlp.py:12>) | Objectives, weights, architecture |
| E09 | [src/calibration.py](<D:/CAO HOC/IDS System/src/calibration.py:8>) | Clipped logit → LogisticRegression |
| E10 | [scripts/04_train_stage2.py](<D:/CAO HOC/IDS System/scripts/04_train_stage2.py:54>); [src/stage2.py](<D:/CAO HOC/IDS System/src/stage2.py:12>) | Class mapping; stage2_matrix 29; training 37/81 |
| E11 | [scripts/06_evaluate_pipeline.py](<D:/CAO HOC/IDS System/scripts/06_evaluate_pipeline.py:51>) | File checks, compose 93, open-set metrics 119, save 126 |
| E12 | [src/evaluation.py](<D:/CAO HOC/IDS System/src/evaluation.py:9>); [src/metrics.py](<D:/CAO HOC/IDS System/src/metrics.py:8>) | Gate/UNKNOWN và định nghĩa metric |
| E13 | [scripts/05_train_novelty.py](<D:/CAO HOC/IDS System/scripts/05_train_novelty.py:44>) | Metadata LOACO; train 80; threshold/scores 119–184 |
| E14 | [src/novelty.py](<D:/CAO HOC/IDS System/src/novelty.py:19>) | q95; subsampling 34; max probability 65; OCSVM 76; IF 95 |
| E15 | [src/training_utils.py](<D:/CAO HOC/IDS System/src/training_utils.py:12>); [src/runtime.py](<D:/CAO HOC/IDS System/src/runtime.py:10>); [src/model_data.py](<D:/CAO HOC/IDS System/src/model_data.py:21>) | Early stopping, checkpoint/history, seeds và contracts |
| E16 | [docs/TRAINING_GUIDE.md](<D:/CAO HOC/IDS System/docs/TRAINING_GUIDE.md:1>); [docs/PHASE_2_REPORT.md](<D:/CAO HOC/IDS System/docs/PHASE_2_REPORT.md:1>); [README.md](<D:/CAO HOC/IDS System/README.md:1>) | Tài liệu hiện hữu, không coi là bằng chứng hoàn tất |
| E17 | [tests/test_training_contracts.py](<D:/CAO HOC/IDS System/tests/test_training_contracts.py:1>); [tests/test_preprocessing.py](<D:/CAO HOC/IDS System/tests/test_preprocessing.py:1>) | Unit tests cho contract nhỏ, không toàn bộ experimental validity |
| E18 | [requirements.txt](<D:/CAO HOC/IDS System/requirements.txt:1>); [.venv/pyvenv.cfg](<D:/CAO HOC/IDS System/.venv/pyvenv.cfg:1>); [configs/model_config.json](<D:/CAO HOC/IDS System/configs/model_config.json:1>) | Dependencies, interpreter, cấu hình GPU/models |

## 5. Inventory artifact thực tế

- Dữ liệu: [CICIDS2017](<D:/CAO HOC/IDS System/CICIDS2017>); [data/processed](<D:/CAO HOC/IDS System/data/processed>); [artifacts/metadata/raw_manifest.json](<D:/CAO HOC/IDS System/artifacts/metadata/raw_manifest.json>).
- AE: [models/autoencoder/main/best.pt](<D:/CAO HOC/IDS System/models/autoencoder/main/best.pt>), [models/autoencoder/loaco_26/best.pt](<D:/CAO HOC/IDS System/models/autoencoder/loaco_26/best.pt>); mỗi run có latent_features.npy và run.json.
- Stage 1: [models/stage1](<D:/CAO HOC/IDS System/models/stage1>); mỗi cấu hình có 5 model fold, 1 final và 1 calibrator. P_attack nằm trong [data/processed/experiments](<D:/CAO HOC/IDS System/data/processed/experiments>).
- Stage 2: [models/stage2](<D:/CAO HOC/IDS System/models/stage2>); probabilities, indices và class_ids ở [results/stage2](<D:/CAO HOC/IDS System/results/stage2>).
- Novelty: [models/novelty/loaco_26/heldout_26](<D:/CAO HOC/IDS System/models/novelty/loaco_26/heldout_26>); max-probability không cần model riêng; threshold tại [artifacts/thresholds/loaco_26/heldout_26](<D:/CAO HOC/IDS System/artifacts/thresholds/loaco_26/heldout_26>).
- Pipeline: [results/pipeline](<D:/CAO HOC/IDS System/results/pipeline>); mỗi run có metrics.json và test_predictions.csv.gz. Danh mục chính xác và số liệu ở [docs/research_audit/03_experiment_review.md](<D:/CAO HOC/IDS System/docs/research_audit/03_experiment_review.md>).
- Tài liệu tham khảo: [Tài liệu tham khảo](<D:/CAO HOC/IDS System/Tài liệu tham khảo>) có 15 PDF. Audit chưa thực hiện systematic literature review hoặc đọc/trích từng PDF; không suy ra tác giả/DOI từ tên file. Tính mới học thuật chưa được xác minh.

## 6. Nhật ký kiểm tra

| Kiểm tra | Phương pháp không huấn luyện | Kết quả |
|---|---|---|
| Root/Git | Get-Location; git -C đúng root status/log | Root đúng; commit như đầu báo cáo |
| Unit tests | .venv\Scripts\python.exe -B -m unittest discover -s tests -v | 16/16 PASS, lần chạy lại 0,124 s; đây không phải thời gian train |
| Environment | Python -B, sys.version, importlib.metadata | Python 3.10.7; NumPy 2.2.6; pandas 2.3.3; sklearn 1.7.2; torch 2.13.0+cu130; XGBoost 3.2.0; joblib 1.5.3 |
| Raw integrity | SHA256 đọc streaming 5 CSV | Cả 5 khớp manifest local; không chứng minh nguồn tải |
| Dataset contract | memmap, label/split/count/hash | 2.096.804 hàng; BENIGN ID0; binary khớp; raw/scaled hữu hạn |
| Scaler | Tính lại train mean, đối chiếu state và transform mẫu | Khớp full train; LOACO unknown train chưa bị loại |
| Duplicate model input | Hash 84 cột float32 rồi so từng phần tử | 2.253 val, 2.213 test có bản sao vector trong train |
| Metrics/replay | Tính lại từ probabilities; compose và so CSV | 5 Stage 1, 4 Stage 2, 4 pipeline khớp; cả 4 final prediction khớp từng hàng |
| Novelty | q95 known-val + score metric | Maxprob khớp tuyệt đối; IF/OCSVM lệch rất nhỏ do lưu float32 |
| Negative contract probe | Mảng giả trong RAM chứa NaN | Hàm compose trả BENIGN thay vì từ chối |

Không chạy GPU benchmark, train, model forward/reload mới hoặc bootstrap lại 1.000 lần. Không đọc PCAP hay xác minh sessions/near-duplicates. Full-row hash khác nhau không chứng minh độc lập thống kê. Mã kiểm tra read-only có thể tái dùng nằm trong phụ lục báo cáo 03; không tạo script executable trong project.

## 7. Chỉ mục báo cáo

[02 — Correctness](<D:/CAO HOC/IDS System/docs/research_audit/02_pipeline_correctness.md>) · [03 — Experiments](<D:/CAO HOC/IDS System/docs/research_audit/03_experiment_review.md>) · [04 — Contributions](<D:/CAO HOC/IDS System/docs/research_audit/04_research_contributions.md>) · [05 — Thesis notes](<D:/CAO HOC/IDS System/docs/research_audit/05_thesis_technical_notes.md>) · [06 — Roadmap](<D:/CAO HOC/IDS System/docs/research_audit/06_improvement_roadmap.md>) · [07 — Executive summary](<D:/CAO HOC/IDS System/docs/research_audit/07_executive_summary.md>).
