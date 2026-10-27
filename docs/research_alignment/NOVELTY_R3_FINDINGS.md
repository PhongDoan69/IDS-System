# Kết quả huấn luyện lại và đối chứng novelty nhiều seed — CICIDS2017 R3

Study: `novelty_r3_20261027`. Ngày kiểm toán: 27/10/2026, múi giờ Asia/Saigon.

Quy ước: **VERIFIED FROM IMPLEMENTATION** = xác nhận từ code/config/contract; **VERIFIED FROM EXPERIMENTS** = xác nhận từ artifacts đã chạy và phép tính kiểm tra; **TECHNICAL INTERPRETATION** = diễn giải có điều kiện; **REQUIRES FURTHER VERIFICATION** = chưa đủ bằng chứng thực nghiệm.

## 1. Kết luận chính

**VERIFIED FROM EXPERIMENTS.** Hoàn tất **120/120 subprocess steps**, tất cả exit code 0: **9 trial** = 3 held-out label × seed 42/43/44; **54 evaluation** = 3 novelty detector × 2 gate × 9 trial; thêm **9 reference evaluation không novelty**. Bắt đầu 14:18:53 và kết thúc 16:26:01 ngày 27/10/2026, khoảng 2 giờ 7 phút 9 giây. Không gặp lỗi hết dung lượng; không cần dừng vì thiếu ổ đĩa.

**VERIFIED FROM EXPERIMENTS.** Với recall gate, kNN balanced–L2–k1 có unknown recall, precision và F1 cao hơn cả MCP và Mahalanobis trong **cả 9 so sánh cùng held-out/seed**. Tuy nhiên, E2E macro-F1 chỉ cao hơn MCP ở **6/9 trial**; không có bằng chứng “kNN tốt hơn mọi chỉ số trong mọi trường hợp”.

**TECHNICAL INTERPRETATION.** kNN là ứng viên chung đáng giữ để kiểm chứng tiếp; kết quả Portscan chưa mạnh và nhạy với seed. Với DoS Hulk/DDoS, toàn bộ unknown còn bỏ sót của ứng viên trong đợt này nằm ở Stage 1. Vì vậy, ưu tiên tiếp theo khác nhau theo nguồn lỗi, không chỉ là tăng độ nhạy của novelty detector.

**REQUIRES FURTHER VERIFICATION.** Đây là độ ổn định theo quá trình fit trên **một split đã xem test**, chưa là xác nhận zero-day thực tế, chưa chứng minh tính mới thuật toán hay tính tổng quát trên dataset/split độc lập. Tên `confirmatory` của runner không thay đổi giới hạn này.

Nguồn chính: [status.json](<D:/CAO HOC/IDS System/results/novelty_confirmation/novelty_r3_20261027/status.json>), [protocol_lock.json](<D:/CAO HOC/IDS System/results/novelty_confirmation/novelty_r3_20261027/protocol_lock.json>), [comparison.json](<D:/CAO HOC/IDS System/results/novelty_confirmation/novelty_r3_20261027/comparison.json>), [summary.json](<D:/CAO HOC/IDS System/results/novelty_confirmation/novelty_r3_20261027/summary.json>), [RESEARCH_REPORT.md](<D:/CAO HOC/IDS System/results/novelty_confirmation/novelty_r3_20261027/RESEARCH_REPORT.md>).

## 2. Pipeline thực sự được thực thi

**VERIFIED FROM IMPLEMENTATION.** Quy tắc cuối cùng:

```text
84 features -> StandardScaler known-train -> AE latent 16
    -> Stage 1 XGBoost binary + Platt -> P_attack
        P_attack < gate: BENIGN (0), kết thúc
        P_attack >= gate:
            Stage 2 XGBoost latent_only -> xác suất các lớp known
            novelty score >= threshold: UNKNOWN (-1)
            novelty score < threshold: lớp known có xác suất cao nhất
```

**VERIFIED FROM IMPLEMENTATION.** AE 84→64→32→16→32→64→84, MSE/AdamW, early stopping known-validation, tối đa 100 epoch, patience 12. AE học benign và known attacks, không phải benign-only anomaly detector. Train dùng CUDA/AMP; encode FP32. Stage 1/Stage 2 dùng CUDA XGBoost `hist`, giữ hyperparameters đã khóa; Stage 2 có balanced sample weights và không dùng P_attack làm meta-feature.

