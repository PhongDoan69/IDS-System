# 02 — Tính đúng đắn của pipeline

Phạm vi: D:\CAO HOC\IDS System, commit 895cc8b, audit 24/10/2026. Các mã E dẫn tới sổ bằng chứng trong [docs/research_audit/01_project_status.md](<D:/CAO HOC/IDS System/docs/research_audit/01_project_status.md>).
Quy ước: CONFIRMED ISSUE = có bằng chứng trực tiếp; POTENTIAL RISK = cơ chế rủi ro nhưng chưa đo ảnh hưởng; NO ISSUE FOUND = chưa thấy lỗi trong phạm vi kiểm tra; NOT VERIFIABLE = chưa đủ bằng chứng để kết luận.

## 1. Dataset và định nghĩa target

### 1.1 Dữ liệu nào thực sự được dùng?

Cấu hình đọc monday.csv, tuesday.csv, wednesday.csv, thursday.csv, friday.csv trong [CICIDS2017](<D:/CAO HOC/IDS System/CICIDS2017>). Metadata ghi 2.099.971 dòng, 89 cột; cleaning bỏ 3.167 full-row duplicate, không bỏ dòng invalid, còn 2.096.804. Mảng đầu vào model là float32, 84 chiều. Audit đọc lại SHA256 cả 5 CSV và khớp raw_manifest local; raw/scaled không có NaN/Inf. Không có bằng chứng thiếu file nào trong 5 file đã cấu hình. Điều này không chứng minh đã có toàn bộ dữ liệu của một bản phát hành upstream xác định.

