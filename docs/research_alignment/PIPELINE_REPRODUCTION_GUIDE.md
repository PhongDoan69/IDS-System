# Hướng dẫn tái lập pipeline IDS — revised_v1

Cập nhật ngày 26/10/2026. Thư mục duy nhất: `D:\CAO HOC\IDS System`.

**Trạng thái kiểm chứng:** các tham số CLI đã được kiểm bằng `--help`; 37 unit/integration tests đạt; bốn pipeline lịch sử replay khớp. Integration tests dùng model giả, còn scaler, calibration, contract và metric chạy thật trên dữ liệu giả. **Chưa chạy full training CICIDS2017 hoặc thử cài lại môi trường sạch trong đợt này.** Các lệnh training dưới đây dành cho người nghiên cứu thực hiện, không phải nhật ký đã hoàn thành.

## A. Điều kiện trước khi thực hiện

- Dùng ID mới; không ghi đè `main`, `loaco_26` hoặc run dở dang. Không xóa checkpoint để cố tiếp tục một run thất bại.
- Chốt target policy, split, tiêu chí chọn cấu hình và ngân sách tính toán trước khi đọc test metrics. Scripts 03/04 vẫn tính test metrics sau training; chưa có cơ chế tự động làm mù test hoặc khóa lựa chọn bất biến.
- `revised_v1` sửa scaler/OOF nhưng giữ split hiện tại. Feature-vector overlap, ngữ nghĩa Attempted và provenance vẫn chưa được giải quyết; không gọi toàn bộ protocol là hoàn toàn không leakage.
- Chạy một job GPU tại một thời điểm. Stage 1 latent mới cần thêm năm encoder fold-local, nên chi phí có thể cao hơn đáng kể. Chưa có benchmark để khẳng định cấu hình tối ưu nhất cho GPU 4 GB.
- Check-only chỉ chạy được khi upstream đã tồn tại. Nó kiểm contract/logic, không chứng minh hội tụ hoặc độ tin cậy khoa học.

## B. Môi trường Windows và Visual Studio Code

Trong VS Code, mở đúng thư mục IDS System và chọn interpreter `D:\CAO HOC\IDS System\.venv\Scripts\python.exe`. Dùng terminal PowerShell; không thực thi bare đường dẫn `.py`.

```powershell
Set-Location -LiteralPath "D:\CAO HOC\IDS System"
py -0p
```

Môi trường hiện tại đã kiểm: Python 3.10.7 64-bit; NumPy 2.2.6, pandas 2.3.3, scikit-learn 1.7.2, joblib 1.5.3, XGBoost 3.2.0 có CUDA; PyTorch 2.13.0+cu130, CUDA runtime 13.0; RTX 3050 Laptop, 4096 MiB VRAM. Đây là môi trường hiện tại, không được gán ngược cho training lịch sử.

### B1. Tạo môi trường sạch khi thực sự cần