**VERIFIED FROM IMPLEMENTATION / EXPERIMENTS.** Mỗi trial fit scaler mới; AE, nested 5-fold OOF encoders/classifiers, Platt và final Stage 1/Stage 2 đều train mới. OOF mỗi fold có fit/stop/calibration/holdout tách biệt; scaler/AE/classifier không fit hoặc early-stop bằng outer holdout. Các tệp scaled được hard-link sau khi replay transform mới khớp hoàn toàn, chỉ là tiết kiệm storage, không tái sử dụng trọng số AE/XGBoost lịch sử.

**VERIFIED FROM IMPLEMENTATION.** Ba detector trên cùng upstream của mỗi trial:

| Detector | Cách tính novelty | Phạm vi fit riêng |
|---|---|---|
| MCP | `1 - max_c P_stage2(c|z)` | Không có model novelty riêng; dùng Stage 2 đã fit |
| Mahalanobis | Khoảng cách bình phương nhỏ nhất đến mean lớp; covariance pooled within-class Ledoit–Wolf | Toàn bộ known-train attack latent |
| kNN | Khoảng cách Euclidean bình phương đến láng giềng k=1, latent chuẩn hóa L2 với epsilon 1e-10 | 50.000 known-train attack, balanced quota, không replacement/oversampling |

**VERIFIED FROM IMPLEMENTATION / EXPERIMENTS.** Mahalanobis và kNN dùng CPU FP64; kNN exact cKDTree, không approximate NN. Reference của cả 9 trial có đủ 25 lớp known và không chứa validation/test/held-out train rows. Reference seed bằng seed trial, nên biến thiên quan sát được bao gồm cả fit upstream và lấy mẫu reference.

**VERIFIED FROM IMPLEMENTATION / EXPERIMENTS.** Recall gate được chọn từ known-validation với benign FPR budget 0,001, ngưỡng ≤0,5; gate phụ cố định 0,5. Cả ba novelty threshold là quantile 95% known-validation attack score và được lưu trước khi query test. Gate validation FPR lớn nhất xác minh được là **0,0009983992**; novelty validation rejection thực tế **5,000843%–5,003660%** do số mẫu hữu hạn/quy tắc `>=`, không ép test về đúng 5%.

**VERIFIED FROM IMPLEMENTATION.** Unknown là nhãn `-1`, không phải tên DoS Hulk/Portscan/DDoS do hệ thống tự suy ra. Nhãn gốc held-out chỉ dùng kiểm tra loại trừ và chấm điểm, không dùng routing hay chọn cấu hình bằng test.

## 3. So sánh chính: kết quả sau recall gate

**VERIFIED FROM EXPERIMENTS.** Mỗi ô dạng mean ± sample standard deviation trên **3 lần fit**, không phải confidence interval hoặc ba test độc lập. Precision/recall/F1/FRR theo phần trăm; E2E macro-F1 trên thang 0–1. Precision unknown tính trên toàn test, bao gồm benign; FRR là known attack bị gán UNKNOWN sau gate / toàn bộ known attack test.

| Held-out | Detector | Unknown recall % | Min–max recall % | Unknown precision % | Unknown F1 % | Known FRR % | E2E macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|
| DoS Hulk | MCP | 35,21 ± 9,84 | 24,48–43,82 | 75,01 ± 5,73 | 47,61 ± 10,47 | 4,93 ± 0,02 | 0,7913 ± 0,0224 |
| DoS Hulk | Mahalanobis | 30,41 ± 3,68 | 26,74–34,10 | 72,43 ± 2,38 | 42,79 ± 4,07 | 4,99 ± 0,07 | 0,7058 ± 0,0075 |
| DoS Hulk | kNN | **93,28 ± 5,40** | 87,59–98,33 | 88,86 ± 0,74 | 90,98 ± 2,97 | 4,95 ± 0,11 | 0,7943 ± 0,0081 |
| Portscan | MCP | 36,74 ± 3,86 | 32,30–39,26 | 76,04 ± 2,09 | 49,50 ± 3,99 | 4,88 ± 0,05 | 0,7811 ± 0,0136 |
| Portscan | Mahalanobis | 6,87 ± 1,18 | 5,54–7,77 | 37,79 ± 3,84 | 11,61 ± 1,87 | 4,86 ± 0,03 | 0,6678 ± 0,0152 |
| Portscan | kNN | **55,39 ± 9,31** | 44,92–62,73 | 82,75 ± 1,86 | 66,12 ± 7,46 | 4,87 ± 0,22 | 0,8248 ± 0,0151 |
| DDoS | MCP | 24,79 ± 3,36 | 21,92–28,49 | 52,95 ± 3,34 | 33,75 ± 3,79 | 4,90 ± 0,02 | 0,7936 ± 0,0138 |
| DDoS | Mahalanobis | 8,13 ± 6,37 | 2,77–15,18 | 24,60 ± 14,61 | 12,16 ± 8,99 | 4,96 ± 0,07 | 0,6995 ± 0,0105 |
| DDoS | kNN | **99,61 ± 0,22** | 99,37–99,80 | 81,49 ± 0,15 | 89,65 ± 0,17 | 4,95 ± 0,06 | 0,8030 ± 0,0095 |

