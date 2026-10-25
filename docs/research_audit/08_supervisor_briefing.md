# 08 — Báo cáo tiến độ nghiên cứu phục vụ trao đổi với giảng viên hướng dẫn

**Đề tài:** Nghiên cứu phát triển hệ thống phát hiện xâm nhập kết hợp mô hình máy học.

[TECHNICAL INTERPRETATION] Bản tổng hợp ngày 24/10/2026 chỉ sử dụng các báo cáo audit 01–07 trong D:\CAO HOC\IDS System\docs\research_audit, phản ánh snapshot 895cc8b. Các nhãn “VERIFIED” dưới đây kế thừa bằng chứng của audit, không hàm ý đã huấn luyện hoặc kiểm chứng lại mô hình trong lần biên soạn này.

**Quy ước bằng chứng**

- **VERIFIED FROM IMPLEMENTATION:** cấu trúc hoặc hành vi của mã nguồn đã được audit xác nhận.
- **VERIFIED FROM EXPERIMENTS:** artifact, kết quả hoặc phép kiểm tra thực nghiệm đã được audit xác nhận; không tự bảo đảm protocol hợp lệ.
- **TECHNICAL INTERPRETATION:** diễn giải kỹ thuật hoặc đề xuất dựa trên audit, không phải phát hiện mới.
- **REQUIRES FURTHER VERIFICATION:** giả thuyết, giới hạn hoặc điều kiện chưa đủ bằng chứng để kết luận.

## 1. Mục tiêu nghiên cứu

[TECHNICAL INTERPRETATION] Nghiên cứu IDS ở mức luồng mạng, giải quyết ba nhiệm vụ liên quan: phát hiện BENIGN/ATTACK; phân loại các nhãn attack đã biết; và khảo sát khả năng từ chối attack chưa biết bằng mô phỏng Leave-One-Attack-Class-Out (LOACO). Trọng tâm đánh giá là ảnh hưởng của biểu diễn latent, xác suất attack làm đặc trưng phụ và lỗi lan truyền giữa hai tầng, thay vì chỉ tối đa hóa accuracy. Nguồn: [A05, I1–I4](<D:/CAO HOC/IDS System/docs/research_audit/05_thesis_technical_notes.md>).

[VERIFIED FROM IMPLEMENTATION] Đầu vào hiện tại là CSV đặc trưng flow đã trích xuất; hệ thống là pipeline thực nghiệm offline, chưa phải bộ phát hiện trực tiếp trên packet stream. Nguồn: [A02, §4](<D:/CAO HOC/IDS System/docs/research_audit/02_pipeline_correctness.md>).

## 2. Phương pháp đã triển khai

[VERIFIED FROM IMPLEMENTATION] Pipeline được audit xác nhận như sau; toàn bộ mô tả trong bảng mang nhãn này. Nguồn: [A01, §3–4](<D:/CAO HOC/IDS System/docs/research_audit/01_project_status.md>), [A02, §1–5](<D:/CAO HOC/IDS System/docs/research_audit/02_pipeline_correctness.md>).

| Khâu | Implementation thực tế |
|---|---|
| Chuẩn bị dữ liệu | Đọc 5 daily CSV; làm sạch numeric; loại duplicate trên toàn dòng; bỏ Label, Attempted Category, IP và timestamp khỏi features; stratified random split 70/15/15, seed 42; scaler fit trên train chung. |
| Biểu diễn | Dense Autoencoder đối xứng 84→64→32→16→32→64→84; học joint bằng MSE và AdamW, trên cả benign và attack train. Không có greedy layer-wise pretraining; không phải feature selection. |
| Stage 1 | XGBoost với binary logistic hoặc MLP hidden 32/16 với weighted BCE; so sánh scaled 84 chiều và latent 16 chiều; tạo P_attack bằng 5-fold OOF cho train, final model cho validation/test; Platt-style calibration trên logit. |
| Stage 2 | Chỉ train trên attack: XGBoost multiclass với balanced sample weights hoặc MLP hidden 64/32 với weighted cross entropy. Ba biến thể main: latent-only XGB, latent+P_attack XGB, latent+P_attack MLP. |
| Quyết định cuối | P_attack < 0,5 → BENIGN; ngược lại lấy class argmax của Stage 2. Khi bật novelty, mẫu qua gate và vượt ngưỡng novelty → UNKNOWN. Ngưỡng gate 0,5 là cố định, chưa được tối ưu theo validation. |
| Novelty | Ba score: 1−max probability, One-Class SVM và Isolation Forest trên latent; ngưỡng lấy quantile 95 của known-attack validation. |

