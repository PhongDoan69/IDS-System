# Hướng dẫn huấn luyện pipeline IDS

> HƯỚNG DẪN LỊCH SỬ — Cập nhật chỉ dẫn ngày 26/10/2026:
> source mới yêu cầu `--protocol revised_v1`, preprocessing per-run và lineage mới.
> Dùng [PIPELINE_REPRODUCTION_GUIDE.md](research_alignment/PIPELINE_REPRODUCTION_GUIDE.md)
> cho training mới. Các checklist/ngày/lệnh bên dưới là lịch sử, không phản ánh trạng thái hiện tại.
> Đã có legacy end-to-end/LOACO nhưng còn lỗi validity theo audit; không ghi đè `main`/`loaco_26`.
> XGBoost pin/runtime hiện tại được kiểm là **3.2.0**, không phải 3.4.2 được ghi trong phần cũ.

Tài liệu này dành cho việc chạy trong Visual Studio Code trên máy hiện tại:

- GPU: NVIDIA GeForce RTX 3050 Laptop GPU, VRAM 4 GB;
- tài nguyên hệ thống quan sát được: khoảng 16 GB RAM, 12 logical processors;
- driver NVIDIA: 610.62, báo mức tương thích CUDA tối đa 13.3;
- môi trường hỗ trợ: Python 3.10-3.12 (ưu tiên bản mới nhất đã cài), PyTorch 2.13.0 wheel `cu130`, XGBoost 3.4.2;
- dữ liệu Phase 2: 2.096.804 dòng, 84 đặc trưng, split train/validation/test cố định.

Không cài CUDA Toolkit chỉ để chạy pipeline. PyTorch wheel đã mang CUDA runtime. `nvcc`
chỉ cần khi tự biên dịch extension CUDA.

## Trạng thái thực nghiệm hiện tại (09/10/2026)

- [x] Cài và xác minh môi trường Python/CUDA.
- [x] Phase 2: làm sạch, chia tập và chuẩn hóa dữ liệu.
- [x] Autoencoder `main` và latent 16 chiều.
- [x] Stage 1: bốn cấu hình XGBoost/MLP trên scaled/latent, có xác suất OOF.
- [x] Stage 2: `latent_only`, `latent_plus_pattack_xgb` và
  `latent_plus_pattack_mlp`.
- [ ] **Bước tiếp theo:** đánh giá closed-set end-to-end bằng script 06.
- [ ] Thực nghiệm LOACO/zero-day và novelty detection.
- [ ] Tổng hợp bảng kết quả, confusion matrix và phân tích sai số cho luận văn.

Không chạy lại một bước đã đánh dấu hoàn tất nếu không thay đổi cấu hình hoặc `run-id`.
Chạy lại với cùng `run-id` có thể ghi đè artifact và làm mất khả năng truy vết kết quả.

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

**Vai trò:** giảm 84 đặc trưng đã chuẩn hóa xuống vector latent 16 chiều, loại bớt
nhiễu và tạo cùng một không gian biểu diễn cho Stage 1, Stage 2 và novelty detector.

**Đầu vào:** `data/processed/features_scaled.npy` và split ID cố định của Phase 2.

```powershell
.\.venv\Scripts\python.exe scripts\02_train_autoencoder.py --run-id main
```

Kiến trúc mặc định: `84 -> 64 -> 32 -> 16 -> 32 -> 64 -> 84`, MSE loss, AdamW,
AMP FP16, batch 8192 và early stopping theo validation MSE. Test không tham gia fit,
chọn epoch hay ngưỡng.

**Đầu ra cần kiểm tra:**

- `models/autoencoder/main/best.pt`;
- `data/processed/experiments/main/latent_features.npy`;
- `artifacts/metadata/autoencoder/main/run.json`;
- `results/autoencoder/main/history.json`.

**Lưu ý:** latent phải có đúng 2.096.804 dòng và giữ nguyên thứ tự Phase 2. Không tạo
latent riêng cho từng split rồi ghép thủ công vì dễ làm lệch nhãn và `row_hash`.

### 3.2 Stage 1: BENIGN/ATTACK