**VERIFIED FROM EXPERIMENTS.** So sánh paired kNN trừ baseline, cùng held-out/seed, lấy trung bình 3 seed:

| Held-out | Δ recall so MCP, điểm % | Δ recall so Mahalanobis, điểm % | Δ E2E macro-F1 so MCP |
|---|---:|---:|---:|
| DoS Hulk | +58,07 | +62,87 | +0,00297 |
| Portscan | +18,65 | +48,52 | +0,04362 |
| DDoS | +74,82 | +91,48 | +0,00937 |

**TECHNICAL INTERPRETATION.** Lợi ích về unknown không tương đương lợi ích đồng đều trên known/benign. Với DoS Hulk seed 43/44 và DDoS seed 43, kNN có E2E macro-F1 thấp hơn MCP dù unknown recall cao hơn. Không chọn riêng seed tốt hoặc detector tốt theo held-out từ bảng test này.

Nguồn: `summary.json/groups`, `paired_knn_minus_baseline`; toàn bộ 54 dòng, kể cả fixed gate, ở [summary.csv](<D:/CAO HOC/IDS System/results/novelty_confirmation/novelty_r3_20261027/summary.csv>).

## 4. Tỷ lệ phát hiện unknown: mẫu số và cách gộp đúng

**VERIFIED FROM EXPERIMENTS.** Mỗi seed có 23.770 unknown DoS Hulk, 23.860 unknown Portscan, 14.272 unknown DDoS, tổng **61.902 trường hợp** trong ba bài toán LOACO. Bảng dưới gộp ba bài toán cùng seed, không phải một model duy nhất đồng thời held-out cả ba lớp.

| Seed | kNN: detected / 61.902 | Recall kNN % | Recall MCP % | Recall Mahalanobis % |
|---|---:|---:|---:|---:|
| 42 | 51.516 / 61.902 | 83,22 | 26,90 | 14,75 |
| 43 | 48.962 / 61.902 | 79,10 | 34,76 | 16,54 |
| 44 | 48.337 / 61.902 | 78,09 | 38,53 | 17,30 |
| Mean ± SD theo seed | Không cộng thành mẫu độc lập mới | **80,13 ± 2,72** | **33,40 ± 5,93** | **16,20 ± 1,31** |

**VERIFIED FROM EXPERIMENTS.** Nếu cho ba held-out trọng số bằng nhau thay vì trọng số theo support: macro-heldout recall kNN **82,76 ± 2,35%**, MCP **32,25 ± 5,56%**, Mahalanobis **15,14 ± 1,73%**, SD tính trên ba giá trị macro theo seed.

**TECHNICAL INTERPRETATION.** Câu trả lời ngắn cho “tỷ lệ hệ thống phát hiện unknown” là **80,13% trung bình gộp theo support, trong thiết kế này**, không phải 100% và không phải tỷ lệ phát hiện zero-day ngoài thực tế. Không dùng 185.706 quan sát lặp theo seed làm 185.706 mẫu test độc lập.

## 5. Phân rã lỗi unknown và hiệu ứng gate

**VERIFIED FROM EXPERIMENTS.** Ứng viên kNN, recall gate:

