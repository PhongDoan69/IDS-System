# 04 — Đóng góp nghiên cứu, phát hiện thực nghiệm và giới hạn tuyên bố

Root duy nhất D:\CAO HOC\IDS System. Snapshot 895cc8b, 24/10/2026.
Bằng chứng định lượng: [docs/research_audit/03_experiment_review.md](<D:/CAO HOC/IDS System/docs/research_audit/03_experiment_review.md>); giới hạn protocol: [docs/research_audit/02_pipeline_correctness.md](<D:/CAO HOC/IDS System/docs/research_audit/02_pipeline_correctness.md>).

## 1. Phân biệt bốn loại đóng góp

| Nhóm | Có thể trình bày | Không được đánh đồng |
|---|---|---|
| A. Implemented engineering work | Pipeline modular, memmap, lưu artifact, probability handoff, cascade, novelty và evaluation | Có code không đồng nghĩa thuật toán mới |
| B. Experimentally supported findings | Quan sát số học trên snapshot/split hiện tại, có điều kiện và support | Một seed không đồng nghĩa kết quả tổng quát hoặc superiority |
| C. Potential research contributions | Giả thuyết có cơ chế, cần baseline/ablation/literature | Ý tưởng tích hợp không tự tạo novelty |
| D. Unsupported claims | Chỉ liệt kê để tránh dùng trong luận văn | Không đưa thành kết luận đã đạt |

Mức tin cậy dưới đây chỉ cho phát biểu cụ thể, không phải điểm chất lượng đề tài. “Cao” nghĩa source/artifact kiểm chứng trực tiếp; “trung bình” là diễn giải hợp lý trong phạm vi hẹp; “thấp/chưa xác minh” là chưa có bằng chứng cần thiết.

## 2. Các ứng viên đóng góp

### C1. Pipeline IDS hai giai đoạn có artifact truy vết

1. Cơ chế: binary gate BENIGN/ATTACK trước attack classifier; mapping ID riêng và ghép final predictions có row_hash.
2. Source: [src/evaluation.py](<D:/CAO HOC/IDS System/src/evaluation.py:9>), [scripts/06_evaluate_pipeline.py](<D:/CAO HOC/IDS System/scripts/06_evaluate_pipeline.py:93>), [scripts/01_prepare_data.py](<D:/CAO HOC/IDS System/scripts/01_prepare_data.py:117>).
3. Bằng chứng: cả ba main pipeline có prediction CSV; tái ghép và metric khớp; khung ingest→scale→encode→classify hoạt động.
4. Thiếu: strict provenance, inference raw-to-final trong clean process, deployment; độc lập split còn vấn đề.
5. Baseline cần: single-stage multiclass gồm BENIGN, cùng features/split/tuning budget; cascade với các gate khác.
6. Cách viết: “Đã xây dựng và kiểm chứng tính nhất quán của một pipeline phân loại luồng mạng hai giai đoạn phục vụ thực nghiệm offline.”
7. Tin cậy: cao cho triển khai A; chưa xác minh tính mới C. Hai-stage IDS tự thân không phải bằng chứng đóng góp thuật toán mới.

### C2. Đánh giá representation 84 chiều so với latent 16

1. Cơ chế: AE reconstruction nén features, dùng cùng không gian latent cho classifiers.
2. Source: [src/autoencoder.py](<D:/CAO HOC/IDS System/src/autoencoder.py:12>), [scripts/03_train_stage1.py](<D:/CAO HOC/IDS System/scripts/03_train_stage1.py:33>).
3. Bằng chứng: hai latent artifacts; Stage 1 có đầy đủ XGB/MLP × scaled/latent; raw-scaled binary F1 cao hơn latent trong cả hai family tại snapshot.
4. Thiếu: raw Stage 2/cascade, multi-seed, latent-dimension ablation, latency/memory đo thực.
5. Baseline cần: no-AE, PCA nếu muốn kiểm tra nén tuyến tính, cùng điều kiện classifier/tuning. PCA chưa triển khai, không mô tả như đã có.
6. Cách viết: “Trên split khảo sát, nén từ84 xuống16 chiều chưa đem lại cải thiện binary classification; cần kiểm tra trade-off tài nguyên và phân lớp attack.”
7. Tin cậy: cao cho quan sát B, thấp cho giả thuyết latent giúp generalization. Kết quả âm được báo cáo trung thực vẫn có giá trị; không ép AE thành thành phần bắt buộc để giữ câu chuyện.