**Vai trò:** cổng phát hiện nhị phân. Nếu `P_attack` dưới ngưỡng, flow được gán BENIGN;
nếu vượt ngưỡng, flow mới đi tiếp sang Stage 2. `P_attack` còn là đặc trưng stacking
trong các thí nghiệm Stage 2 có hậu tố `plus_pattack`.

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

**Đầu ra quan trọng:**

- `data/processed/experiments/main/stage1_<model>_<representation>_p_attack_all.npy`;
- `results/stage1/main/<model>_<representation>/metrics.json`;
- model cuối và năm model OOF trong `models/stage1/main/`.

**Kiểm tra trước khi sang Stage 2:** số dòng `P_attack` phải bằng 2.096.804; train dùng
OOF, validation/test dùng model cuối; không được tự tính lại xác suất train bằng chính
model đã fit trên toàn bộ train.

### 3.3 Stage 2: phân loại kiểu tấn công

**Vai trò:** chỉ phân loại các flow được xem là tấn công thành một trong 26 nhãn attack.
Ba cấu hình dưới đây là ablation để đo đóng góp của `P_attack` và loại mô hình.

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

**Kết quả đã xác nhận:**

| Thí nghiệm | Validation macro-F1 | Test macro-F1 | Test balanced accuracy | Test accuracy |
|---|---:|---:|---:|---:|
| `latent_only` XGBoost | **0,88094** | 0,90239 | 0,91397 | 0,98185 |
| `latent_plus_pattack_xgb` | 0,85813 | **0,91087** | **0,92917** | 0,98183 |
| `latent_plus_pattack_mlp` | 0,73163 | 0,75756 | 0,90720 | 0,93958 |

Mô hình chính phải được chọn bằng validation, không chọn bằng test. Theo quy tắc đó,
`latent_only` XGBoost là cấu hình chính hiện tại. XGBoost + `P_attack` và MLP được giữ
làm ablation. Việc XGBoost + `P_attack` có test macro-F1 cao hơn chỉ được báo cáo như
kết quả quan sát, không dùng để thay đổi quyết định sau khi đã xem test.

MLP dừng sau 39 epoch và checkpoint tốt nhất đã được nạp lại. Kết quả thấp hơn XGBoost
không phải lỗi chạy; đây là bằng chứng thực nghiệm rằng mô hình cây phù hợp hơn với biểu
diễn tabular hiện tại.

**Artifact của lần chạy MLP vừa hoàn tất:**

- `models/stage2/main/latent_plus_pattack_mlp/final.pt`;
- `results/stage2/main/latent_plus_pattack_mlp/metrics.json`;
- `history.json`, `class_ids.npy`, validation/test probabilities và indices.

### 3.4 Bước tiếp theo: đánh giá closed-set end-to-end

**Vai trò:** ghép cổng Stage 1 với Stage 2 thành hệ thống IDS hoàn chỉnh và đánh giá theo
đúng đường đi triển khai: `flow -> P_attack -> BENIGN hoặc lớp tấn công`. Đây là kết quả
closed-set nền để so sánh với hệ thống open-set/zero-day ở Phase LOACO.

Đầu tiên đánh giá cấu hình chính được chọn bằng validation:

```powershell
$Python = ".\.venv\Scripts\python.exe"
$PAttack = "data\processed\experiments\main\stage1_xgboost_latent_p_attack_all.npy"
$Stage2 = "results\stage2\main\latent_only"

# Chỉ kiểm tra hợp đồng file và thứ tự test; không tính metric hay ghi prediction.
& $Python scripts\06_evaluate_pipeline.py `
  --run-id eval_main_latent_only `
  --p-attack-path $PAttack --stage2-result-dir $Stage2 --check-only

# Chạy đánh giá chính thức.
& $Python scripts\06_evaluate_pipeline.py `
  --run-id eval_main_latent_only `
  --p-attack-path $PAttack --stage2-result-dir $Stage2
```

Sau đó đánh giá hai ablation bằng `run-id` khác để không ghi đè:

```powershell
$Stage2 = "results\stage2\main\latent_plus_pattack_xgb"
& $Python scripts\06_evaluate_pipeline.py `
  --run-id eval_main_pattack_xgb `
  --p-attack-path $PAttack --stage2-result-dir $Stage2

$Stage2 = "results\stage2\main\latent_plus_pattack_mlp"
& $Python scripts\06_evaluate_pipeline.py `
  --run-id eval_main_pattack_mlp `
  --p-attack-path $PAttack --stage2-result-dir $Stage2
```

