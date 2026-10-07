# Hướng dẫn huấn luyện pipeline IDS

Tài liệu này dành cho việc chạy trong Visual Studio Code trên máy hiện tại:

- GPU: NVIDIA GeForce RTX 3050 Laptop GPU, VRAM 4 GB;
- tài nguyên hệ thống quan sát được: khoảng 16 GB RAM, 12 logical processors;
- driver NVIDIA: 610.62, báo mức tương thích CUDA tối đa 13.3;
- môi trường hỗ trợ: Python 3.10-3.12 (ưu tiên bản mới nhất đã cài), PyTorch 2.13.0 wheel `cu130`, XGBoost 3.4.2;
- dữ liệu Phase 2: 2.096.804 dòng, 84 đặc trưng, split train/validation/test cố định.

Không cài CUDA Toolkit chỉ để chạy pipeline. PyTorch wheel đã mang CUDA runtime. `nvcc`
chỉ cần khi tự biên dịch extension CUDA.

## 1. Cài môi trường trong VS Code

Script tự chọn Python 64-bit mới nhất trong các bản 3.12, 3.11 và 3.10 đã đăng ký với
`py launcher`. Mở thư mục `D:\CAO HOC\IDS System` trong VS Code, rồi chạy:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows_cuda.ps1
```

Muốn buộc dùng một phiên bản cụ thể, truyền tham số, ví dụ
`-PythonVersion 3.12`. Dùng `py -0p` để xem các phiên bản Python đã cài.

Chọn interpreter `.venv\Scripts\python.exe`, sau đó xác minh:

```powershell
.\.venv\Scripts\python.exe scripts\verify_environment.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`verify_environment.py` chỉ thực hiện phép toán tensor rất nhỏ để kiểm tra CUDA; không
khởi tạo hay huấn luyện mô hình.

## 2. Kiểm tra trước khi chạy

Mọi script huấn luyện có `--check-only`. Chế độ này kiểm tra config, hình dạng và đường
dẫn đầu vào rồi thoát trước khi khởi tạo model:

```powershell
.\.venv\Scripts\python.exe scripts\02_train_autoencoder.py --check-only
```

Các script sau phụ thuộc artifact của script trước, nên `--check-only` của chúng chỉ chạy
được sau khi artifact đầu vào đã tồn tại.

## 3. Thí nghiệm closed-set chính

### 3.1 Autoencoder

```powershell
.\.venv\Scripts\python.exe scripts\02_train_autoencoder.py --run-id main
```

Kiến trúc mặc định: `84 -> 64 -> 32 -> 16 -> 32 -> 64 -> 84`, MSE loss, AdamW,
AMP FP16, batch 8192 và early stopping theo validation MSE. Test không tham gia fit,
chọn epoch hay ngưỡng.

### 3.2 Stage 1: BENIGN/ATTACK

Chạy đủ bốn cấu hình để có baseline và ablation:

```powershell
.\.venv\Scripts\python.exe scripts\03_train_stage1.py --run-id main --model xgboost --representation scaled
.\.venv\Scripts\python.exe scripts\03_train_stage1.py --run-id main --model mlp --representation scaled
.\.venv\Scripts\python.exe scripts\03_train_stage1.py --run-id main --model xgboost --representation latent
.\.venv\Scripts\python.exe scripts\03_train_stage1.py --run-id main --model mlp --representation latent
```

Mỗi cấu hình tạo xác suất train bằng 5-fold out-of-fold (OOF). Platt scaling chỉ fit
trên OOF train. Xác suất validation/test đến từ model cuối fit trên train. Vì vậy,
`P_attack` có thể đưa sang Stage 2 mà không tạo stacking leakage.

### 3.3 Stage 2: phân loại kiểu tấn công

Ví dụ dùng `P_attack` của Stage 1 XGBoost latent:

```powershell
$PAttack = "data\processed\experiments\main\stage1_xgboost_latent_p_attack_all.npy"

.\.venv\Scripts\python.exe scripts\04_train_stage2.py --run-id main --experiment latent_only
.\.venv\Scripts\python.exe scripts\04_train_stage2.py --run-id main --experiment latent_plus_pattack_xgb --p-attack-path $PAttack
.\.venv\Scripts\python.exe scripts\04_train_stage2.py --run-id main --experiment latent_plus_pattack_mlp --p-attack-path $PAttack
```

Stage 2 chỉ fit trên attack flows. BENIGN không được biến thành một lớp trong Stage 2.
Class weight cân bằng được tính từ train. Validation dùng early stopping; test chỉ dùng
đánh giá cuối.

## 4. Thí nghiệm zero-day đúng chuẩn LOACO