### C3. So sánh XGBoost và MLP trong Stage 1

1. Cơ chế: boosted trees so với mạng dense, hai representation và weighted binary objectives.
2. Source: [src/stage1_xgboost.py](<D:/CAO HOC/IDS System/src/stage1_xgboost.py:15>), [src/stage1_mlp.py](<D:/CAO HOC/IDS System/src/stage1_mlp.py:12>).
3. Bằng chứng: bốn cấu hình main, saved5-fold/final/calibrator; XGB scaled FP15/FN7, MLP scaled FP44/FN52 trên cùng test.
4. Thiếu: fair tuning budget, nhiều seed, paired CI; OOF protocol chưa độc lập hoàn toàn.
5. Baseline cần: matched representation, matched selection metric, hyperparameter search chỉ train/validation.
6. Cách viết: “Trong các cấu hình đã chạy, XGBoost trên scaled features cho ít lỗi binary hơn MLP; chưa suy rộng ra mọi cấu hình hoặc môi trường mạng.”
7. Tin cậy: cao cho số đếm B; trung bình cho lựa chọn baseline thực dụng; không phải novelty riêng.

### C4. Attack probability như meta-feature

1. Cơ chế: ghép [z,p_attack] thành17 chiều, dùng scalar từ Stage 1 train OOF và final prediction cho val/test.
2. Source: [src/stage2.py](<D:/CAO HOC/IDS System/src/stage2.py:29>), [scripts/03_train_stage1.py](<D:/CAO HOC/IDS System/scripts/03_train_stage1.py:86>), [src/calibration.py](<D:/CAO HOC/IDS System/src/calibration.py:13>).
3. Bằng chứng: hai Stage 2 experiment thực sự consume P_attack, không chỉ gate; XGB latent+p valMacro-F1 = 0,858131 thấp hơn latent-only0,880938; finalMacro-F1 cũng thấp hơn trong main.
4. Thiếu: strict cross-fitting/calibration, MLP latent-only, ablation no-calibration, repeated runs.
5. Baseline cần: latent-only vs latent+p với cùng classifier; p từ different Stage 1 representation nhưng chọn trên validation; có thể scalar random/shuffled chỉ như negative control train-side được thiết kế trước.
6. Cách viết: “Đã khảo sát xác suất attack như đặc trưng phụ; kết quả hiện tại chưa xác nhận lợi ích ổn định.”
7. Tin cậy: cao cho engineering A và quan sát B; tính đóng góp C còn phụ thuộc sửa protocol/literature. Không nói “stacking hoàn toàn không leakage”.

### C5. Đo và phân tích error propagation

1. Cơ chế: phân rã benign qua gate, attack bị chặn, attack qua gate phân lớp sai; đối chiếu oracle Stage 2 và cascade.
2. Source: [scripts/04_train_stage2.py](<D:/CAO HOC/IDS System/scripts/04_train_stage2.py:157>), [src/evaluation.py](<D:/CAO HOC/IDS System/src/evaluation.py:20>); phép tính audit từ final CSV.
3. Bằng chứng: latent-only có41+61+1377=1479 lỗi; Stage 2 oracleMacro-F1 = 0,902392 so final0,840758. Infiltration và SQL Injection có F1 cuối bằng0.
4. Thiếu: threshold sensitivity trên validation; effect trên từng family/group và uncertainty.
5. Baseline cần: cùng Stage 2 với oracle gate và các gate được chọn trước; cost-sensitive validation operating points.
6. Cách viết: “Phân tích cho thấy đánh giá classifier attack riêng có thể che lấp tổn thất ở tầng phát hiện, nhất là lớp ít mẫu.”
7. Tin cậy: cao cho B. Đây là hướng đóng góp phân tích có giá trị cho luận văn nếu được chuẩn hóa sau sửa split; chưa có cơ chế mới “kiểm soát lỗi” đã triển khai.

