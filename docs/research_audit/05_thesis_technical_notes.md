# 05 — Ghi chú kỹ thuật luận văn và chuẩn bị bảo vệ

Ngày 24/10/2026; project duy nhất D:\CAO HOC\IDS System; snapshot 895cc8b.
Dùng cùng [docs/research_audit/02_pipeline_correctness.md](<D:/CAO HOC/IDS System/docs/research_audit/02_pipeline_correctness.md>) và [docs/research_audit/03_experiment_review.md](<D:/CAO HOC/IDS System/docs/research_audit/03_experiment_review.md>). Phần này giải thích implementation hiện tại, không hợp thức hóa các lỗi protocol.

## I1. Bài toán nghiên cứu

Đầu vào hiện tại là bản ghi flow đã được trích xuất thành CSV, không phải packet stream trực tiếp. Hệ thống cần phân biệt BENIGN và ATTACK; với traffic bị coi là attack, phân loại known attack hoặc reject thành UNKNOWN khi bật novelty.

Bài toán có ba trục nên tách rõ:

1. Detection: có nhận ra attack hay không, chịu ràng buộc false alarms.
2. Known attack classification: phân biệt class sau detection, đặc biệt lớp hiếm.
3. Unknown rejection: không ép mọi attack vào known class; chỉ mới mô phỏng qua LOACO.

Câu hỏi nghiên cứu phù hợp: representation16 chiều giữ được bao nhiêu chất lượng so84 features; scalar P_attack có bổ sung thông tin; gate ảnh hưởng minority classes thế nào; novelty score hoạt động ra sao dưới một known-rejection budget. Không mặc định các câu hỏi đều có kết quả tích cực.

## I2. Kiến trúc thực tế và dependency

Luồng training hiện tại:

CSV → cleaning/full-row dedup → stratified random split → scaler train chung → AE train → latent theo row order → Stage 1 folds/final + calibration → P_attack → Stage 2 attack-only → predictions → evaluation.

Stage 1 có thể dùng scaled 84 thay latent. Main Stage 2 có ba cấu hình: XGB latent 16, XGB latent 16+p, MLP latent 16+p. Các pipeline đã lưu đều sử dụng gate XGB latent. Novelty hiện chỉ có LOACO-26, với maxprob/OCSVM/IF, và final pipeline chỉ cho maxprob.

Luồng quyết định:

Flow features → scaler đóng băng → encoder khi cần → Stage 1 P_attack → gate0,5 → BENIGN hoặc Stage 2 class → optional unknown rejection → final label.

Phải phân biệt sơ đồ logic với cách chạy hiện tại: script04 đã predict Stage 2 cho mọi test row; script06 ghép arrays. Chưa có evidence về online flow extraction hoặc chỉ thực thi Stage 2 cho attack trong production.

Dẫn source: [scripts/02_train_autoencoder.py](<D:/CAO HOC/IDS System/scripts/02_train_autoencoder.py:34>), [scripts/03_train_stage1.py](<D:/CAO HOC/IDS System/scripts/03_train_stage1.py:33>), [scripts/04_train_stage2.py](<D:/CAO HOC/IDS System/scripts/04_train_stage2.py:20>), [scripts/06_evaluate_pipeline.py](<D:/CAO HOC/IDS System/scripts/06_evaluate_pipeline.py:93>).

## I3. Thuật toán cốt lõi

- Standardization: trung bình/phương sai fit train, transform cố định. Main train-only đã kiểm chứng; strict LOACO chưa có scaler riêng.
- Dense AE: học tái tạo đầu vào84 chiều qua bottleneck16. Học joint, không chứng minh greedy SAE; fit cả benign và attack train.
- XGBoost: binary:logistic Stage 1, multi:softprob Stage 2; class weighting và early stopping.
- MLP: LayerNorm/ReLU/dropout; weighted BCE ở Stage 1, weighted CE ở Stage 2.
- Platt-style calibration: logistic regression trên logit của probability, fit OOF labels. Không biến calibration thành bảo đảm xác suất đúng tuyệt đối.
- OOF: loại hàng khỏi fold fitting trước khi tạo meta-feature; code hiện còn chọn epoch bằng chính outer holdout và self-calibration.
- Novelty: maxprob là thiếu tự tin của known-class classifier; OCSVM/IF là anomaly scores trên latent known attacks. AE reconstruction error không được dùng làm novelty score trong implementation hiện tại.