| Held-out | Seed | Detected / support | Unknown bị gate nhận benign | Qua gate nhưng nhận known | Benign nhận UNKNOWN | Known FRR % |
|---|---:|---:|---:|---:|---:|---:|
| DoS Hulk | 42 | 22.325 / 23.770 | 1.445 | 0 | 162 | 4,8435 |
| DoS Hulk | 43 | 20.819 / 23.770 | 2.951 | 0 | 127 | 5,0608 |
| DoS Hulk | 44 | 23.374 / 23.770 | 396 | 0 | 100 | 4,9596 |
| Portscan | 42 | 14.968 / 23.860 | 187 | 8.705 | 150 | 4,9286 |
| Portscan | 43 | 13.961 / 23.860 | 1.330 | 8.569 | 125 | 5,0618 |
| Portscan | 44 | 10.719 / 23.860 | 2.612 | 10.529 | 94 | 4,6339 |
| DDoS | 42 | 14.223 / 14.272 | 49 | 0 | 87 | 5,0168 |
| DDoS | 43 | 14.182 / 14.272 | 90 | 0 | 144 | 4,9325 |
| DDoS | 44 | 14.244 / 14.272 | 28 | 0 | 117 | 4,9023 |

**VERIFIED FROM EXPERIMENTS.** Mỗi dòng thỏa `detected + gate-blocked + admitted-as-known = unknown support`. Với DoS Hulk/DDoS, kNN score-only unknown recall bằng 100% ở cả ba seed, nhưng recall **cuối cascade** thấp hơn vì gate đã loại mẫu. Score-only bỏ qua benign và gate nên không được thay thế kết quả toàn hệ thống.

**VERIFIED FROM EXPERIMENTS.** Portscan score-only recall theo seed 42/43/44 là **63,52% / 64,07% / 55,86%**; sau gate còn **62,73% / 58,51% / 44,92%**. Đây là cả hai nút thắt: novelty geometry chưa tách tốt một phần Portscan và gate làm mất thêm unknown.

**VERIFIED FROM EXPERIMENTS.** Thay fixed gate 0,5 bằng recall gate làm recall kNN tăng ở cả 9 trial:

| Held-out | Δ recall seed 42, điểm % | Seed 43 | Seed 44 |
|---|---:|---:|---:|
| DoS Hulk | +2,95 | +11,57 | +2,98 |
| Portscan | +2,38 | +6,63 | +18,32 |
| DDoS | +1,26 | +3,10 | +0,37 |

**TECHNICAL INTERPRETATION.** Recall gate giúp giảm bỏ sót unknown trong đợt này, nhưng không luôn tăng E2E macro-F1; gate/novelty còn làm phát sinh false alarms hoặc sai lớp known. Không tiếp tục hạ ngưỡng bằng cách xem held-out test. Nhánh rescue/bypass cho mẫu gate-benign, nếu nghiên cứu, phải là protocol mới với ngân sách benign false alarm được kiểm soát.

Nguồn: `comparison.json/*/final_unknown_metrics`, `error_decomposition`, `score_only_unknown_metrics`; phép kiểm lại từ `test_predictions` dạng `predictions.npz`, P_attack và novelty score. Số “qua gate nhưng nhận known” được tính bằng support trừ detected và gate-blocked, đồng thời xác minh từ predictions.

## 6. Stage 1, Stage 2 và error propagation

**VERIFIED FROM EXPERIMENTS.** Mean ± SD theo ba seed, recall gate; Stage 1 test gồm cả known và held-out attacks. Stage 2 oracle là đánh giá classifier trên toàn true-known-attack test, bỏ qua gate; admitted là chỉ true-known-attack đã qua gate, trước novelty.

| Held-out | Stage 1 attack recall % | Stage 1 benign FPR % | Stage 2 validation macro-F1 | Stage 2 oracle known-test macro-F1 | Stage 2 admitted-known macro-F1 |
|---|---:|---:|---:|---:|---:|
| DoS Hulk | 97,892 ± 1,674 | 0,09324 ± 0,00363 | 0,8871 ± 0,0064 | 0,8901 ± 0,0220 | 0,9624 ± 0,0099 |
| Portscan | 98,185 ± 1,572 | 0,09521 ± 0,00883 | 0,8911 ± 0,0145 | 0,8999 ± 0,0179 | 0,9673 ± 0,0028 |
| DDoS | 99,887 ± 0,026 | 0,09479 ± 0,00696 | 0,8827 ± 0,0175 | 0,9077 ± 0,0057 | 0,9408 ± 0,0261 |