[VERIFIED FROM IMPLEMENTATION] P_attack thực sự được ghép thành đầu vào 17 chiều trong hai biến thể meta-feature, không chỉ dùng làm gate. Tuy nhiên, Stage 2 được dự đoán trước cho mọi test row rồi mới ghép quyết định; chưa có bằng chứng tiết kiệm inference nhờ chỉ chạy tầng hai khi cần. Nguồn: [A02, §3.3–4.1](<D:/CAO HOC/IDS System/docs/research_audit/02_pipeline_correctness.md>).

## 3. Thí nghiệm hoàn thành và kết quả kiểm chứng

[VERIFIED FROM EXPERIMENTS] Audit ghi nhận 2.096.804 hàng, 84 features; train/validation/test lần lượt 1.467.762/314.521/314.521. Có hai AE, năm cấu hình Stage 1, bốn cấu hình Stage 2, ba novelty scores trong LOACO-26 và bốn báo cáo end-to-end; đây không phải các lần lặp độc lập. Có 16 unit tests đạt; bốn bộ quyết định cuối tái ghép khớp artifact. Nguồn: [A01, §6](<D:/CAO HOC/IDS System/docs/research_audit/01_project_status.md>), [A03, §1–7](<D:/CAO HOC/IDS System/docs/research_audit/03_experiment_review.md>).

[VERIFIED FROM EXPERIMENTS] Stage 1 main: test F1 của XGBoost scaled/latent là **0,999857/0,999339**; MLP scaled/latent là **0,999378/0,997330**. XGBoost scaled có FP=15, FN=7; XGBoost latent có FP=41, FN=61. Các main pipeline đã lưu dùng gate XGBoost latent, không phải scaled. Nguồn: [A03, §3](<D:/CAO HOC/IDS System/docs/research_audit/03_experiment_review.md>).

[VERIFIED FROM EXPERIMENTS] Toàn bộ số liệu bảng dưới lấy từ A03, thang 0–1. Stage 2 được đánh giá trên 77.141 attack test thật; end-to-end trên toàn bộ 314.521 test rows, gồm BENIGN. Nguồn: [A03, §4–5](<D:/CAO HOC/IDS System/docs/research_audit/03_experiment_review.md>).

| Biến thể Stage 2 main | Val Macro-F1, attack-only | Test Macro-F1, attack-only | Test Macro-F1, end-to-end | Test accuracy, end-to-end |
|---|---:|---:|---:|---:|
| latent_only, XGBoost | 0,880938 | 0,902392 | 0,840758 | 0,995298 |
| latent_plus_pattack_xgb | 0,858131 | 0,910874 | 0,837458 | 0,995285 |
| latent_plus_pattack_mlp | 0,731635 | 0,757557 | 0,734622 | 0,984958 |

[TECHNICAL INTERPRETATION] Latent-only được validation Macro-F1 ủng hộ nhất trong ba cấu hình này; test attack-only cao hơn của latent+P_attack XGB không phải căn cứ đảo lựa chọn. Chưa thể kết luận AE hoặc meta-feature tạo cải thiện ổn định. Nguồn: [A03, §3–4](<D:/CAO HOC/IDS System/docs/research_audit/03_experiment_review.md>).

[VERIFIED FROM EXPERIMENTS] LOACO hiện chỉ có DDoS, ID 26, với 14.272 unknown test samples. Bảng sau là **novelty score-only trên true attack rows**, chưa qua gate và không gồm BENIGN; target known-validation rejection là 5%. Nguồn: [A03, §6](<D:/CAO HOC/IDS System/docs/research_audit/03_experiment_review.md>).

| Score | Unknown recall | Unknown F1 | Known rejection trên test | AUROC |
|---|---:|---:|---:|---:|
| Max probability | 0,260650 | 0,352690 | 0,049357 | 0,785392 |
| One-Class SVM | 0,118694 | 0,177689 | 0,049325 | 0,548214 |
| Isolation Forest | 0,030199 | 0,048283 | 0,050104 | 0,850716 |