## I4. Các quyết định phải giải thích được

| Quyết định | Lập luận có thể dùng | Điều chưa được chứng minh |
|---|---|---|
| Hai giai đoạn | Tách detection và nhận diện attack, cho phép kiểm soát gate | Hơn single-stage về accuracy/tài nguyên |
| XGBoost và MLP | So sánh cây boosting với dense network trên tabular features | Superiority mọi cấu hình/dataset |
| AE16 chiều | Thử học representation gọn hơn | Nén giữ tín hiệu lớp hiếm hoặc nhanh hơn tổng pipeline |
| BENIGN không vào Stage 2 | Stage 2 conditional classifier cho known attacks | Gate không bao giờ đưa benign vào Stage 2 |
| P_attack meta-feature | Scalar tóm tắt bằng chứng attack của Stage 1 | Nó độc lập với latent hoặc luôn thêm thông tin |
| Calibration | Giúp score có ý nghĩa hơn khi chọn gate/meta-feature | Đã calibrated tốt khi chưa có reliability/Brier/ECE |
| Gate0,5 | Giá trị cố định đang triển khai | Là ngưỡng tối ưu cho false-alarm budget |
| Macro-F1 | Không để lớp đông chi phối như accuracy/weighted-F1 | Ước lượng ổn định khi support1–5 |
| LOACO | Mô phỏng một class không tham gia known learning | Zero-day thực tế hoặc mọi attack chưa thấy |
| Giữ nhãn raw | Bảo toàn dữ liệu gốc để truy vết | Mọi annotation nên thành target class riêng |
| Random stratification | Giữ class coverage trên benchmark | Độc lập sessions/time/domain |
| Seed42 | Có điểm khởi đầu tái lập | Bitwise determinism hoặc uncertainty do training |

## I5. Công thức đúng với code

Ký hiệu x∈R^84; S là scaler; z=Eθ(S(x))∈R^16; y=0 là BENIGN, y∈K là known attack. Các hàm dưới là ước lượng/score của model, không coi như posterior đã được chứng minh calibrated.

### Standardization và reconstruction

\[
\widetilde x_j=\frac{x_j-\mu_{j,\mathrm{train}}}{\sigma_{j,\mathrm{train}}},
\qquad
\mathcal L_{\mathrm{AE}}=\frac{1}{nd}\sum_{i=1}^{n}\sum_{j=1}^{d}
\left(\widetilde x_{ij}-D_\phi(E_\theta(\widetilde x_i))_j\right)^2.
\]

Nếu scale bằng0, implementation thay bằng1. Trong strict LOACO, “train” phải là known-only train; code hiện chưa bảo đảm phần scaler này. Nguồn: [src/preprocessing.py](<D:/CAO HOC/IDS System/src/preprocessing.py:59>), [src/autoencoder.py](<D:/CAO HOC/IDS System/src/autoencoder.py:73>).

### Stage 1, calibration và gate

\[
p_{\mathrm{raw}}(x)=f_1(v(x)),\quad
v(x)\in\{\widetilde x,z\},
\]
\[
p(x)=\sigma\!\left(a\,\operatorname{logit}
(\operatorname{clip}(p_{\mathrm{raw}},10^{-6},1-10^{-6}))+b\right),
\qquad
g(x)=\mathbf1[p(x)\ge\tau_1],\quad\tau_1=0.5.
\]

Với MLP, p_raw là sigmoid(logit); XGB trả binary logistic probability. a,b học từ OOF scores/targets bằng LogisticRegression; không calibration trên test theo source. Nguồn: [src/calibration.py](<D:/CAO HOC/IDS System/src/calibration.py:8>).

### Stage 2 và prediction closed-set

\[
u(x)=z \ \text{hoặc}\ [z;p(x)],\quad
q_k(x)=f_{2,k}(u(x)),\quad
k^*(x)=\arg\max_{k\in K}q_k(x).
\]
\[
\widehat y_{\mathrm{closed}}(x)=
\begin{cases}
0,& g(x)=0,\\
k^*(x),& g(x)=1.
\end{cases}
\]