### C6. Nghiên cứu class imbalance và nhóm hiếm

1. Cơ chế: Stage 1 class-ratio weight; Stage 2 balanced sample/class weights; macro metrics và per-class audit.
2. Source: [src/stage1_xgboost.py](<D:/CAO HOC/IDS System/src/stage1_xgboost.py:9>), [src/stage2.py](<D:/CAO HOC/IDS System/src/stage2.py:59>), [src/stage2.py](<D:/CAO HOC/IDS System/src/stage2.py:95>).
3. Bằng chứng: các nhãn còn support nhỏ; lớpSQLAttempted chỉ1 test và F1 = 0; high accuracy không bảo đảm minority detection.
4. Thiếu: justification ngữ nghĩa Attempted, confidence intervals, weight ablation, class-wise error analysis đầy đủ.
5. Baseline cần: weighted vs unweighted theo cùng protocol và label policy đã thống nhất. Không resample validation/test; không synthetic oversampling trước split.
6. Cách viết: “Cơ chế weighting đã được triển khai nhưng chưa chứng minh giải quyết được lớp hiếm; kết quả được báo kèm support.”
7. Tin cậy: cao cho A/B; thấp cho tuyên bố “khắc phục mất cân bằng”. Đây là điểm cần trung thực khi bảo vệ.

### C7. LOACO và unknown rejection ở operating point cố định

1. Cơ chế: loại một class khỏi known training; score1-maxp,OCSVM,IF; thresholdq95 known-validation; UNKNOWN chỉ sau gate.
2. Source: [scripts/05_train_novelty.py](<D:/CAO HOC/IDS System/scripts/05_train_novelty.py:80>), [src/novelty.py](<D:/CAO HOC/IDS System/src/novelty.py:19>), [src/evaluation.py](<D:/CAO HOC/IDS System/src/evaluation.py:24>).
3. Bằng chứng: DDoS heldout26; score-only IF AUROC0,850716 nhưng recall = 0,030199 tại threshold; maxprob final unknown recall = 0,247197.
4. Thiếu: scaler known-only, full cross-stage lineage, multi-heldout, method selection không dùng unknown test; metrics final cho mọi method.
5. Baseline cần: cùng heldout/protocol cho cả3 methods, no-rejection closed-set control, aggregate macro theo heldout và report từng lớp.
6. Cách viết: “Đã triển khai thí nghiệm sơ bộ unknown rejection trên DDoS giữ lại; kết quả chưa đáp ứng đầy đủ strict LOACO và không chứng minh zero-day thực tế.”
7. Tin cậy: cao cho A và số học B; thấp cho kết luận generalization. Đây là hướng C đáng làm tiếp sau correctness, không phải đóng góp đã hoàn tất.

### C8. Tổ chức tài nguyên tính toán

1. Cơ chế: memmap/chunk, float32, latent nhỏ, CUDA hist, AMP, batch giới hạn, novelty sample caps.
2. Source: [configs/model_config.json](<D:/CAO HOC/IDS System/configs/model_config.json:11>), [src/model_data.py](<D:/CAO HOC/IDS System/src/model_data.py:65>), [src/autoencoder.py](<D:/CAO HOC/IDS System/src/autoencoder.py:134>).
3. Bằng chứng: code/config có các cơ chế đó; dataset và model artifacts tồn tại; môi trường Python/torch/CUDA-wheel đọc được.
4. Thiếu: runtime thực, peak RAM/VRAM, throughput/latency, failed/OOM runs; elapsed_seconds=0 chưa đo.
5. Baseline cần: đo CPU/GPU/raw/latent dưới cùng batch và phần cứng; tính chi phí encoder+data transfer+calibration+gate.
6. Cách viết: “Implementation có lựa chọn kỹ thuật nhằm giới hạn tài nguyên, nhưng chưa đánh giá định lượng hiệu quả tính toán.”
7. Tin cậy: cao cho A; chưa đủ bằng chứng cho efficiency contribution. Không gọi cấu hình là tối ưu nhất.