Script setup hỗ trợ Python 3.10–3.12 64-bit đã đăng ký với launcher. Ví dụ dùng đúng phiên bản máy hiện tại:

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\setup_windows_cuda.ps1" -PythonVersion "3.10"
```

Input: Python đã cài, `requirements.txt`, kết nối để tải packages. Output: `.venv`, dependencies và Torch cu130 theo script. Script chỉ tạo venv nếu chưa có, sau đó cài packages và verify; vì vậy không chạy lại vô cớ trên môi trường đang hoạt động.

Thành công: exit code 0 và thông báo setup complete. Nếu không thấy Python, kiểm `py -0p`; nếu lỗi pip/wheel/network, dừng và đọc lỗi, không bỏ pin hoặc đổi CUDA tùy tiện. Cú pháp setup đã đọc từ source, nhưng đợt căn chỉnh không cài lại hoặc kiểm download trên máy sạch.

### B2. Kiểm tra môi trường và tests

```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts\verify_environment.py --skip-cuda-smoke
.\.venv\Scripts\python.exe -X utf8 -B -m unittest discover -s tests -v
```

Output: diagnostics và test report trên terminal, không có model training artifacts. Đã quan sát CUDA available, runtime 13.0, đúng GPU và 37 tests PASS. `--skip-cuda-smoke` không chạy phép cộng tensor GPU; bỏ cờ này nếu cần smoke test tensor bốn phần tử. Đây không phải benchmark mô hình.

Wheel Torch mang CUDA runtime; setup này không dùng nvcc để biên dịch model. Không đồng nhất giá trị `driver_max_cuda` trong config với runtime thực tế. Dùng `-X utf8` để tránh lỗi cp1252 khi in tiếng Việt, `-B` để không sinh pycache. Sau mỗi lệnh native kiểm `$LASTEXITCODE`; nếu khác 0 thì dừng trước phase phụ thuộc.

## C. Cấu trúc project và chuẩn bị dữ liệu

```text
CICIDS2017/                         monday.csv ... friday.csv
configs/base.json                  cleaning, target, feature exclusions, split
configs/model_config.json           architecture, hyperparameters, paths
data/processed/                    Phase 2 arrays và row/split identities
data/processed/experiments/<R>/     scaler riêng, latent, P_attack của run mới
models/<phase>/<R>/                 fold models và final checkpoints
artifacts/metadata/<phase>/<R>/     plan, execution status, metadata
results/<phase>/<R>/                probabilities, metrics, history
artifacts/thresholds/<R>/           novelty thresholds theo heldout/variant
data/external/                     dữ liệu CSE và CIC-UNSW đã có local
```

### C1. Nguồn dữ liệu và audit

Cần đúng năm file trong `configs/base.json`: monday.csv, tuesday.csv, wednesday.csv, thursday.csv, friday.csv. Snapshot có 89 cột; 84 predictors còn lại sau loại Label, Attempted Category, Timestamp, Src IP dec và Dst IP dec. Khi chuyển máy, đối chiếu SHA256 với `artifacts/metadata/raw_manifest.json`.

**NOT REPRODUCIBLE từ một public archive xác định:** chưa đủ bằng chứng xác nhận upstream release và ngữ nghĩa Attempted. Không tải một bộ khác cùng tên CICIDS2017 rồi coi là cùng benchmark. Cần xác nhận nguồn, archive, checksum và giấy phép; không có lệnh download tự động.

Nếu cần audit lại đầy đủ vào thư mục mới:

```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts\00_audit_dataset.py --config configs\base.json --output-dir results\audit_rebuild_20261026
```

Vai trò: đọc schema, chất lượng dữ liệu, nhãn và manifest; không train. Input là năm CSV. Output trong `results/audit_rebuild_20261026`: dataset_summary.csv, label_distribution.csv, data_quality_report.json; thư mục con `metadata` chứa raw_manifest.json và schema.json. Thành công: exit 0, đủ năm file, schema nhất quán và các số đếm có giải trình. Missing file/schema mismatch phải được điều tra tại nguồn, không bỏ cột hoặc thêm 0 để qua kiểm tra. Full audit này chưa được chạy lại trong lượt căn chỉnh.

### C2. Dùng Phase 2 hiện có hoặc rebuild tách biệt

Trong workspace hiện tại, nên giữ Phase 2 đã có và đi tới C3. Không chạy script 01 mặc định vì nó sẽ từ chối ghi đè baseline.

Nếu cần tái tạo độc lập từ raw:

```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts\01_prepare_data.py --config configs\base.json --output-dir data\processed_rebuild_20261026
```

Vai trò: cleaning, full-row dedup, mapping nhãn, split theo lớp và scaler main train-only. Output trong thư mục rebuild:

- features_raw.npy, features_scaled.npy, row_hashes.npy, attack_label_ids.npy, binary_labels.npy, attempted_flags.npy, source_ids.npy, split_ids.npy;
- train_indices.npy, validation_indices.npy, test_indices.npy, split_summary.csv;
- `preprocessors/scaler.joblib`;
- `metadata/feature_names.json`, label_mapping.json, source_mapping.json, cleaning_report.json, split_config.json.

Thành công: arrays cùng số hàng, nhãn/split hợp lệ, features hữu hạn. Đối chiếu số lượng với audit nếu dùng cùng snapshot; không gọi số kỳ vọng là kết quả đã chạy. `--max-rows-per-file` chỉ dành cho smoke data, không dùng cho bảng benchmark đầy đủ. Full-row dedup chưa giải quyết overlap ở model-input representation.

Nếu chọn nhánh rebuild, trong VS Code dùng Save As tạo `configs/model_config_rebuild.json` từ model_config.json và đổi hai field trong object `experiment`:

```json
"processed_dir": "data/processed_rebuild_20261026",
"prepared_metadata_dir": "data/processed_rebuild_20261026/metadata"
```

Đây là hai field thay trong config đầy đủ, không phải một JSON standalone. Mọi lệnh sau thêm `--config configs\model_config_rebuild.json`; các đường dẫn `data\processed\...` phải đổi sang thư mục rebuild. Không trộn metadata cũ với arrays mới. Scaler C2 không phải scaler LOACO; C3 luôn tạo scaler per-run.

### C3. Tạo preprocessing corrective cho main

Ví dụ còn lại dùng Phase 2 hiện có, seed 42. Nếu ID minh họa đã tồn tại, chọn ID mới và thay nhất quán mọi đường dẫn:

```powershell
$R = "rev_main_20261026_s42_v1"
.\.venv\Scripts\python.exe -X utf8 -B scripts\01b_prepare_protocol.py --run-id $R --check-only
.\.venv\Scripts\python.exe -X utf8 -B scripts\01b_prepare_protocol.py --run-id $R
```

Input: raw array, labels, splits, hashes và feature/label/split metadata. Vai trò: giữ nguyên task/split, fit scaler đúng phạm vi và lưu identity.

Output tại `data/processed/experiments/<R>/preprocessing/`: features_scaled.npy, scaler.joblib, fit_indices.npy, execution.json, features_scaled.npy.contract.json. Thành công: status completed, fit indices chỉ thuộc train; main kỳ vọng 1.467.762 hàng với snapshot hiện tại. Check-only không ghi file. Overwrite error yêu cầu ID mới; thiếu schema/mapping thì không tiếp tục. Đợt này chỉ kiểm C3 ở chế độ check-only trên dữ liệu thật, chưa tạo corrected full arrays.

## D. Autoencoder và Stage 1

### D1. AE common và tạo latent

```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts\02_train_autoencoder.py --run-id $R --protocol revised_v1 --check-only
.\.venv\Scripts\python.exe -X utf8 -B scripts\02_train_autoencoder.py --run-id $R --protocol revised_v1
```

Input: scaler/manifest/scaled array từ C3. Vai trò: train dense AE common trên train, early stopping trên validation, restore checkpoint rồi encode toàn bộ dữ liệu theo row order. Không có lệnh encode riêng cần chạy.

Output: `models/autoencoder/<R>/best.pt`; `data/processed/experiments/<R>/latent_features.npy` và sidecar; `artifacts/metadata/autoencoder/<R>/run.json`; `results/autoencoder/<R>/history.json`.

Thành công: status completed, latent shape `[N,16]`, hữu hạn, hashes khớp. Nếu OOM, giữ run thất bại, giảm batch trong bản config mới và dùng ID mới; không đổi split hay âm thầm fallback CPU. Check-only không fit model.

### D2. Stage 1: nested OOF, final model và calibration

```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts\03_train_stage1.py --run-id $R --protocol revised_v1 --model xgboost --representation latent --check-only
.\.venv\Scripts\python.exe -X utf8 -B scripts\03_train_stage1.py --run-id $R --protocol revised_v1 --model xgboost --representation latent
```

Input: latent common và raw/scaled/identity từ các bước trước. Vai trò: năm outer folds; trong mỗi outer-training chia 80/10/10 cho fit, stopping và calibration. Scaler/AE fold-local chỉ phục vụ scalar p. Outer holdout không được dùng trong các thao tác fit/stop/calibration sinh feature của chính nó. Final classifier dùng common representation, toàn train và validation cho stopping. Final Platt fit raw OOF, chỉ áp lên final validation/test. Không cần chạy script calibration riêng.

Output:

- `models/stage1/<R>/xgboost_latent/fold_1...fold_5/`: fit_indices.npy, stop_indices.npy, calibration_indices.npy, holdout_indices.npy, scaler.joblib, encoder.pt, encoder_history.json, classifier.json, platt.joblib nếu bật calibration;
- cùng thư mục model: final.json và platt_calibrator.joblib;
- `data/processed/experiments/<R>/stage1_xgboost_latent_p_attack_all.npy` và sidecar;
- `results/stage1/<R>/xgboost_latent/`: metrics.json, oof_train_indices.npy, raw_oof.npy;
- `artifacts/metadata/stage1/<R>/xgboost_latent.json`.

Thành công: status completed, xác suất nằm trong `[0,1]`, đủ N hàng, fold scopes rời nhau. Main không có NaN; LOACO chỉ có NaN tại heldout train/validation đã loại, không được có NaN ở test. Thiếu contract phải chạy upstream mới, không copy/đổi tên artifacts từ main cũ. Cache features tạm được dọn sau từng fold; scaler, model và indices vẫn được giữ.

Đối chứng Stage 1 cùng split/config, chạy tuần tự sau khi chốt budget; có thể thêm `--check-only` trước mỗi lệnh:

```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts\03_train_stage1.py --run-id $R --protocol revised_v1 --model xgboost --representation scaled
.\.venv\Scripts\python.exe -X utf8 -B scripts\03_train_stage1.py --run-id $R --protocol revised_v1 --model mlp --representation scaled
.\.venv\Scripts\python.exe -X utf8 -B scripts\03_train_stage1.py --run-id $R --protocol revised_v1 --model mlp --representation latent
```

Tag/output tương ứng: xgboost_scaled, mlp_scaled, mlp_latent. MLP lưu `.pt` thay `.json` và thêm history. Scaled dùng scaler per-run/fold-local, không dùng scaled array legacy để sinh OOF. Metrics gồm raw OOF, calibrated OOF, validation và test; giữ cùng metric set. Brier có sẵn, nhưng ECE/reliability curves và independent model-reload benchmark còn thiếu.

## E. Stage 2: known-attack classification

Ví dụ dùng p của XGB latent, như gate lịch sử; đây không phải tuyên bố cấu hình thắng mọi trường hợp:

```powershell
$PAttack = Join-Path (Get-Location) "data\processed\experiments\$R\stage1_xgboost_latent_p_attack_all.npy"
.\.venv\Scripts\python.exe -X utf8 -B scripts\04_train_stage2.py --run-id $R --protocol revised_v1 --experiment latent_only --check-only
.\.venv\Scripts\python.exe -X utf8 -B scripts\04_train_stage2.py --run-id $R --protocol revised_v1 --experiment latent_only
.\.venv\Scripts\python.exe -X utf8 -B scripts\04_train_stage2.py --run-id $R --protocol revised_v1 --experiment latent_plus_pattack_xgb --p-attack-path "$PAttack"
.\.venv\Scripts\python.exe -X utf8 -B scripts\04_train_stage2.py --run-id $R --protocol revised_v1 --experiment latent_plus_pattack_mlp --p-attack-path "$PAttack"
```

Input: latent common, known-attack indices và p khi cần. Script tự tạo ma trận `[z,p]`; không cần bước ghép meta-feature thủ công. Stage 2 không train BENIGN và loại heldout khi làm LOACO. Control MLP latent-only tùy chọn sau khi chốt kế hoạch:

```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts\04_train_stage2.py --run-id $R --protocol revised_v1 --experiment latent_only_mlp
```

Output mỗi `<variant>`: `models/stage2/<R>/<variant>/final.json` hoặc `.pt`; `results/stage2/<R>/<variant>/` chứa validation_indices.npy, validation_probabilities.npy, test_indices.npy, test_probabilities.npy, class_ids.npy, metrics.json, contract.json; MLP có history.json. Metadata: `artifacts/metadata/stage2/<R>/<variant>.json`.

Thành công: main có 26 attack classes, input dimension 16/17, probabilities hữu hạn và tổng mỗi hàng xấp xỉ 1; test indices chứa mọi test flow. `known_test_metrics` là oracle known-attack subset, không phải cascade cuối. Chọn variant theo validation macro-F1 đã quy định, không đảo lựa chọn theo test. P-attack/run/heldout/hash mismatch phải được điều tra ở upstream, không sửa JSON để vượt kiểm tra.

## F. Closed-set end-to-end

Mỗi evaluation dùng ID riêng. Ví dụ latent-only:

```powershell
$S2 = Join-Path (Get-Location) "results\stage2\$R\latent_only"
$E = "eval_rev_main_20261026_latent_v1"
.\.venv\Scripts\python.exe -X utf8 -B scripts\06_evaluate_pipeline.py --run-id $E --p-attack-path "$PAttack" --stage2-result-dir "$S2" --check-only
.\.venv\Scripts\python.exe -X utf8 -B scripts\06_evaluate_pipeline.py --run-id $E --p-attack-path "$PAttack" --stage2-result-dir "$S2"
```

Input: p, Stage 2 probabilities/class IDs/indices/contracts và Phase 2 identity. Vai trò: dùng predicted gate 0,5 rồi Stage 2 argmax; đánh giá toàn test, không dùng ground truth để routing.

Output: `results/pipeline/<E>/metrics.json`, test_predictions.csv.gz, contract.json. Thành công: đúng N test, có per-class/confusion matrix, FPR/FNR, error decomposition và các aggregate metric cũ; CSV có row_hash đúng thứ tự. Check-only validate và compose trong RAM, không ghi output, không tính metrics/bootstrap. Pass không chứng minh split độc lập.

Để đánh giá variant khác, đổi `$S2` và `$E`. Nếu Stage 2 dùng meta-feature, phải dùng đúng p đã dùng khi train Stage 2. Thời gian composition chỉ là ghép scores đã lưu. **NOT REPRODUCIBLE** cho raw-to-model latency/throughput: chưa có entrypoint frozen raw-to-final và benchmark đầy đủ.

## G. LOACO: toàn bộ chain riêng cho từng heldout

Ví dụ ID 26 là DDoS trong mapping hiện tại; phải kiểm mapping nếu đổi dữ liệu. Unknown không được vào scaler/AE/Stage 1/calibration/Stage 2/novelty fitting. Transform và predict unknown test bằng tham số đã đóng băng là hợp lệ.

```powershell
$L = "rev_loaco26_20261026_s42_v1"
.\.venv\Scripts\python.exe -X utf8 -B scripts\01b_prepare_protocol.py --run-id $L --held-out-label-id 26 --check-only
.\.venv\Scripts\python.exe -X utf8 -B scripts\01b_prepare_protocol.py --run-id $L --held-out-label-id 26
.\.venv\Scripts\python.exe -X utf8 -B scripts\02_train_autoencoder.py --run-id $L --protocol revised_v1 --held-out-label-id 26
.\.venv\Scripts\python.exe -X utf8 -B scripts\03_train_stage1.py --run-id $L --protocol revised_v1 --model xgboost --representation latent --held-out-label-id 26
.\.venv\Scripts\python.exe -X utf8 -B scripts\04_train_stage2.py --run-id $L --protocol revised_v1 --experiment latent_only --held-out-label-id 26
```

Output giống C3/D/E nhưng dưới `<L>`. Với snapshot hiện tại, scaler fit scope phải là 1.401.162 known-train rows; Stage 2 có known class set bỏ ID 26. Đây là expectation đã đối chiếu, không phải corrected full run đã hoàn thành. Có thể chạy `--check-only` cho 02–04 sau khi upstream sẵn sàng.

### G1. Novelty với known-validation threshold

```powershell
$LS2 = Join-Path (Get-Location) "results\stage2\$L\latent_only"
.\.venv\Scripts\python.exe -X utf8 -B scripts\05_train_novelty.py --run-id $L --protocol revised_v1 --held-out-label-id 26 --stage2-result-dir "$LS2" --ae-metadata "artifacts\metadata\autoencoder\$L\run.json" --stage1-metadata "artifacts\metadata\stage1\$L\xgboost_latent.json" --stage2-metadata "artifacts\metadata\stage2\$L\latent_only.json" --methods max_probability one_class_svm isolation_forest --check-only
.\.venv\Scripts\python.exe -X utf8 -B scripts\05_train_novelty.py --run-id $L --protocol revised_v1 --held-out-label-id 26 --stage2-result-dir "$LS2" --ae-metadata "artifacts\metadata\autoencoder\$L\run.json" --stage1-metadata "artifacts\metadata\stage1\$L\xgboost_latent.json" --stage2-metadata "artifacts\metadata\stage2\$L\latent_only.json" --methods max_probability one_class_svm isolation_forest
```

Input: latent known train, Stage 2 known-validation/all-test probabilities, metadata và sidecars. Vai trò: MCP dùng `1-maxp`; OCSVM/IF fit known attacks với sample caps; mỗi score chọn q95 trên known-attack validation. Không chọn method hoặc threshold bằng unknown test.

Output:

- `results/novelty/<L>/heldout_26/latent_only/`: `<method>_test_scores.npy`, `<method>_validation_scores.npy`, test_indices.npy, metrics.json, contract.json;
- `models/novelty/<L>/heldout_26/latent_only/`: model OCSVM/IF; MCP không có model riêng;
- `artifacts/thresholds/<L>/heldout_26/latent_only/<method>.json`;
- `artifacts/metadata/novelty/<L>/heldout_26_latent_only.json`.

Thành công: đúng known-validation indices và heldout ancestry; `selected_on=known_validation_only`; scores hữu hạn. Protocol hiện yêu cầu ít nhất 500 heldout test samples; nếu không đủ thì báo giới hạn support, không hạ điều kiện hậu nghiệm để qua check. Paths mới có variant Stage 2; paths legacy không tương đương. Chạy cả ba methods trong một invocation nếu muốn so sánh; không thêm method vào output cũ bằng cách ghi đè.

### G2. Final open-set sau gate

```powershell
$LP = Join-Path (Get-Location) "data\processed\experiments\$L\stage1_xgboost_latent_p_attack_all.npy"
.\.venv\Scripts\python.exe -X utf8 -B scripts\06_evaluate_pipeline.py --run-id eval_rev_loaco26_mcp_v1 --p-attack-path "$LP" --stage2-result-dir "$LS2" --held-out-label-id 26 --novelty-result-dir "results\novelty\$L\heldout_26\latent_only" --novelty-method max_probability --novelty-threshold-json "artifacts\thresholds\$L\heldout_26\latent_only\max_probability.json" --check-only
.\.venv\Scripts\python.exe -X utf8 -B scripts\06_evaluate_pipeline.py --run-id eval_rev_loaco26_mcp_v1 --p-attack-path "$LP" --stage2-result-dir "$LS2" --held-out-label-id 26 --novelty-result-dir "results\novelty\$L\heldout_26\latent_only" --novelty-method max_probability --novelty-threshold-json "artifacts\thresholds\$L\heldout_26\latent_only\max_probability.json"
```

Output: `results/pipeline/eval_rev_loaco26_mcp_v1/` chứa metrics, prediction CSV và contract. Đọc riêng `score_only_unknown_metrics`, `final_unknown_metrics`, conditional known-attack metrics và full end-to-end metrics. Legacy alias `open_set_metrics` không phải unknown metric cuối.

Với IF/OCSVM, đổi method, threshold file và evaluation ID tương ứng. Mỗi heldout khác cần toàn chain riêng; không mượn scaler/encoder từ main. Corrective full LOACO chưa chạy; multi-heldout và nghiệm thu thực tế còn thiếu.

## H. Replay lịch sử, không hợp thức hóa protocol cũ

```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts\06_evaluate_pipeline.py --run-id legacy_readonly_probe --p-attack-path data\processed\experiments\main\stage1_xgboost_latent_p_attack_all.npy --stage2-result-dir results\stage2\main\latent_only --allow-legacy-artifacts --check-only
```

Lệnh tương đương đã PASS trên 314.521 test rows, không ghi output. Nếu xuất báo cáo phải dùng ID mới và bỏ check-only; report vẫn mang `legacy_replay_UNVERIFIED_LINEAGE`. Không có cờ legacy để cho phép training mới bằng artifacts cũ. Bốn final prediction arrays lịch sử đã replay khớp; chưa reload model checkpoints để tái sinh probabilities.

## I. External adapters

```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts\07_inspect_external.py --dataset CSE-CIC-IDS2018 --rows-per-file 1000
.\.venv\Scripts\python.exe -X utf8 -B scripts\07_inspect_external.py --dataset CIC-UNSW-NB15 --full
```

Input mặc định: `data/external/<dataset>`. CSE đọc `.csv`; UNSW đọc Data.csv và Lable.csv có header Label. Output là JSON trên stdout. `--output docs\research_alignment\external_check_new.json` lưu file mới và từ chối overwrite; `--data-dir` đổi nguồn; `--feature-metadata` đổi primary schema để đối chiếu.

Đã kiểm adapter: CSE prefix 1.000 dòng mỗi chín CSV, tổng 9.000 dòng, 78 native features; UNSW full 447.915 dòng, 76 features, X/y cùng số hàng. Prefix counts không phải phân phối toàn dataset. File CSE đuôi `.csv.757702C0` chưa xác nhận completeness, không được tự đổi tên để đưa vào pipeline.

**NOT REPRODUCIBLE hiện tại:** full external training và zero-shot cross-dataset inference. Thiếu phê duyệt shared features/units/extractor/label ontology, external split/training integration và frozen inference entrypoint. `configs/external_shared_features.template.json` cố ý để `approved:false`, mapping rỗng. Không zero-fill cho đủ 84 chiều. Retrain riêng trên mỗi dataset là intra-dataset replication, không phải chuyển miền không retrain.

## J. Checklist nghiệm thu

- [ ] Đúng root/interpreter; lưu config, source version/hash và package versions trước run.
- [ ] Raw integrity, schema, label mapping, row/split identities khớp; nguồn và target policy được giải trình.
- [ ] Không overwrite; upstream đều completed. Status running sau crash là incomplete; không resume ngầm hoặc sửa sidecar để qua check.
- [ ] Scaler fit chỉ train và loại heldout; latent/p/probabilities đúng thứ tự; OOF fit/stop/calibration/holdout rời nhau.
- [ ] Không ghép latent từ các encoder fold vào Stage 2; chỉ ghép scalar p với latent common.
- [ ] Metrics có population/support rõ ràng; confusion class order đúng; error partitions cộng đúng; unknown cuối gồm gate và benign.
- [ ] Model/threshold/budget được chốt trước test; test cũ đã xem phải gọi exploratory.
- [ ] Giữ logs cả run thành công/thất bại; seed mới không được coi là test độc lập mới.
- [ ] Chưa tuyên bố real-time, real-world zero-day, cross-dataset superiority hoặc novelty khi chỉ có code/tests.

Lỗi thường gặp: CUDA/OOM → verify môi trường, chỉ một job, giảm batch trong config và run ID mới; NaN/order/hash mismatch → kiểm upstream, không sửa số liệu; access denied/file lock trên Windows → kiểm quyền và process giữ memmap, không xóa dữ liệu rộng; missing attack class → kiểm mapping/coverage/heldout, không relabel để nâng score.

Hướng dẫn cung cấp các entrypoint và output contracts có thật. Full reproduction từ máy sạch, full GPU runs, uncertainty và benchmark thực tế vẫn cần kiểm chứng theo [báo cáo validity](03_experiment_validity_report.md).