[VERIFIED FROM EXPERIMENTS] Với max-probability **sau toàn pipeline**, unknown recall là **0,247197**, precision **0,532207**, F1 **0,337592**; 372 unknown bị Stage 1 chặn, 14 benign bị gán UNKNOWN. Pipeline LOACO có multiclass Macro-F1=0,793589. Chưa có artifact final pipeline cho OCSVM/IF. Nguồn: [A03, §5–6](<D:/CAO HOC/IDS System/docs/research_audit/03_experiment_review.md>).

[TECHNICAL INTERPRETATION] Các số LOACO là kết quả sơ bộ có giới hạn protocol tại mục 5; không phải xác nhận khả năng phát hiện zero-day thực tế.

## 4. Đóng góp kỹ thuật và phát hiện thực nghiệm

- [VERIFIED FROM IMPLEMENTATION] Đã tích hợp pipeline hai tầng với representation learning, calibration, meta-feature và unknown rejection; lưu model, probabilities, class mapping và row identity để truy vết. Nguồn: [A04, C1–C4, C7](<D:/CAO HOC/IDS System/docs/research_audit/04_research_contributions.md>).
- [VERIFIED FROM EXPERIMENTS] Ablation Stage 1 cho thấy scaled features có binary F1 cao hơn latent trong cả hai model family trên split hiện tại; kết quả chưa ủng hộ lợi ích phổ quát của AE. Nguồn: [A04, C2–C3](<D:/CAO HOC/IDS System/docs/research_audit/04_research_contributions.md>).
- [VERIFIED FROM EXPERIMENTS] Main latent-only có 41 benign qua gate, 61 attack bị chặn và 1.377 attack qua gate bị phân loại sai. Infiltration và SQL Injection có final F1=0, với support lần lượt 5 và 2. Nguồn: [A03, §5](<D:/CAO HOC/IDS System/docs/research_audit/03_experiment_review.md>).
- [TECHNICAL INTERPRETATION] Giá trị nghiên cứu rõ nhất hiện nay là triển khai có truy vết và phân tích khoảng cách giữa đánh giá classifier riêng với hiệu quả toàn hệ thống. Nguồn: [A04, C5 và §4](<D:/CAO HOC/IDS System/docs/research_audit/04_research_contributions.md>).
- [REQUIRES FURTHER VERIFICATION] Chưa xác minh novelty học thuật; chưa chứng minh cascade vượt single-stage, meta-feature cải thiện ổn định, hay hệ thống hiệu quả thời gian thực. Nguồn: [A04, §3–4](<D:/CAO HOC/IDS System/docs/research_audit/04_research_contributions.md>).

## 5. Hạn chế hiện tại

- [VERIFIED FROM EXPERIMENTS] **Overlap đầu vào:** 2.253 validation và 2.213 test vectors trùng hoàn toàn 84 features với train, dù full-row hashes khác nhau. Nguồn: [A02, §2.1](<D:/CAO HOC/IDS System/docs/research_audit/02_pipeline_correctness.md>).
- [VERIFIED FROM EXPERIMENTS] **LOACO preprocessing:** scaler fit cả 66.600 DDoS train thuộc lớp heldout. Nguồn: [A02, §2.2](<D:/CAO HOC/IDS System/docs/research_audit/02_pipeline_correctness.md>). [TECHNICAL INTERPRETATION] Đây là tiếp xúc phân bố lớp “chưa biết”, không phải bằng chứng scaler fit trên test; strict LOACO chưa đạt.
- [VERIFIED FROM IMPLEMENTATION] **OOF chưa độc lập hoàn toàn:** outer holdout dùng cho early stopping; calibrator fit toàn OOF targets rồi áp lại cùng hàng; scaler/AE không fold-local. Nguồn: [A02, §3.3](<D:/CAO HOC/IDS System/docs/research_audit/02_pipeline_correctness.md>).
- [VERIFIED FROM IMPLEMENTATION] **Đánh giá và kiểm tra chưa đầy đủ:** open_set_metrics hiện là score-only; check-only chưa bảo đảm đầy đủ ancestry/schema/probability validity; MLP weighted-loss aggregation chưa tương đương global weighted loss. Nguồn: [A02, §3.4–4](<D:/CAO HOC/IDS System/docs/research_audit/02_pipeline_correctness.md>).
- [REQUIRES FURTHER VERIFICATION] **Dữ liệu/nhãn:** chưa chốt nguồn phiên bản và ngữ nghĩa Attempted; không mặc định 26 nhãn ngoài BENIGN tương ứng 26 hành vi tấn công độc lập. Nguồn: [A02, §1](<D:/CAO HOC/IDS System/docs/research_audit/02_pipeline_correctness.md>).
- [REQUIRES FURTHER VERIFICATION] **Khái quát hóa:** chưa định lượng near-duplicate/session dependence, ảnh hưởng ports/lab artifacts, multi-seed, multi-heldout và cross-dataset. Mức metric bị ảnh hưởng bởi các rủi ro chưa được đo. Nguồn: [A02, §2](<D:/CAO HOC/IDS System/docs/research_audit/02_pipeline_correctness.md>), [A03, §8](<D:/CAO HOC/IDS System/docs/research_audit/03_experiment_review.md>).
- [REQUIRES FURTHER VERIFICATION] **Tái lập và triển khai:** thiếu selection lock trước test, complete run provenance, clean-process model replay và runtime/latency đo thực. Metric tính lại khớp không đồng nghĩa training đã được tái lập. Nguồn: [A03, §7](<D:/CAO HOC/IDS System/docs/research_audit/03_experiment_review.md>).