### C9. Cross-dataset generalization

1. Cơ chế dự kiến: fit nguồn và evaluate target độc lập với common schema/units/label ontology.
2. Source: chưa có loader/mapping/run tương ứng trong project; đây là mục tiêu đề bài.
3. Bằng chứng: không có metrics hoặc artifacts cho dataset thứ hai.
4. Thiếu: mọi bằng chứng thực nghiệm, compatibility và budget.
5. Baseline cần: within-dataset control và source→target transfer không fit target test.
6. Cách viết: “Cross-dataset evaluation là hướng mở rộng; chưa được thực hiện.”
7. Tin cậy: cao cho đánh giá hiện trạng D; không được liệt kê như đóng góp đã đạt.

## 3. Những khẳng định phải tránh

| Khẳng định không đủ bằng chứng | Cách diễn đạt đúng hơn |
|---|---|
| Hệ thống hoàn toàn không leakage | Đã có kiểm soát test fit ở một số bước, nhưng split/OOF/LOACO còn điểm cần sửa |
| LOACO đã mô phỏng nghiêm ngặt lớp chưa thấy | Đã loại heldout trong model fitting; scaler chung còn tiếp xúc heldout train |
| Nhận diện26 loại tấn công độc lập | Phân loại26 non-BENIGN annotation labels; target semantics chưa chốt |
| SAE mới/thuật toán mới | Dense AE nhiều lớp huấn luyện joint; novelty chưa được khảo sát tài liệu |
| Meta-feature làm tăng độ chính xác | Kết quả tăng/giảm phụ thuộc metric và split; validation chưa ủng hộ lợi ích |
| Accuracy99,53% tức mọi attack được phát hiện tốt | Một số lớp hiếm có finalF1 = 0; cần per-class/support |
| Phát hiện zero-day đã được chứng minh | Mới một heldout class trong benchmark, protocol còn giới hạn |
| Nhanh/real-time/tối ưu RTX3050 | Chưa benchmark; chỉ cấu hình nhằm phù hợp tài nguyên |
| Generalize sang mạng/dataset khác | Chưa có cross-dataset hoặc deployment evidence |
| Unit tests PASS chứng minh experimental validity | Test coverage chưa bao gồm những lỗi protocol đã xác nhận |

## 4. Khuyến nghị định vị luận văn

Nên định vị là “thiết kế, triển khai và đánh giá có kiểm soát IDS hai giai đoạn”, với câu hỏi nghiên cứu rõ về representation, meta-feature và error propagation. Với trình độ Thạc sĩ, một nghiên cứu so sánh tái lập được, có negative findings, kiểm soát leakage và phân tích giới hạn có giá trị hơn việc tăng số thuật toán nhưng thiếu protocol.

Bộ đóng góp có triển vọng nhất:

- A: pipeline có artifact contract và khả năng truy vết, sau khi bổ sung provenance.
- B: phân tích sự khác biệt giữa detection, oracle classification và final errors.
- B/C: đánh giá có đối chứng latent và P_attack, chấp nhận khả năng không cải thiện.
- C: LOACO nhiều lớp với operating point kiểm soát false rejection, sau khi sửa preprocessing.

Chưa thực hiện independent novelty review. Thư mục [Tài liệu tham khảo](<D:/CAO HOC/IDS System/Tài liệu tham khảo>) có15 PDF nhưng audit này không gán nội dung/tác giả/DOI chưa đọc. Trước khi tuyên bố “đề xuất mới”, cần literature matrix gồm kiến trúc, dataset version, split unit, OOF/calibration, unknown protocol, metric và chi phí của từng công trình. Không so điểm số với bài khác khi khác phiên bản CICIDS2017/nhãn/split.

Kết luận về mức đóng góp cuối cùng cần người hướng dẫn đánh giá theo yêu cầu chương trình; audit không thay thế phê duyệt học thuật.