q được train attack-only với weighting. Không nên viết q chính xác bằng P(y=k|ATTACK,x) theo nghĩa calibration đã xác nhận. Source dùng class_ids để map argmax position về ID thật, không dùng vị trí0 làm BENIGN. Nguồn: [src/stage2.py](<D:/CAO HOC/IDS System/src/stage2.py:12>), [src/evaluation.py](<D:/CAO HOC/IDS System/src/evaluation.py:20>).

### Unknown rejection

\[
s_{\max p}(x)=1-\max_{k\in K}q_k(x),\quad
s_{\mathrm{OCSVM}}(x)=-\mathrm{decision\_function}(z),\quad
s_{\mathrm{IF}}(x)=-\mathrm{score\_samples}(z).
\]
\[
\tau_U=Q_{0.95}\{s(x):x\in V_{\mathrm{known\ attacks}}\}.
\]
\[
\widehat y(x)=
\begin{cases}
0,& p(x)<\tau_1,\\
-1,& p(x)\ge\tau_1\land s(x)\ge\tau_U,\\
k^*(x),&\text{còn lại}.
\end{cases}
\]

Với ties, quantile95 và phép ≥ không bảo đảm rejection đúng chính xác5%. Mẫu số calibration là known ATTACK validation, không phải mọi traffic. Nguồn: [src/novelty.py](<D:/CAO HOC/IDS System/src/novelty.py:19>), [src/evaluation.py](<D:/CAO HOC/IDS System/src/evaluation.py:24>).

### Metric và error propagation

\[
\mathrm{DR}=\frac{TP}{TP+FN},\quad
\mathrm{FPR}=\frac{FP}{FP+TN},\quad
\mathrm{FNR}=\frac{FN}{TP+FN}.
\]
\[
F1_k=\frac{2P_kR_k}{P_k+R_k},\quad
\mathrm{MacroF1}=\frac1C\sum_kF1_k,\quad
\mathrm{WeightedF1}=\sum_k\frac{n_k}{N}F1_k.
\]

Trong closed-set cascade, ba tập lỗi rời nhau:

\[
E=E_{\mathrm{benign\ passed}}+E_{\mathrm{attack\ blocked}}
  +E_{\mathrm{passed\ attack\ wrong}},\quad
\mathrm{Accuracy}_{\mathrm{E2E}}=1-\frac{E}{N}.
\]

Với unknown class U:

\[
R_U^{\mathrm{final}}
=\frac{\sum_i\mathbf1[y_i=U,\,g_i=1,\,s_i\ge\tau_U]}
{\sum_i\mathbf1[y_i=U]}.
\]

Score-only recall bỏ g khỏi tử số nên có thể lớn hơn final recall. Unknown precision/F1 cuối phải tính cả false unknown từ BENIGN. PR_AUC trong src/metrics.py thực tế là average_precision_score (AP), không phải diện tích trapezoidal đường PR. Nguồn: [src/metrics.py](<D:/CAO HOC/IDS System/src/metrics.py:8>).

## I6. Hai mươi câu hỏi bảo vệ