**Đầu ra:**

- `results/pipeline/<eval-run-id>/metrics.json`: metric Stage 1, macro/weighted F1,
  balanced accuracy và bootstrap 95% CI cho accuracy;
- `results/pipeline/<eval-run-id>/test_predictions.csv.gz`: nhãn thật, nhãn dự đoán,
  `P_attack` và `row_hash` của từng mẫu test.

**Tiêu chí hoàn tất:** script kết thúc không lỗi, `test_samples=314521`, file metric có
`stage1_test_metrics`, `end_to_end_metrics` và `accuracy_bootstrap_95ci`. Chưa thêm
novelty arguments ở bước này vì `main` là closed-set và không có held-out class.

**Lưu ý:** không dùng kết quả test của ba lần đánh giá để tinh chỉnh threshold hoặc
hyperparameter. Nếu cần thay đổi mô hình, phải quyết định bằng train/validation và tạo
`run-id` mới trước khi xem test lần tiếp theo.

## 4. Thí nghiệm zero-day đúng chuẩn LOACO

**Vai trò:** mô phỏng lớp tấn công chưa từng xuất hiện trong quá trình học và đo khả
năng gắn nhãn `UNKNOWN_ATTACK`. Đây là phần khác biệt quan trọng giữa một bộ phân loại
closed-set thông thường và hệ thống IDS có khả năng hỗ trợ phát hiện zero-day.

Không được lấy model `main` rồi chỉ giấu một lớp ở bước novelty. Với mỗi lớp tấn công
được giữ lại, phải huấn luyện lại AE, Stage 1 và Stage 2 bằng cùng một ID. Ví dụ giữ lại
label ID 26 (DDoS):

Các label đủ điều kiện `minimum_held_out_samples=500` trên test là 2, 5, 8, 9, 11,
18, 23, 25 và 26. Đối với báo cáo chính nên ưu tiên các lớp tấn công không mang hậu tố
`Attempted`: 2 (FTP-Patator), 5 (DoS Slowloris), 9 (DoS Hulk), 11 (DoS GoldenEye),
18 (Infiltration-Portscan), 25 (Portscan) và 26 (DDoS). Chạy ID 26 trước để xác minh
toàn bộ quy trình, sau đó mới mở rộng sang các ID còn lại.

```powershell
$Run = "loaco_26"
$HeldOut = 26

.\.venv\Scripts\python.exe scripts\02_train_autoencoder.py --run-id $Run --held-out-label-id $HeldOut
.\.venv\Scripts\python.exe scripts\03_train_stage1.py --run-id $Run --model xgboost --representation latent --held-out-label-id $HeldOut

$PAttack = "data\processed\experiments\$Run\stage1_xgboost_latent_p_attack_all.npy"
.\.venv\Scripts\python.exe scripts\04_train_stage2.py --run-id $Run --experiment latent_only --held-out-label-id $HeldOut
```

Vai trò từng lệnh:

1. Autoencoder không được nhìn thấy held-out class, tránh latent encoder học trực tiếp
   cấu trúc của lớp được tuyên bố là zero-day.
2. Stage 1 loại lớp đó khỏi train/validation và sinh OOF `P_attack` mới cho run LOACO.
3. Stage 2 chỉ học các attack class còn lại; held-out class không xuất hiện trong
   `class_ids.npy`.

`latent_only` được dùng làm cấu hình LOACO chính vì đã thắng theo validation macro-F1
ở thí nghiệm `main`. Có thể chạy thêm `latent_plus_pattack_xgb` như sensitivity
analysis, nhưng không đổi cấu hình chính dựa trên kết quả held-out/test.

Trước mỗi lệnh huấn luyện có thể thêm `--check-only`. Luôn kiểm tra metadata của cả ba
phase có cùng `held_out_label_id`; không tái sử dụng latent hoặc `P_attack` của `main`.

Sau đó fit ba detector novelty. Script sẽ từ chối chạy nếu metadata của AE/Stage 1/
Stage 2 không chứng minh rằng cùng lớp đã bị loại khỏi train và validation:

```powershell
$Stage2 = "results\stage2\$Run\latent_only"
$AeMeta = "artifacts\metadata\autoencoder\$Run\run.json"
$S1Meta = "artifacts\metadata\stage1\$Run\xgboost_latent.json"
$S2Meta = "artifacts\metadata\stage2\$Run\latent_only.json"

.\.venv\Scripts\python.exe scripts\05_train_novelty.py `
  --run-id $Run --held-out-label-id $HeldOut `
  --stage2-result-dir $Stage2 `
  --ae-metadata $AeMeta --stage1-metadata $S1Meta --stage2-metadata $S2Meta
```

Ngưỡng novelty lấy từ phân vị 95% của known validation, tương ứng mục tiêu từ chối nhầm
5% known attacks. Held-out test tuyệt đối không dùng fit detector hay chọn ngưỡng.

Ba detector có vai trò khác nhau:

- `max_probability`: baseline độ tin cậy của Stage 2, không cần fit thêm model;
- `one_class_svm`: học biên của known attacks trong latent space;
- `isolation_forest`: phát hiện điểm bất thường bằng phân hoạch ngẫu nhiên, mở rộng tốt
  hơn OCSVM khi số mẫu lớn.

Chạy OCSVM/Isolation Forest trên CPU; không chạy đồng thời với một job GPU khác. Nếu
quá trình bị gián đoạn, giữ nguyên artifact phase đã hoàn tất và chạy lại đúng lệnh bị
lỗi, không xóa toàn bộ run.

## 5. Đánh giá open-set end-to-end sau LOACO

**Vai trò:** ghép Stage 1, Stage 2 và novelty detector để tạo ba loại quyết định cuối:
BENIGN, known attack class hoặc `UNKNOWN_ATTACK`.

Ví dụ với max-probability detector:

```powershell
$Novelty = "results\novelty\$Run\heldout_$HeldOut"
$Threshold = "artifacts\thresholds\$Run\heldout_$HeldOut\max_probability.json"
$EvalRun = "eval_loaco_26_maxprob"

.\.venv\Scripts\python.exe scripts\06_evaluate_pipeline.py `
  --run-id $EvalRun --held-out-label-id $HeldOut `
  --p-attack-path $PAttack --stage2-result-dir $Stage2 `
  --novelty-result-dir $Novelty --novelty-method max_probability `
  --novelty-threshold-json $Threshold
```

Đầu ra gồm metric nhị phân, metric đa lớp end-to-end, open-set metric, khoảng tin cậy
bootstrap 95% cho accuracy và file dự đoán nén có `row_hash` để truy vết.

Chạy riêng script 06 cho từng novelty method bằng các `run-id` khác nhau, ví dụ
`eval_loaco_26_maxprob`, `eval_loaco_26_ocsvm` và `eval_loaco_26_iforest`. Không ghi
ba phương pháp vào cùng một `run-id` vì `metrics.json` và prediction sẽ bị ghi đè.

Trong luận văn cần báo cáo ít nhất: unknown recall, unknown F1, open-set ROC-AUC,
open-set PR-AUC, known false rejection rate và metric end-to-end. Confusion matrix nên
tách rõ `UNKNOWN_ATTACK` thay vì gộp vào một known class.

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

## 8. Checklist sau mỗi lệnh dài

1. Ghi lại nguyên lệnh, `run-id`, thời gian bắt đầu/kết thúc và GPU được dùng.
2. Xác nhận script in `status=completed` hoặc artifact metadata có trường tương ứng.
3. Kiểm tra file model/metric có kích thước lớn hơn 0 và thời gian sửa đúng lần chạy.
4. Đọc metric validation trước; chỉ đọc test để báo cáo sau khi quyết định mô hình đã
   được khóa.
5. Không sửa trực tiếp `.npy`, checkpoint hoặc probability file.
6. Không chạy hai tiến trình PyTorch/XGBoost cùng lúc trên RTX 3050 4 GB.
7. Nếu OOM, giảm batch/max-bin và tạo `run-id` mới; không âm thầm thay tham số giữa
   các lần chạy cùng ID.