Nguồn UNB mô tả CICIDS2017 gốc là traffic 5 ngày, có flow features và nhãn. Nhưng tên bộ dữ liệu không đủ xác thực phiên bản CSV. Xem [trang dữ liệu gốc UNB](https://www.unb.ca/cic/datasets/ids-2017.html).

Schema local có Attempted Category, Total TCP Flow Time, ICMP Code/Type và nhãn Infiltration - Portscan. Đây là dấu hiệu phù hợp với nhánh Improved CICIDS2017; đối chiếu [tài liệu kỹ thuật CNS2022](https://intrusion-detection.distrinet-research.be/CNS2022/CICIDS2017.html). Đây là suy luận về nguồn, không phải xác nhận provenance; thiếu URL tải, archive/version và checksum do nhà phát hành cung cấp.

### 1.2 Cảnh báo về Attempted

Nguồn [CNS2022 — Dataset Download](https://intrusion-detection.distrinet-research.be/CNS2022/Dataset_Download.html) giải thích Attempted là flow dự kiến thuộc cuộc tấn công nhưng không biểu hiện hành vi độc hại; trang này không khuyến nghị biến Attempted thành các lớp ML riêng. Đây là cảnh báo về ngữ nghĩa target, không phải chỉ một lựa chọn model.

Local base.json đặt attempted_policy=preserve; src/labels.py chỉ chuẩn hóa whitespace và giữ riêng Attempted; binary_label gán mọi nhãn khác BENIGN thành ATTACK. Vì vậy, hiện tại hệ thống học 27 nhãn chú giải, chưa thể gọi 26 nhãn ngoài BENIGN là 26 loại hành vi tấn công độc lập đã được thẩm định.

Phân loại: CONFIRMED ISSUE về khoảng trống justification cho target; POTENTIAL RISK về sự không phù hợp với chính sách của bản phát hành nghi vấn. Chưa đủ bằng chứng để kết luận bản local chính xác là archive CNS2022 nào.

Hành động cần làm sau audit: xác minh provenance; giữ raw label bất biến, tạo target policy riêng có version; xin thống nhất ngữ nghĩa với người hướng dẫn; thực hiện sensitivity study giữa các chính sách có cơ sở. Không tự sửa nhãn, gộp lớp hay thay dữ liệu trong audit. “Giữ raw label” không đồng nghĩa “bắt buộc coi từng raw label là một lớp ML”.

### 1.3 Phân bố sau cleaning và split

Đếm lại từ attack_label_ids.npy/split_ids.npy; không chỉ chép bảng tài liệu. Tổng train/validation/test = 1.467.762 / 314.521 / 314.521. Tổng attack tương ứng = 359.987 / 77.141 / 77.141.

| ID | Nhãn local | Train | Validation | Test |
|---|---|---:|---:|---:|
| 0 | BENIGN | 1107775 | 237380 | 237380 |
| 1 | FTP-Patator - Attempted | 8 | 2 | 2 |
| 2 | FTP-Patator | 2780 | 596 | 596 |
| 3 | SSH-Patator | 2073 | 444 | 444 |
| 4 | SSH-Patator - Attempted | 19 | 4 | 4 |
| 5 | DoS Slowloris | 2701 | 579 | 579 |
| 6 | DoS Slowloris - Attempted | 1293 | 277 | 277 |
| 7 | DoS Slowhttptest | 1218 | 261 | 261 |
| 8 | DoS Slowhttptest - Attempted | 2358 | 505 | 505 |
| 9 | DoS Hulk | 110928 | 23770 | 23770 |
| 10 | DoS Hulk - Attempted | 407 | 87 | 87 |
| 11 | DoS GoldenEye | 5297 | 1135 | 1135 |
| 12 | Heartbleed | 7 | 2 | 2 |
| 13 | DoS GoldenEye - Attempted | 56 | 12 | 12 |
| 14 | Web Attack - Brute Force - Attempted | 904 | 194 | 194 |
| 15 | Web Attack - Brute Force | 51 | 11 | 11 |
| 16 | Infiltration - Attempted | 31 | 7 | 7 |
| 17 | Infiltration | 26 | 5 | 5 |
| 18 | Infiltration - Portscan | 48038 | 10294 | 10294 |
| 19 | Web Attack - XSS - Attempted | 459 | 98 | 98 |
| 20 | Web Attack - XSS | 12 | 3 | 3 |
| 21 | Web Attack - SQL Injection - Attempted | 3 | 1 | 1 |
| 22 | Web Attack - SQL Injection | 9 | 2 | 2 |
| 23 | Botnet - Attempted | 2847 | 610 | 610 |
| 24 | Botnet | 516 | 110 | 110 |
| 25 | Portscan | 111346 | 23860 | 23860 |
| 26 | DDoS | 66600 | 14272 | 14272 |

Mỗi lớp vẫn xuất hiện nhưng nhiều lớp chỉ có 1–5 mẫu test. Một lỗi làm recall thay đổi rất lớn; không thể suy luận độ ổn định chỉ từ việc “đủ nhãn”.

### 1.4 Cleaning và features

[src/preprocessing.py](<D:/CAO HOC/IDS System/src/preprocessing.py:27>) coercion numeric, chuyển Inf thành NaN, bỏ dòng có numeric invalid; không impute. Zero invalid là kết quả của snapshot, không phải không có logic cleaning.

[configs/base.json](<D:/CAO HOC/IDS System/configs/base.json:18>) loại Label, Attempted Category, Timestamp, Src IP dec, Dst IP dec. Đây là bước loại identifiers/annotation hợp lý. Không thấy Flow ID trong schema local. Src Port, Dst Port, Protocol, Total TCP Flow Time và các flow statistics vẫn được giữ.

- NO ISSUE FOUND: label, Attempted Category, IP và timestamp không có trong 84 feature.
- POTENTIAL RISK: ports/flow statistics có thể ghi nhớ dịch vụ, lịch tấn công hoặc dấu vết lab. Chưa có feature ablation đủ để định lượng.
- POTENTIAL RISK: đặc trưng đòi hỏi flow/connection hoàn tất không tự nhiên tương đương phát hiện trực tuyến thời gian thực; cần định nghĩa thời điểm observation.
- NOT IMPLEMENTED: selector học từ dữ liệu (RFE/MI/SHAP selection...). Không có bằng chứng feature selection dùng test. AE là feature extraction, không phải lựa chọn subset cột.

Label IDs được cấp theo thứ tự xuất hiện tại [scripts/01_prepare_data.py](<D:/CAO HOC/IDS System/scripts/01_prepare_data.py:56>), không hard-code BENIGN=0 lúc tạo map. Snapshot hiện tại có BENIGN=0 và binary nhất quán; thay thứ tự file có thể phá giả định ID0 ở downstream. Đây là POTENTIAL RISK cho các lần chuẩn bị khác, không lỗi của mapping đã kiểm tra.

## 2. Leakage và split — bảng phán định

| Hạng mục | Phán định | Bằng chứng và giới hạn |
|---|---|---|
| Scaler main dùng test để fit | NO ISSUE FOUND | fit chỉ split0 tại E02:147; số mẫu và mean khớp toàn train |
| Validation/test được transform bằng scaler đóng băng | NO ISSUE FOUND | Transform mẫu khớp tuyệt đối với scaled.npy; chưa test deploy từ raw ngoài project |
| Full-row hash overlap | NO ISSUE FOUND trong hash đã lưu | 2.096.804 row_hash khác nhau; không bảo đảm feature độc lập |
| Model-input duplicates giữa split | CONFIRMED ISSUE | 2.253 validation, 2.213 test có toàn bộ 84 float32 feature bằng một hàng train |
| Near-duplicates/session overlap | NOT VERIFIABLE | Chưa dựng session/time groups hoặc khoảng cách near-duplicate |
| Random split tạo generalization quá lạc quan | POTENTIAL RISK | E05 trộn trong lớp, không group theo host/session/day |
| Strict LOACO scaler | CONFIRMED ISSUE | Scaler chứa 66.600 train DDoS; không có scaler riêng theo heldout |
| Fold validation dùng để early stop chính OOF | CONFIRMED ISSUE | E07:86–122 dùng outer holdout cả để chọn model lẫn tạo OOF |
| Calibration của feature OOF | CONFIRMED ISSUE | E07:124–128 calibrate trên toàn OOF target rồi áp lại cùng hàng |
| Scaler/encoder không fold-local | CONFIRMED ISSUE về strict cross-fitting | AE/scaler đã fit toàn outer train; tiếp xúc X của OOF holdout; khác với label leakage |
| Final model early stopping dùng validation | NO ISSUE FOUND | Source Stage 1/2/AE truyền validation, không test |
| Novelty threshold dùng unknown test | NO ISSUE FOUND trong code/array hiện tại | q95 known-validation; heldout bị loại khỏi validation index; số liệu khớp |
| Test dùng để con người chọn model sau khi xem | NOT VERIFIABLE | Script sinh test metric ngay trong train; không có immutable selection log trước test |
| Run-id/path gây trộn artifact | POTENTIAL RISK | CLI nhận đường dẫn độc lập; kiểm tra ancestry chưa đủ |
| Mức metric bị thổi phồng bao nhiêu | NOT VERIFIABLE | Chưa rerun protocol sạch/paired ablation; không bịa mức suy giảm |

### 2.1 Duplicate không phải hash collision

Code hash toàn 89 cột tại [src/data_loader.py](<D:/CAO HOC/IDS System/src/data_loader.py:66>) và E02:44, trước khi loại IP/time/label. Hai flow khác timestamp/IP có thể khác row_hash nhưng giống hệt model input.

Audit hash 84 float32 feature để tìm ứng viên rồi so từng phần tử, không kết luận từ hash đơn thuần. Có 2.213 test rows và 2.253 val rows khớp train; các cặp đối chiếu không lệch nhãn. Đây là sự lặp lại đầu vào model đã xác nhận; không nhất thiết cùng raw network session, cũng chưa chứng minh toàn bộ accuracy cao do duplicate.

Khắc phục đúng: freeze protocol mới; tạo groups trên feature representation/canonical flow identity và kiểm tra cross-split overlap, giữ cùng group trong một split. Không xóa test rows một cách hậu nghiệm chỉ để nâng điểm. Temporal split cần kiểm soát coverage vì từng attack diễn ra theo ngày; nó có thể trở thành bài toán open-set chứ không còn closed-set tương đương.

### 2.2 LOACO scaler — phạm vi ảnh hưởng chính xác

[scripts/02_train_autoencoder.py](<D:/CAO HOC/IDS System/scripts/02_train_autoencoder.py:34>) nạp features_scaled.npy chung rồi mới loại heldout khỏi train/validation. [scripts/01_prepare_data.py](<D:/CAO HOC/IDS System/scripts/01_prepare_data.py:147>) không nhận heldout khi fit scaler.

State scaler ghi n_samples_seen_=1.467.762; known train nếu bỏ ID26 chỉ còn 1.401.162. Mean tính lại full train khác state tối đa 3,73e-9 do số học; mean known-only khác tới 0,138924 độ lệch chuẩn global ở một feature. Không có scaler theo loaco_26 trong artifacts/preprocessors.

Kết luận: không phải fit trên test; là tiếp xúc phân bố của lớp được tuyên bố “chưa từng thấy” qua preprocessing. LOACO hiện tại chỉ là preliminary, chưa đáp ứng strict unseen-class protocol. Metadata “test_used_for_fit_or_threshold=false” không phát hiện lỗi này.

Cần scaler/AE/Stage 1/calibrator/Stage 2/novelty riêng cho từng heldout; tất cả bước fit/chọn tham số phải loại lớp này. Encode/infer trên unknown test sau khi đóng băng là hợp lệ.

## 3. Latent representation và model training

### 3.1 Autoencoder

[src/autoencoder.py](<D:/CAO HOC/IDS System/src/autoencoder.py:12>) triển khai symmetric dense AE: 84 → 64 → 32 → 16 → 32 → 64 → 84. Hidden ReLU, latent/output linear; MSE reconstruction; AdamW lr=0,001, weight_decay=1e-5, gradient clipping=5; batch 8.192; tối đa 100 epoch, patience12; AMP FP16 theo hardware config. Không thấy greedy layer-wise pretraining, sparse penalty hay denoising objective.

Main fit cả BENIGN và ATTACK train, không phải benign-only anomaly AE. LOACO đã loại heldout ở AE fit nhưng input scaler còn nhiễm như trên. Latent được encode cho toàn bộ hàng theo thứ tự và dùng thật ở downstream.

Main best epoch100/MSE val0,0584128613; LOACO epoch99/MSE0,0523065002. Hai loss khác tập validation nên không so sánh chất lượng trực tiếp. Main chạm giới hạn epoch không chứng minh hội tụ. MSE thấp không chứng minh giữ thông tin phân biệt tấn công.

Đã có ablation raw-scaled vs latent ở Stage 1, và raw-scaled tốt hơn ở các binary metric quan sát. Thiếu raw-scaled Stage 2 và toàn cascade để khẳng định lợi ích nén. Không được nói “không có ablation nào”; phải nói ablation chưa đầy đủ.

### 3.2 Stage 1

XGBoost: binary:logistic, scale_pos_weight từ train; hist/CUDA trong config, depth8, max_bin128, 1.500 estimators max, learning_rate0,05, early stop75. MLP: hidden32/16, LayerNorm, ReLU, dropout0,2, BCEWithLogitsLoss có pos_weight. Cả hai có biến thể scaled 84 và latent 16.

P_attack trước calibration là đầu ra classifier; sau calibration là logistic trên clipped logit. Không phải probability đã được chứng minh calibrated chỉ vì gọi hàm Platt. Thiếu Brier/ECE/reliability và so sánh trước/sau calibration.

Ngưỡng gate dùng 0,5 cố định từ config; không thấy tìm ngưỡng tối ưu trên validation theo FPR/recall. Do đó mô tả đúng là “ngưỡng cố định”, không nói “đã tối ưu ngưỡng”.

### 3.3 OOF và meta-feature

Code có StratifiedKFold 5 folds, model từng fold thật, giữ vị trí prediction đúng; đây là OOF thật ở mức loại hàng khỏi gradient/tree fit. Nhưng:

1. Outer holdout labels tham gia early stopping của chính model dự đoán holdout.
2. Calibrator học từ toàn OOF targets, rồi áp lên cùng OOF rows: own-label phụ thuộc gián tiếp qua tham số calibrator.
3. Scaler/AE chung đã học X của fold holdout; đây là exposure không giám sát, không nên đánh đồng với leakage test hoặc trực tiếp dùng label.

P_attack được dùng cả ở gate và hai Stage 2 meta-feature experiments. Latent-only Stage 2 không dùng cột này nên không trực tiếp chịu lỗi stacking feature; gate vẫn dùng classifier/calibrator của Stage 1. So sánh phải tách phạm vi này.

Khắc phục tối thiểu: outer fold chỉ dùng để dự đoán; inner train/validation chọn epoch/calibration; lưu fold IDs và fit IDs. Với strict fold-local AE, mỗi encoder tạo latent coordinate riêng, không nên ghép ngẫu nhiên các latent khác không gian. Có thể dùng fold-local encoder chỉ cho scalar OOF P_attack, còn Stage 2 dùng một representation thống nhất fit trên train, và công bố rõ contract; hoặc dùng một tập representation-training độc lập. Cần định nghĩa protocol trước khi viết lại code.

### 3.4 Stage 2

[src/stage2.py](<D:/CAO HOC/IDS System/src/stage2.py:12>) mapping loại BENIGN; main 26 attack classes, LOACO-26 còn 25. stage2_matrix ghép thật [z, p] khi được yêu cầu. XGBoost multi:softprob dùng balanced sample weights; MLP hidden64/32, LayerNorm/ReLU/dropout0,25, class-weighted cross entropy. Không thấy SMOTE/resampling synthetic.

Một vấn đề loss aggregation được xác nhận trong [src/stage2.py](<D:/CAO HOC/IDS System/src/stage2.py:118>): weighted CrossEntropyLoss reduction=mean chuẩn hóa theo tổng class weights trong batch, nhưng code nhân batch loss với số hàng rồi chia tổng hàng. Đây không bằng global weighted loss khi tỷ lệ lớp giữa batch khác nhau. Hệ quả có thể làm early stopping/scheduler phụ thuộc cách chia batch; chưa lượng hóa ảnh hưởng vào checkpoint hiện tại. Training gradient không vì vậy tự động vô hiệu.

XGBoost config có eval_metric cuối là merror ở Stage 2; early stopping theo metric cuối, không trực tiếp macro-F1. Cơ chế này được nêu trong [tài liệu XGBoost](https://xgboost.readthedocs.io/en/stable/python/python_intro.html#early-stopping). Nên nhất quán objective chọn checkpoint và tiêu chí nghiên cứu, nhưng không tuning lại trên test.

## 4. Closed-set end-to-end và check-only

### 4.1 Logic thực tế

```text
Nạp P_attack toàn Phase 2 và Stage2 probabilities/class_ids/test_indices
Yêu cầu test_indices == flatnonzero(split_ids == TEST)
Lấy P_attack[test_indices]
Gán mặc định final = BENIGN
Với p >= 0.5: final = class_ids[argmax(Stage2 probabilities)]
Nếu bật novelty, chỉ các hàng đã qua gate và score >= threshold thành UNKNOWN(-1)
Đổi nhãn thật heldout thành -1 khi đánh giá LOACO
Tính multiclass metric trên TẤT CẢ test rows
Lưu prediction CSV với row_hash
Riêng open_set_metrics hiện tại: tính score-only trên true ATTACK rows, không dùng final
```

Không có chạy Stage 2 online có điều kiện: script04 đã dự đoán Stage 2 cho toàn bộ test; script06 chỉ áp gate khi ghép quyết định. Vì thế kiến trúc logic cascaded không chứng minh tiết kiệm thời gian inference.

### 4.2 check-only đảm bảo gì?

[scripts/06_evaluate_pipeline.py](<D:/CAO HOC/IDS System/scripts/06_evaluate_pipeline.py:51>)–91 xác nhận load được arrays; lengths cơ bản; heldout ID tồn tại/khác0; Stage 2 test_indices bằng split test theo thứ tự; nếu có novelty thì score length và threshold field tồn tại.

Nó KHÔNG bảo đảm: identity của P_attack/latent/novelty theo row_hash; model ancestry; schema hash; label-map hash; run/heldout đồng nhất tất cả artifacts; probability đúng 1D/2D; hàng/cột Stage 2 phù hợp class_ids; class_ids duy nhất và loại BENIGN/heldout; score finite; xác suất trong [0,1] và tổng hàng≈1; threshold phù hợp phương pháp; scientific split validity. Hàm compose chạy sau check-only, nên một số lỗi length còn chưa bị chạm tới.

Probe read-only với P_attack=[NaN] trả nhãn0 BENIGN. Đây là lỗi fail-open input validation đã xác nhận, không phải phát hiện NaN trong test artifacts thực tế. LOACO có NaN cố ý ở heldout train/val bị bỏ; không nên reject toàn mảng một cách mù quáng, mà validate đúng index cần dùng.

Audit bổ sung xác nhận bốn Stage 2 test index arrays đúng, probabilities hữu hạn, tổng hàng sai số tối đa 3,58e-7, class mapping hiện tại đúng; bốn CSV hash/truth/recomposed predictions khớp. Điều này tốt hơn check-only nhưng vẫn không tự chứng minh lineage từ model training chưa replay.

### 4.3 Lan truyền lỗi

Stage 2 known_test_metrics chỉ trên nhãn thật là attack (và known trong LOACO): oracle attack filter. Nó không phản ánh benign false alarms hoặc attack bị Stage 1 chặn. Main latent-only: 41 benign qua gate + 61 attack bị chặn + 1.377 attack qua gate bị phân loại sai = 1.479 lỗi cuối.

Threshold sensitivity chưa có. Phải báo cáo detection, conditional classification, final decision riêng, không trộn mẫu số.

## 5. Novelty/open-set/zero-day

Code có ba score: 1-max known-class probability, âm decision_function OCSVM, âm score_samples IsolationForest. Cả ba lấy quantile95 của KNOWN ATTACK validation, target rejection5%; không calibration trên benign validation. OCSVM cap20.000, IF cap100.000; helper giữ lớp hiếm qua quota rồi bổ sung random, không đảm bảo tập hoàn toàn balanced.

CLI cho giữ bất kỳ non-BENIGN ID hợp lệ, nhưng script05 yêu cầu ít nhất 500 heldout TEST samples. Với split hiện tại các ID đáp ứng là 2,5,8,9,11,18,23,25,26; chỉ 26 có artifact. Không nên loại lớp hiếm khỏi mọi thảo luận chỉ vì không qua ngưỡng protocol này.

- Closed-set: mọi target class đã có ở train.
- Novelty detection: score phân biệt known/unknown dưới giả định riêng.
- Open-set recognition: vừa phân lớp known vừa reject unknown, có thể mắc lỗi gate.
- Simulated zero-day: giữ lại attack class để mô phỏng chưa thấy trong benchmark; không chứng minh zero-day ngoài thực tế.

LOACO-26 đã loại nhãn26 khỏi AE/Stage 1/Stage 2 fitting theo source và metadata; threshold chỉ known-validation. Nhưng scaler exposure làm strict protocol không đạt. Ngoài ra báo cáo open_set_metrics của script06 bỏ gate và benign: recall = 0,260650 là score-only, trong khi final recall = 0,247197; F1_all_test 0,337592 chứ không phải0,352690. Có 372 unknown bị Stage 1 gán benign; 14 benign bị reject unknown. Số liệu chi tiết ở báo cáo03.

Chỉ một heldout class không cho phép khái quát mọi unknown attack. Chọn novelty method vì tốt nhất trên unknown test rồi gọi đó là phương pháp đã chốt cũng là nguy cơ selection leakage; cần protocol chọn trên validation/pseudo-unknown training families hoặc báo cáo tất cả như exploratory.

## 6. Kết luận correctness

Đã xác nhận tính nhất quán số học của saved outputs, không xác nhận hoàn toàn tính độc lập của experimental protocol. Không thấy trực tiếp fit model trên test trong code đã đọc; vẫn có lỗi độc lập quan trọng như trên. Những nhận định cũ “LOACO đã hợp lệ” hoặc “OOF bảo đảm không leakage” phải thu hẹp theo audit này; không sửa lịch sử kết quả. Giữ các run hiện có như exploratory, tạo run mới sau khi protocol được chốt.