| Câu hỏi | Hội đồng kiểm tra gì? | Bằng chứng hiện có | Câu trả lời kỹ thuật gợi ý và caveat |
|---|---|---|---|
| 1. Dataset có đúng bản CICIDS2017 gốc? | Provenance | 5 CSV,raw_manifest,schema | Thuộc họ CICIDS2017 nhưng schema gợi ý bản cải tiến; hash chỉ bảo đảm local integrity. Chưa đủ bằng chứng xác định archive upstream. |
| 2. Vì sao có27 nhãn? | Target semantics | label_mapping,base.json | Có1 BENIGN và26 annotation labels ngoài benign, gồm Attempted. Không khẳng định26 hành vi độc lập; cần chốt label policy trước đánh giá cuối. |
| 3. Vì sao dùng hai-stage thay một classifier? | Research hypothesis | evaluation.py;3 main pipelines | Tách detection và attack recognition để phân tích gate. Chưa có single-stage control nên chưa chứng minh hơn. |
| 4. Stage 2 có thấy BENIGN lúc train? | Conditional task | 04_train_stage2.py:67 | Không; chỉ known attacks. Lúc evaluation mọi flow có score, gate quyết định sử dụng; benign lọt gate bị ép vào attack/unknown. |
| 5. P_attack có phải một feature thật? | Stacking vs gating | stage2_matrix:29;2 meta runs | Có trong latent+p variants thành17 chiều, đồng thời dùng gate. Latent-only không có cột p. Không gọi mọi cascade là stacking. |
| 6. Tại sao OOF vẫn có leakage? | Nested model selection | 03_train_stage1.py:86–128 | Hàng không vào gradient fit nhưng labels tham gia chọn epoch/tree và calibrator áp lại cùng target. Cần inner selection/cross-calibration. |
| 7. AE có làm tăng độ chính xác? | Ablation |4 Stage 1 metrics | Chưa; scaled 84 tốt hơn latent 16 trong binary snapshot. Cần raw Stage 2/cascade và tài nguyên đo thực. |
| 8. Đây là SAE hay AE? | Algorithm fidelity | autoencoder.py:12 | Deep dense AE đối xứng huấn luyện joint. Không có greedy layer-wise pretraining; tránh dùng thuật ngữ gây hiểu nhầm. |
| 9. Vì sao train AE cả attack? | Representation vs anomaly | 02_train_autoencoder.py:37 | Mục tiêu reconstruction representation cho supervised downstream, không benign-only anomaly detector. Reconstruction error hiện không dùng reject. |
| 10. Threshold0,5 được chọn thế nào? | Operating-point control | model_config.evaluation | Cố định trong config, chưa threshold sweep theo FPR budget. Không tuyên bố đã tối ưu. |
| 11. Calibration có tác dụng gì? | Probability quality | calibration.py;joblib | Logistic transform giúp ánh xạ score; cần reliability/Brier/ECE để chứng minh. F1 cao không tự chứng minh calibration tốt. |
| 12. Test có dùng fit không? | Leakage distinctions | prep/train scripts | Không thấy trực tiếp fit test. Nhưng feature duplicates, LOACO scaler và OOF selection vẫn là lỗi khác; không trả lời đơn giản “không leakage”. |
| 13. Dedup đã làm rồi sao còn trùng? | Representation-level identity | full-row hash + audit overlap | Hash89 cột trước drop khác với84 input; 2.213 test vectors trùng train. Chưa đo mức metric inflation. |
| 14. Accuracy99,53% có đủ tốt? | Imbalance | finalMacroF1 = 0,840758;per-class | Không đủ: Infiltration/SQL Injection finalF1 = 0 với support5/2. Cần macro,recall,FPR,per-class và uncertainty. |
| 15. Stage 2 F1 cao sao final thấp? | Error propagation |41+61+1377 lỗi | Stage 2 oracle giả định biết attack thật; gate chặn attack/cho benign qua. So metric phải giữ đúng population. |
| 16. LOACO hiện thực sự unseen chưa? | Full preprocessing isolation | scaler n1467762;26train66600 | Model fit đã bỏ26, scaler chưa bỏ; strict unseen chưa đạt. Sửa toàn preprocessing và tạo run mới. |
| 17. Recall unknown là26,07% hay24,72%? | Score vs final metric | novelty JSON/finalCSV | 26,07% là isolated score-only;24,72% là final qua gate. F1 trên toàn test cũng phải tính false unknown từ benign. |
| 18. Vì sao IF AUROC tốt nhưng recall thấp? | Ranking vs threshold | AUROC0,850716,recall = 0,030199 | AUROC tích hợp nhiều ngưỡng, q95 known-val là một operating point. Không chọn threshold bằng unknown test để nâng recall. |
| 19. Kết quả có tái lập/đủ thống kê không? | Reproducibility | seed42,artifacts,bootstrap | Saved predictions tái tính khớp; chưa retrain, multi-seed hay clustered CI. Config CUDA không deterministic; CI accuracy không bao phủ training uncertainty. |
| 20. Đóng góp mới và khả năng triển khai ở đâu? | Novelty/external validity | Pipeline,ablation,error analysis | Đóng góp chắc nhất là engineering và phân tích có kiểm soát sau sửa protocol. Chưa systematic review,cross-dataset,online inference hoặc latency; không gọi production/zero-day đã chứng minh. |