## 6. Năm khái niệm kỹ thuật cần nắm vững

[TECHNICAL INTERPRETATION] Năm nội dung sau là trọng tâm giải thích khi bảo vệ; toàn bộ bảng là định hướng kỹ thuật tổng hợp từ [A05, I3–I6](<D:/CAO HOC/IDS System/docs/research_audit/05_thesis_technical_notes.md>) và [A02](<D:/CAO HOC/IDS System/docs/research_audit/02_pipeline_correctness.md>).

| Khái niệm | Điểm sinh viên cần giải thích chính xác |
|---|---|
| 1. Data leakage và phạm vi fit | Tách train/validation/test; phân biệt test leakage, exposure lớp heldout và phụ thuộc giữa flows. Hash khác nhau không bảo đảm đầu vào hoặc sessions độc lập. |
| 2. OOF, calibration và meta-feature | “Không vào gradient fit” chưa đủ nếu nhãn tham gia chọn checkpoint/calibrator. P_attack dùng làm feature khác với chỉ threshold gating; calibration phải có kiểm chứng chất lượng xác suất. |
| 3. Cascade và metric theo population | Phân biệt binary detection, oracle attack-only và final decision; gate gây false negative/false positive. Macro-F1 cần đi cùng per-class support, không thay bằng accuracy trong dữ liệu mất cân bằng. |
| 4. Representation learning | AE tối ưu reconstruction, không trực tiếp tối ưu nhận diện attack; bottleneck là feature extraction, không phải chọn subset cột. MSE thấp không chứng minh giữ được tín hiệu lớp hiếm. |
| 5. LOACO và operating point | Loại heldout khỏi mọi bước fit/selection, kể cả scaler. AUROC phản ánh ranking qua nhiều ngưỡng, không bảo đảm recall tốt tại ngưỡng cụ thể; LOACO không tương đương zero-day thực tế. |

## 7. Khoảng trống bằng chứng — chính xác cần kiểm tra gì?

[REQUIRES FURTHER VERIFICATION] Toàn bộ các kiểm tra dưới đây còn thiếu hoặc chưa hoàn chỉnh theo [A03, §8](<D:/CAO HOC/IDS System/docs/research_audit/03_experiment_review.md>) và [A06, Phases 1–4](<D:/CAO HOC/IDS System/docs/research_audit/06_improvement_roadmap.md>); không phải kết quả đã đạt.

| Câu hỏi | Kiểm tra/đối chứng cần bổ sung |
|---|---|
| Protocol đã độc lập chưa? | Audit provenance/target policy; split theo group với báo cáo overlap; fit-row lineage cho scaler/AE/folds/calibrator; negative tests cho sai hàng, schema, nhãn, NaN; kiểm tra weighted-loss không phụ thuộc batch partition. |
| Hai tầng và AE có lợi gì? | Single-stage multiclass gồm BENIGN; Stage 2 và cascade dùng scaled features so với latent, cùng split, target policy và selection budget. |
| P_attack/calibration có lợi không? | Latent-only so latent+P_attack cho từng classifier, bổ sung MLP latent-only; OOF sạch; uncalibrated control, Brier/ECE/reliability trên validation. |
| Gate và lớp hiếm có bền vững? | Validation threshold sweep theo false-positive budget; per-class precision/recall/F1/support; nhiều seed và paired/cluster confidence intervals phù hợp. |
| Unknown rejection có khái quát? | Scaler và mọi model known-only; nhiều heldout classes theo eligibility chốt trước; cả ba novelty methods có score-only và final metrics, kể cả benign→UNKNOWN và gate misses. |
| Có thể triển khai/transfer? | Clean-process raw-to-final replay; đo latency/throughput/RAM/VRAM toàn pipeline. Nếu giữ claim cross-dataset: xác minh schema/units/label mapping rồi đánh giá dataset thứ hai độc lập. |