**VERIFIED FROM EXPERIMENTS.** Known attack bị Stage 1 chặn theo seed 42/43/44: DoS Hulk trial **21/39/26**, Portscan **24/24/23**, DDoS **29/20/45** mẫu. Đây là lỗi bổ sung ngoài unknown gate-blocked. Tổng lỗi E2E kNN tương ứng là **5.626/7.422/4.598**, **11.862/12.897/15.928**, **4.840/4.859/4.664** mẫu.

**TECHNICAL INTERPRETATION.** Macro-F1 admitted-known cao hơn oracle không chứng minh Stage 2 tốt lên: population đã bị gate lọc, support/class set có thể thay đổi, đặc biệt các lớp rất hiếm. Đánh giá khả năng phân loại known phải dùng oracle và per-class support cùng E2E, không chỉ conditional metric.

**VERIFIED FROM EXPERIMENTS.** Test benign FPR cao nhất trong các recall-gate trial là khoảng **0,10490%** (Portscan seed 42), dù mọi gate đều thỏa budget 0,1% trên validation. Budget validation không phải bảo đảm chính xác trên test/triển khai.

**VERIFIED FROM EXPERIMENTS.** Chín reference evaluation không novelty đều có **0 unknown detected**. Đây chỉ là kiểm tra pipeline không có cơ chế reject thì không sinh nhãn UNKNOWN, không phải một thuật toán unknown detection cạnh tranh khác.

Nguồn: `results/stage2/<run>/latent_only/metrics.json`; `comparison.json` và `results/pipeline/<run>_closed/metrics.json`.

## 7. Known false rejection theo lớp và giới hạn support hiếm

**VERIFIED FROM EXPERIMENTS.** Global known FRR khoảng 5% che khuất khác biệt theo lớp. Ví dụ với kNN/recall gate:

| Known class | Support test mỗi trial | FRR mean % khi held-out Hulk | Khi held-out Portscan | Khi held-out DDoS |
|---|---:|---:|---:|---:|
| DoS GoldenEye | 1.135 | 23,67 | 13,89 | 20,23 |
| DoS Slowloris | 579 | 1,50 | 1,27 | 1,32 |
| DoS Slowhttptest | 261 | 1,02 | 1,15 | 1,02 |
| Infiltration - Portscan | 10.294 | 2,03 | 0,87 | 1,56 |
| Heartbleed | 2 | **100,00** | 16,67 | 66,67 |
| SSH-Patator - Attempted | 4 | 41,67 | 25,00 | 41,67 |
| Infiltration | 5 | 20,00 | 13,33 | 20,00 |

**VERIFIED FROM EXPERIMENTS.** Heartbleed khi held-out Hulk: cả 2 known test samples đều bị kNN nhận UNKNOWN ở từng seed (MCP FRR trung bình 33,33%, Mahalanobis 16,67% trên cùng 2 mẫu). Với held-out DDoS, Heartbleed FRR của kNN 50–100%, trong khi MCP/Mahalanobis ở ba seed đều 0% cho lớp này. Đây là chi phí cụ thể không thể bỏ qua dù unknown recall tăng mạnh.

**VERIFIED FROM EXPERIMENTS.** Các lớp known khác có support rất nhỏ: FTP-Patator Attempted 2, Web Attack XSS 3, SQL Injection Attempted 1, SQL Injection 2 mẫu test; kNN FRR bằng 0% ở các trial đã chạy. **TECHNICAL INTERPRETATION.** FRR 0% không đồng nghĩa phân loại đúng tên known class; mẫu vẫn có thể bị nhận thành benign hoặc lớp known khác. Với support 1–5, phần trăm rất không ổn định và không đủ kết luận lớp đó đã được giải quyết.

Nguồn: `results/novelty_confirmation/novelty_r3_20261027/*_class_rejection.json` và `metrics.json/end_to_end_metrics/per_class` trong từng evaluation. Các bảng chỉ mô tả support hiện có, không tăng mẫu bằng cách cộng ba seed.

## 8. Kiểm toán tính toàn vẹn và khả năng tái hiện

**VERIFIED FROM EXPERIMENTS.** Kiểm tra read-only sau chạy đã xác nhận:

- Đủ 120 exit code 0, 9 trial, 54 dòng summary/evaluation và 9 reference không novelty.
- **108 top-level artifact contracts**, kiểm toàn vẹn ancestry với **931 tệp duy nhất** được hash; nguồn/config/dữ liệu và bằng chứng lịch sử khớp checksum khóa.
- Fit indices scaler đúng known-train; cả 9 tệp scaled mới hard-link đúng nguồn đã kiểm exact transform; không tái sử dụng model lịch sử.
- Từng phân hoạch fit/stop/calibration/outer holdout của 45 outer folds không chồng lấn và phủ đúng known-train; outer holdouts phủ mỗi known-train row đúng một lần.
- Novelty fit/reference không chứa held-out/validation/test; reference đủ 50.000 hàng duy nhất và đủ known classes; index test/validation căn hàng với split đã lưu.
- Replay gate bằng known-validation tái tạo đúng threshold; replay quantile từ validation scores tái tạo đúng cả 27 novelty thresholds.
- Tái compose **toàn bộ 54 bộ dự đoán** từ P_attack, Stage 2 probabilities, novelty scores và thresholds khớp `predictions.npz`; số unknown detected/gate-blocked/admitted-as-known và precision/recall được tính lại; class rejection counts khớp predictions.
- Bằng chứng lịch sử MCP/Mahalanobis/kNN không bị thay đổi theo các hash đã khóa; model/checkpoint/ngưỡng mới vẫn được giữ nguyên.

**TECHNICAL INTERPRETATION.** Checksum/contract chứng minh tính nhất quán và toàn vẹn local theo phạm vi kiểm tra, không tự chứng minh raw provenance đáng tin hoặc loại hết mọi dạng data leakage. Nhãn “all test is evaluation-only” ở cấp một run không xóa được việc người nghiên cứu đã xem test lịch sử khi chọn hướng kNN.

**VERIFIED FROM IMPLEMENTATION / EXPERIMENTS.** Tham số/weights/indices được lưu theo hướng dẫn [NOVELTY_MULTISEED_TRAINING_GUIDE.md](<D:/CAO HOC/IDS System/docs/research_alignment/NOVELTY_MULTISEED_TRAINING_GUIDE.md>). MCP tái hiện bằng Stage 2 + threshold, không có novelty model riêng; Mahalanobis/kNN có `.joblib` riêng. Bản báo cáo này là tệp bổ sung; không sửa RESEARCH_REPORT hoặc báo cáo lịch sử.

## 9. Các giới hạn phải công bố trong luận văn

1. **REQUIRES FURTHER VERIFICATION — test exposure.** `balanced_l2_k1` được đề xuất từ kết quả test `knn_v1`; R3 khóa cùng ứng viên cho mọi trial nhưng dùng lại test. Kết quả là thăm dò phát triển phương pháp/seed stability, chưa phải đánh giá xác nhận độc lập.
2. **VERIFIED FROM IMPLEMENTATION / TECHNICAL INTERPRETATION — split và seed.** Ba seed đổi quá trình fit và reference sampling, không đổi split. Không có temporal/group-independent split trong R3; feature-vector overlap giữa split chưa được loại. Seed không tạo thêm dữ liệu test độc lập; chưa thực hiện kiểm định suy luận thống kê cho ưu thế phương pháp.
3. **REQUIRES FURTHER VERIFICATION — provenance và target.** Bản CSV cục bộ có 84 features, 27 labels, giữ Attempted; release/provenance upstream và diễn giải ngữ nghĩa target vẫn cần xác minh. Không mặc nhiên xem đây là bản benchmark canonical của mọi bài báo khác.
4. **VERIFIED FROM IMPLEMENTATION / TECHNICAL INTERPRETATION — label-out khác family-out.** Held-out DoS Hulk ID 9 nhưng **DoS Hulk - Attempted ID 10 vẫn là known**; Portscan ID 25 được loại nhưng nhãn liên quan `Infiltration - Portscan` ID 18 vẫn known. Đây là leave-one-label-out theo mapping hiện có, chưa chứng minh toàn bộ attack family/behavior chưa từng xuất hiện khi train. Quan hệ ngữ nghĩa giữa các nhãn cần kiểm chứng trước khi tuyên bố zero-day family-level.
5. **VERIFIED FROM IMPLEMENTATION / REQUIRES FURTHER VERIFICATION — shared validation.** Known-validation vừa được dùng early stopping upstream vừa dùng đặt gate/novelty thresholds. Cần thiết kế calibration holdout riêng để kiểm tra độ lạc quan; held-out validation không được dùng cho việc chọn ngưỡng hiện tại.
6. **VERIFIED FROM EXPERIMENTS / TECHNICAL INTERPRETATION — coverage.** Chỉ ba held-out có support đủ lớn; Portscan recall biến thiên 44,92–62,73%, một số known rare classes bị reject nặng. Không suy rộng sang mọi dạng tấn công hiếm hoặc họ attack chưa thử.
7. **REQUIRES FURTHER VERIFICATION — deployment.** Chưa đo raw-to-model latency, throughput, VRAM/CPU footprint toàn pipeline hoặc vận hành IDS trực tuyến. Thời gian compose score có sẵn không phải latency inference. Precision hiện tại phụ thuộc prevalence/test mixture, không bảo đảm precision khi unknown ngoài thực tế hiếm hơn nhiều.
8. **VERIFIED FROM IMPLEMENTATION / REQUIRES FURTHER VERIFICATION — khôi phục.** Runner hiện không có resume khi đầy ổ đĩa; dưới 1,5 GiB trước bước tiếp theo sẽ fail, không tự chờ. Checkpoint tốt nhất không đồng nghĩa đã lưu mọi trạng thái RNG/scheduler/OOF/runner để resume chính xác. R3 đã kết thúc không thiếu dung lượng; cơ chế pause/resume là cải tiến vận hành riêng, chưa được triển khai hay kiểm thử trong R3.