Các câu trả lời này phải được cập nhật nếu protocol/artifact thay đổi; không học thuộc số cũ như kết quả cuối.

## I7. Ghi chú có thể chuyển vào luận văn

### Chương phương pháp

“Hệ thống khảo sát kiến trúc phân tầng: bộ phân loại nhị phân tạo điểm attack và điều khiển gate, sau đó bộ phân loại attack-only dự đoán known class. Các thí nghiệm so sánh representation gốc đã scale với latent, và khảo sát P_attack như meta-feature. Đánh giá được tách theo detection, conditional classification và quyết định end-to-end.”

Bổ sung riêng mô tả protocol cuối sau khi sửa; không viết các sửa đổi đề xuất như đã thực hiện.

### Chương triển khai

“Dữ liệu được đọc theo chunk và lưu mảng float32/memmap, đi kèm split IDs, row hashes và class mapping. Model artifacts gồm encoder checkpoints, Stage 1 fold/final/calibrator, Stage 2 model/probabilities và novelty thresholds. Script evaluation ghép predictions theo test indices cố định.”

Giới hạn: chưa deploy raw-to-final độc lập; chưa benchmark model reload; metadata ancestry chưa đầy đủ.

### Thiết lập thực nghiệm

Nêu dataset version còn cần xác minh, file hashes, target policy,84 features, seed42, split units, số mẫu từng lớp, train/validation/test responsibilities, class weighting, early stopping metric và gate0,5. Ghi môi trường audit khác với môi trường train lịch sử chưa được snapshot đầy đủ. Không coi CUDA version ở config là runtime log đã kiểm chứng.

### Kết quả và thảo luận

“Trong bộ kết quả hiện có, latent-only Stage 2 đạt validation Macro-F1 cao nhất trong ba cấu hình chính. End-to-end main latent-only đạt Macro-F1 = 0,840758, thấp hơn oracle attack-only0,902392; một số lớp ít mẫu không được nhận diện đúng ở đầu ra cuối.”

Các số là preliminary của split hiện tại, không trộn với future corrected runs. Không dùng latent+p test tốt hơn để đổi quyết định được yêu cầu dựa trên validation.

### Hạn chế

Nêu duplicate feature overlap; random split không session/time-independent; target semantics; OOF early stopping/calibration; scaler LOACO; sparse class support; một heldout class; no cross-dataset; no runtime evidence. Nêu rõ phần nào confirmed và phần nào potential.

### Hướng phát triển

Correctness → đối chứng closed-set → strict multi-class LOACO → extended validation nếu cần → consolidation. Không ưu tiên thêm Transformer/LLM/GAN khi chưa có câu hỏi nghiên cứu và baseline.

## I8. Context contract để tránh quên ngữ cảnh/hallucination

- Project duy nhất: D:\CAO HOC\IDS System; mọi kết luận current phải kiểm tra lại source/artifact ở đây.
- Trạng thái audit: đã có training results, nhưng đang audit-only; không tự train/chỉnh config vì có roadmap.
- Không dùng test cho fit, calibration, thresholding hoặc lựa chọn model; test đã xem phải ghi vai trò exploratory.
- Phải xác định dataset version, label policy, feature schema, split hash và upstream lineage trước mỗi claim.
- Tên run không chứng minh identity; --check-only không chứng minh correctness toàn protocol.
- Phân biệt số học đã kiểm chứng, kết luận có điều kiện và giả thuyết chưa kiểm chứng.
- Không tuyên bố LOACO valid chỉ từ held_out_label_id khớp; phải kiểm cả scaler và mọi bước fit.
- Không invent metric, latency, paper citation, novelty hoặc progress percentage.
- Không sửa memory hay trạng thái dự án ngầm; update tài liệu chỉ sau bằng chứng mới và đúng phạm vi người dùng cho phép.
- Báo cáo audit phản ánh commit 895cc8b; khi source/results đổi, ghi run/commit mới thay vì ghi đè lịch sử.