## 8. Năm ưu tiên nghiên cứu tiếp theo

[TECHNICAL INTERPRETATION] Thứ tự dưới đây ưu tiên tính hợp lệ khoa học trước tăng độ phức tạp mô hình, theo [A06](<D:/CAO HOC/IDS System/docs/research_audit/06_improvement_roadmap.md>).

1. [TECHNICAL INTERPRETATION] **Chốt dữ liệu và target semantics:** xác minh phiên bản, thống nhất Attempted policy; giữ raw label bất biến và version hóa target mapping.
2. [TECHNICAL INTERPRETATION] **Bảo đảm độc lập dữ liệu/preprocessing:** thiết kế split theo group, kiểm tra overlap và fit scaler riêng đúng phạm vi từng heldout.
3. [TECHNICAL INTERPRETATION] **Sửa protocol học và đánh giá:** inner selection/cross-calibration cho OOF; hoàn thiện lineage/input checks, loss aggregation và final unknown metrics; khóa tiêu chí chọn model/ngưỡng trước test.
4. [TECHNICAL INTERPRETATION] **Hoàn tất đối chứng và độ ổn định:** single-stage, no-AE, meta-feature controls, nhiều seed; strict multi-heldout nếu open-set là kết luận chính.
5. [TECHNICAL INTERPRETATION] **Củng cố hồ sơ luận văn:** immutable run registry, bảng/hình truy về artifact, literature matrix và phát biểu đóng góp đúng phạm vi; chỉ mở rộng deployment/cross-dataset sau khi core protocol đạt.

[TECHNICAL INTERPRETATION] Giữ main/loaco_26 là kết quả exploratory; không ghi đè lịch sử. Đổi seed, split hay run-id trên dữ liệu đã dùng ra quyết định không tự tạo test độc lập mới. Nguồn: [A06, Phase 2](<D:/CAO HOC/IDS System/docs/research_audit/06_improvement_roadmap.md>).

## 9. Năm nội dung cần quyết định với giảng viên hướng dẫn

1. [REQUIRES FURTHER VERIFICATION] **Định nghĩa target:** nguồn phiên bản nào được công nhận, Attempted được xử lý theo chính sách nào và bằng chứng nào đủ để chốt ontology nhãn?
2. [TECHNICAL INTERPRETATION] **Phạm vi luận văn:** closed-set là kết luận chính hay bắt buộc có strict open-set/LOACO; cross-dataset và triển khai thực tế là yêu cầu hay hướng phát triển?
3. [TECHNICAL INTERPRETATION] **Thiết kế evaluation:** đơn vị độc lập là flow group, session hay thời gian; giải quyết class coverage hiếm thế nào; xử lý test đã xem và phần đánh giá xác nhận ra sao?
4. [TECHNICAL INTERPRETATION] **Bộ thí nghiệm tối thiểu:** chốt single-stage/no-AE/meta-feature controls, ngân sách tuning, số seed/heldout và tiêu chí primary metric/FPR budget trước khi chạy tiếp?
5. [REQUIRES FURTHER VERIFICATION] **Chuẩn đóng góp có thể bảo vệ:** bằng chứng nào đủ để công nhận giá trị phân tích error propagation/representation/meta-feature; cần đối chiếu công trình nào trước khi tuyên bố tính mới?

Nguồn định hướng thảo luận: [A04, §4](<D:/CAO HOC/IDS System/docs/research_audit/04_research_contributions.md>), [A06, §8–9](<D:/CAO HOC/IDS System/docs/research_audit/06_improvement_roadmap.md>), [A07](<D:/CAO HOC/IDS System/docs/research_audit/07_executive_summary.md>).

[TECHNICAL INTERPRETATION] **Kết luận tiến độ:** nền tảng triển khai và bộ kết quả sơ bộ đã hình thành; chưa đủ cơ sở dùng toàn bộ số liệu hiện tại làm bằng chứng cuối cho hiệu quả hoặc generalization. Bước quyết định tiếp theo là sửa protocol và bổ sung đối chứng có kiểm soát, không phải thêm thuật toán mới.