## 10. Kết luận dùng trong báo cáo và ưu tiên tiếp theo

**TECHNICAL INTERPRETATION — đoạn kết luận có thể sử dụng:**

> Trên ba bài toán leave-one-label-out của bản CICIDS2017 cục bộ với ba seed huấn luyện, pipeline AE–XGBoost hai giai đoạn kết hợp novelty kNN balanced–L2–k1 đạt unknown recall sau gate trung bình 93,28% cho DoS Hulk, 55,39% cho Portscan và 99,61% cho DDoS, tại known attack false rejection xấp xỉ 5%. Tỷ lệ gộp theo support trên ba bài toán đạt 80,13 ± 2,72% theo seed, cao hơn MCP và Mahalanobis trong cấu hình đối chứng đã khóa. Tuy nhiên, hiệu quả không đồng đều theo lớp, một số known rare classes bị từ chối sai và E2E macro-F1 không luôn cải thiện so với MCP. Các kết quả thể hiện tiềm năng của cơ chế nhận diện UNKNOWN trong mô phỏng loại nhãn, chưa xác nhận phát hiện zero-day ngoài thực tế do test exposure, split ngẫu nhiên còn overlap và provenance/target chưa hoàn toàn xác minh.

**TECHNICAL INTERPRETATION.** Đóng góp hiện có có thể trình bày là tích hợp pipeline và protocol đối chứng có kiểm toán, kết hợp đánh giá known/unknown sau gate và phân tích nguồn lỗi; **không** trình bày việc dùng kNN/Mahalanobis đã có như thuật toán mới, hoặc coi điểm số cao là chứng minh tính mới nghiên cứu.

**REQUIRES FURTHER VERIFICATION — ưu tiên theo giá trị khoa học:**

1. Xác minh provenance/Attempted và xây dựng kiểm chứng độc lập theo group/flow/feature-vector hoặc thời gian, đủ support; tách rõ label-out và family-out.
2. Khóa cùng phương pháp và đánh giá hai dataset ngoài với schema/đơn vị/label adapter có kiểm chứng; fit scaler/AE/classifier trên train riêng từng dataset, không mặc nhiên chuyển cùng weights hoặc cùng giá trị threshold số học.
3. Tách early-stopping validation với threshold-calibration holdout; mở rộng held-out families và seed theo thiết kế trước, không chọn lại k/budget/seed bằng test đã thấy.
4. Phân tích Portscan ở latent và các lỗi known hiếm bằng dữ liệu train/validation; nếu thử detector/rescue gate mới, dùng protocol mới với ngân sách benign FPR/known FRR và báo cả trade-off, giữ R3 làm baseline bất biến.
5. Bổ sung kiểm thử vận hành: pause/chờ dung lượng, resume có đủ trạng thái, lỗi disk/OOM có kiểm soát, và benchmark raw-to-model inference. Không đổi source/config của một đợt đang khóa để “sửa nóng” rồi gộp kết quả như cùng protocol.

Không tự chạy thêm thực nghiệm hoặc đổi cấu hình từ các bảng test trong báo cáo này.