Không được lấy model `main` rồi chỉ giấu một lớp ở bước novelty. Với mỗi lớp tấn công
được giữ lại, phải huấn luyện lại AE, Stage 1 và Stage 2 bằng cùng một ID. Ví dụ giữ lại
label ID 26 (DDoS):

```powershell
$Run = "loaco_26"
$HeldOut = 26

.\.venv\Scripts\python.exe scripts\02_train_autoencoder.py --run-id $Run --held-out-label-id $HeldOut
.\.venv\Scripts\python.exe scripts\03_train_stage1.py --run-id $Run --model xgboost --representation latent --held-out-label-id $HeldOut

$PAttack = "data\processed\experiments\$Run\stage1_xgboost_latent_p_attack_all.npy"
.\.venv\Scripts\python.exe scripts\04_train_stage2.py --run-id $Run --experiment latent_plus_pattack_xgb --p-attack-path $PAttack --held-out-label-id $HeldOut
```

Sau đó fit ba detector novelty. Script sẽ từ chối chạy nếu metadata của AE/Stage 1/
Stage 2 không chứng minh rằng cùng lớp đã bị loại khỏi train và validation:

```powershell
$Stage2 = "results\stage2\$Run\latent_plus_pattack_xgb"
$AeMeta = "artifacts\metadata\autoencoder\$Run\run.json"
$S1Meta = "artifacts\metadata\stage1\$Run\xgboost_latent.json"
$S2Meta = "artifacts\metadata\stage2\$Run\latent_plus_pattack_xgb.json"

.\.venv\Scripts\python.exe scripts\05_train_novelty.py `
  --run-id $Run --held-out-label-id $HeldOut `
  --stage2-result-dir $Stage2 `
  --ae-metadata $AeMeta --stage1-metadata $S1Meta --stage2-metadata $S2Meta
```

Ngưỡng novelty lấy từ phân vị 95% của known validation, tương ứng mục tiêu từ chối nhầm
5% known attacks. Held-out test tuyệt đối không dùng fit detector hay chọn ngưỡng.

## 5. Đánh giá end-to-end

Ví dụ với max-probability detector:

```powershell
$Novelty = "results\novelty\$Run\heldout_$HeldOut"
$Threshold = "artifacts\thresholds\$Run\heldout_$HeldOut\max_probability.json"

.\.venv\Scripts\python.exe scripts\06_evaluate_pipeline.py `
  --run-id $Run --held-out-label-id $HeldOut `
  --p-attack-path $PAttack --stage2-result-dir $Stage2 `
  --novelty-result-dir $Novelty --novelty-method max_probability `
  --novelty-threshold-json $Threshold
```

Đầu ra gồm metric nhị phân, metric đa lớp end-to-end, open-set metric, khoảng tin cậy
bootstrap 95% cho accuracy và file dự đoán nén có `row_hash` để truy vết.

## 6. Lưu ý GPU và khả năng tái lập

- Batch AE/MLP 8192 là điểm bắt đầu cho VRAM 4 GB. Nếu CUDA OOM, giảm lần lượt
  8192 -> 4096 -> 2048; không thay đổi split và phải dùng `run-id` mới.
- XGBoost dùng `tree_method=hist`, `device=cuda:0`, `max_bin=128`. Nếu vẫn OOM,
  giảm `max_bin` xuống 64 hoặc `max_depth` xuống 6 và ghi rõ thành thí nghiệm khác.
- `num_workers=0` tránh lỗi multiprocessing phổ biến trên Windows và dữ liệu memmap.
- AMP FP16 và TF32 ưu tiên tốc độ. Muốn so sánh lặp lại nghiêm ngặt, đặt
  `deterministic_algorithms=true`, `cudnn_benchmark=false`; chấp nhận chạy chậm hơn.
- Không chạy song song XGBoost và PyTorch trên GPU 4 GB.
- One-Class SVM được giới hạn 20.000 mẫu latent cân bằng gần đều theo lớp vì RBF-SVM
  tăng chi phí nhanh theo số mẫu; Isolation Forest dùng tối đa 100.000 mẫu cân bằng.
- Không ghi đè `run-id` giữa các cấu hình hoặc giữa closed-set và LOACO.

## 7. Artifact quan trọng

- `models/`: checkpoint/model đã huấn luyện (không commit Git);
- `data/processed/experiments/<run-id>/`: latent và `P_attack` căn hàng với Phase 2;
- `artifacts/metadata/`: provenance, held-out label và hợp đồng chống leakage;
- `artifacts/thresholds/`: ngưỡng chọn trên validation;
- `results/`: metric, xác suất Stage 2, novelty score và dự đoán cuối.
