# Tổng kết thực nghiệm đợt 1 — CICIDS2017

Ngày tổng kết: 26/10/2026. Thư mục: `D:\CAO HOC\IDS System`. Round ID: `round1_20261026_s42`. Đây là báo cáo bổ sung; không sửa báo cáo audit, review, protocol hoặc kết quả đã lưu.

## 1. Trạng thái và nguồn bằng chứng

[VERIFIED FROM EXPERIMENTS] Chuỗi thực nghiệm bắt đầu lúc **15:49:30**, kết thúc lúc **16:47:42 ngày 26/10/2026**, giờ Việt Nam; thời gian toàn chuỗi khoảng **58,19 phút**. Cả **26/26 subprocess** có status completed và exit code 0. Kiểm tra môi trường/CUDA smoke test thành công; **40/40 tests** đạt. Không còn tiến trình Python của runner tại thời điểm kiểm tra hoàn tất.

[VERIFIED FROM EXPERIMENTS] Kiểm tra tổng kết đối chiếu **15 báo cáo trong comparison.json với 15 metrics.json gốc**, tất cả khớp; **40 checksum source/config** hiện tại khớp protocol_lock.json. Tám mục đối chiếu Phase 2 được lưu trong reproduction_checks.json đều khớp baseline: sáu mảng feature/identity/label/split và hai metadata feature names/label mapping. Dữ liệu tái tạo có **2.096.804 dòng × 84 predictors**, 27 nhãn; test gồm **314.521 dòng**, trong đó 237.380 benign và 77.141 attack.

Nguồn trực tiếp (đường dẫn tương đối từ tài liệu này):

- [Kế hoạch trước training](ROUND1_EXECUTION_PLAN.md).
- [Protocol khóa trước chạy](../../results/research_rounds/round1_20261026_s42/protocol_lock.json) và [trạng thái/lệnh/log/thời gian](../../results/research_rounds/round1_20261026_s42/status.json).
- [Kiểm tra tái tạo dữ liệu](../../results/research_rounds/round1_20261026_s42/reproduction_checks.json).
- [Quyết định chỉ dùng validation](../../results/research_rounds/round1_20261026_s42/selection_validation_only.json).
- [Báo cáo tự động](../../results/research_rounds/round1_20261026_s42/RESEARCH_REPORT.md) và [toàn bộ metric, per-class, confusion matrix](../../results/research_rounds/round1_20261026_s42/comparison.json).

[TECHNICAL INTERPRETATION] Hoàn tất chuỗi và khớp checksum xác nhận khả năng thực thi/tính nhất quán của bản triển khai, không tự xác nhận provenance dữ liệu, tính độc lập thống kê hay tính mới khoa học. Thời gian subprocess gồm I/O, checksum, fit, predict và tính metric; **không phải latency inference**.

## 2. Phương pháp thực sự đã chạy

[VERIFIED FROM IMPLEMENTATION] Raw audit → tái tạo cleaning/full-row dedup và split cố định → scaler per-run → dense AE 84→64→32→16→32→64→84 → Stage 1 binary → Stage 2 attack-only → predicted gate → optional novelty. AE học joint reconstruction, không greedy SAE. Stage 1 có XGBoost/MLP × scaled/latent; p train dùng nested OOF 5 folds với inner fit/stop/calibration 80/10/10 và scaler/AE fold-local. Stage 2 dùng một latent space chung; chỉ scalar p được ghép từ các fold.

[VERIFIED FROM IMPLEMENTATION] Giữ seed 42, Attempted=preserve, split 70/15/15, gate XGB latent cố định 0,5, các ngân sách epoch/tree/batch đã cấu hình. Không tuning theo test. LOACO giữ DDoS, ID 26; fit lại toàn chain với known-only preprocessing; ngưỡng novelty q95 chỉ từ known-attack validation. Đợt này không chạy hai dataset ngoài, không chạy baseline flat multiclass/no-AE Stage 2 hoặc benchmark model-reload inference.

## 3. Stage 1 — kết quả phân loại nhị phân

[VERIFIED FROM EXPERIMENTS] Các số dưới đây ở thang 0–1, không phải phần trăm. Nguồn: `results/stage1/round1_20261026_s42_main/<tag>/metrics.json`; các báo cáo này đã được đối chiếu với comparison.json.

| Cấu hình | Validation F1 | Test F1 | Precision | Recall | FPR | FNR | AUROC | AP | Brier |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| XGB latent | 0,999352 | 0,999313 | 0,999339 | 0,999287 | 0,000215 | 0,000713 | 0,999995 | 0,999986 | 0,000288 |
| XGB scaled | **0,999851** | **0,999857** | 0,999806 | 0,999909 | 0,000063 | 0,000091 | 1,000000* | 1,000000* | 0,000053 |
| MLP scaled | 0,999132 | 0,999086 | 0,998821 | 0,999352 | 0,000383 | 0,000648 | 0,999959 | 0,999890 | 0,000378 |
| MLP latent | 0,997214 | 0,997156 | 0,996492 | 0,997822 | 0,001142 | 0,002178 | 0,999880 | 0,999710 | 0,001160 |

*Làm tròn sáu chữ số không có nghĩa phân loại hoàn hảo: XGB scaled còn **15 false positives và 7 false negatives**. XGB latent có 51 FP và 55 FN. AP là average precision, không đồng nhất với diện tích PR theo quy tắc hình thang.

[TECHNICAL INTERPRETATION] XGB scaled dẫn đầu Stage 1 về validation/test F1 và Brier trong cấu hình, seed, split đã chạy. Với cả XGB và MLP, latent không đem lại cải thiện binary F1 so với scaled features trong đợt này. **Chưa chứng minh AE giúp Stage 1**, nhưng cũng chưa đủ để kết luận AE luôn bất lợi hoặc không cần cho mọi nhiệm vụ.

[VERIFIED FROM IMPLEMENTATION] Gate của Stage 2 ablation vẫn là XGB latent theo kế hoạch; không thay gate sang XGB scaled sau khi xem test. Vì vậy không được gán 15 FP/7 FN của standalone XGB scaled vào các cascade bên dưới.

## 4. Stage 2 và closed-set end-to-end

[VERIFIED FROM EXPERIMENTS] Nguồn: `results/stage2/round1_20261026_s42_main/<variant>/metrics.json` và `results/pipeline/round1_20261026_s42_closed_<variant>/metrics.json`. Stage 2 oracle chỉ đánh giá true attacks; E2E đánh giá toàn test, gồm benign và lỗi gate.

| Biến thể | Val attack macro-F1 | Test attack macro-F1 (oracle) | E2E accuracy | Balanced accuracy | E2E macro-F1 | Weighted-F1 | Tổng lỗi |
|---|---:|---:|---:|---:|---:|---:|---:|
| XGB latent-only | 0,891745 | 0,917161 | 0,995307 | 0,833635 | 0,845273 | 0,995322 | 1.476 |
| XGB latent+p | **0,892170** | 0,917275 | 0,995285 | 0,842691 | 0,843216 | 0,995295 | 1.483 |
| MLP latent-only | 0,742360 | 0,748540 | 0,990188 | 0,811596 | 0,716103 | 0,990337 | 3.086 |
| MLP latent+p | 0,630567 | 0,671336 | 0,982147 | 0,741850 | 0,615989 | 0,982644 | 5.615 |

[VERIFIED FROM EXPERIMENTS] Selector khóa **latent_plus_pattack_xgb** lúc **16:34:28**, trước các bước final closed-set evaluation và LOACO, bằng validation attack macro-F1. Training scripts đã lưu test metrics, nhưng hàm chọn chỉ đọc trường validation; đã có regression test cho quy tắc này. Không đổi lựa chọn vì latent-only có E2E test macro-F1 cao hơn.

| So sánh có đối chứng cùng classifier | Δ validation attack macro-F1 | Δ test E2E macro-F1 | Δ tổng lỗi E2E |
|---|---:|---:|---:|
| XGB latent+p − XGB latent-only | +0,000425 | −0,002057 | +7 |
| MLP latent+p − MLP latent-only | −0,111794 | −0,100114 | +2.529 |

[TECHNICAL INTERPRETATION] Chưa có bằng chứng meta-feature tăng hiệu quả tổng quát hóa: lợi thế validation của XGB+p rất nhỏ và không chuyển thành E2E test macro-F1 tốt hơn; với MLP, cả validation và test đều giảm trong cấu hình này. Negative finding này có giá trị nghiên cứu, nhưng không phải kiểm định ý nghĩa thống kê hoặc bằng chứng p luôn có hại.

[REQUIRES FURTHER VERIFICATION] Không quy kết nguyên nhân giảm của MLP chỉ từ bảng điểm. Cần kiểm phân phối p OOF/final, calibration, thang đo feature và độ nhạy optimization trên validation trong kế hoạch mới. MLP latent-only chạy 43 epoch, MLP+p chạy 25 epoch do early stopping; không sửa checkpoint/threshold hậu nghiệm theo test để làm đẹp kết quả.

### 4.1. Lỗi lan truyền qua gate

[VERIFIED FROM EXPERIMENTS] Cùng gate nên cả bốn cascade có **51 benign qua gate + 55 attack bị chặn**. Lỗi attack đã qua gate nhưng phân loại cuối sai lần lượt là 1.370, 1.377, 2.980 và 5.509. Với ứng viên được chọn: **51 + 55 + 1.377 = 1.483 lỗi**.

[VERIFIED FROM EXPERIMENTS] Hai chiều nhầm lẫn lớn nhất của ứng viên: Portscan → Infiltration - Portscan **779 mẫu** và chiều ngược lại **516 mẫu**. Đây là quan sát confusion matrix, không tự chứng minh hai nhãn phải được gộp; cần giải trình ontology/nguồn nhãn trước mọi thay đổi target.

### 4.2. Accuracy cao nhưng lớp hiếm vẫn yếu

[VERIFIED FROM EXPERIMENTS] Bảng trích từ per-class metrics của **cascade được chọn**; số gate-blocked được đếm lại từ `test_predictions.csv.gz`, không chỉ suy từ F1.

| Nhãn | Test support | F1 XGB latent-only | F1 XGB latent+p | Attack bị gate chặn (ứng viên) |
|---|---:|---:|---:|---:|
| SSH-Patator - Attempted | 4 | 0,857143 | 0,500000 | 1 |
| Heartbleed | 2 | 0,500000 | 0,800000 | 0 |
| Infiltration | 5 | 0,333333 | 0,333333 | 4 |
| Web Attack - XSS - Attempted | 98 | 0,682028 | 0,678899 | 7 |
| Web Attack - SQL Injection - Attempted | 1 | 0 | 0 | 1 |
| Web Attack - SQL Injection | 2 | 0 | 0 | 2 |

[VERIFIED FROM EXPERIMENTS] Stage 2 oracle của ứng viên phân loại đúng cả hai mẫu SQL Injection (F1=1 trên subset oracle), nhưng gate chặn cả hai nên F1 cuối bằng 0. Ba mẫu của hai nhãn SQL Injection đều bị gate chặn. Infiltration có 4/5 mẫu bị chặn.

[TECHNICAL INTERPRETATION] Đây là bằng chứng cụ thể cho việc không dùng standalone Stage 2 để thay thế đánh giá hệ thống. Macro-F1 rất nhạy với lớp support 1–5; F1=1 ở lớp 1–3 mẫu cũng không chứng minh độ bền vững.

[VERIFIED FROM EXPERIMENTS] `stage2_admitted_known_attack_metrics` của ứng viên có macro-F1 **0,962051**, nhưng chỉ trên **77.086 attack qua gate và 24 class IDs**, thiếu hai lớp SQL Injection. Oracle xét **77.141 attack/26 classes**, E2E xét **314.521 flow/27 classes**. Không so ba macro-F1 này như cùng một population/class universe. Báo cáo này giữ nguyên JSON gốc và chỉ làm rõ mẫu số.

## 5. LOACO DDoS — unknown sau predicted gate

[VERIFIED FROM EXPERIMENTS] Toàn chain được fit lại cho `round1_20261026_s42_loaco26`, với Stage 2 XGB latent+p đã chọn từ main validation. Test có **14.272 unknown DDoS**, **62.869 known attacks** và 237.380 benign. Ngưỡng từng detector lấy từ known-attack validation, không từ unknown test. Nguồn: `results/pipeline/round1_20261026_s42_open_<method>/metrics.json`.

| Method | Unknown phát hiện | Precision | Recall | F1 | Known attack false rejection | Benign → unknown | E2E macro-F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Maximum class probability | 3.541 | 0,535785 | 0,248108 | 0,339160 | 0,048545 | 16 | 0,791559 |
| One-Class SVM | 560 | 0,152838 | 0,039238 | 0,062444 | 0,049166 | 13 | 0,627171 |
| Isolation Forest | 358 | 0,102198 | 0,025084 | 0,040281 | 0,049691 | 21 | 0,571738 |

[VERIFIED FROM EXPERIMENTS] Cả ba cùng mất **209 unknown tại gate**. MCP còn từ chối nhầm **3.052 known attacks**; tổng unknown không phát hiện là **10.731/14.272**. Precision cuối đã tính cả benign bị gán UNKNOWN. Không được trình bày score-only recall của MCP **0,253924** như final recall **0,248108**.

[VERIFIED FROM EXPERIMENTS] Để giữ đủ metric hệ thống: E2E accuracy/balanced accuracy/weighted-F1 lần lượt là MCP **0,954547/0,807370/0,950133**; OCSVM **0,942039/0,641079/0,932412**; IF **0,941285/0,579682/0,930456**. Per-class/confusion matrix đầy đủ nằm trong comparison.json.

[TECHNICAL INTERPRETATION] MCP cho kết quả tốt nhất trong ba phương pháp **trên heldout DDoS và operating point này**, nhưng recall khoảng **24,81%** vẫn thấp; không thể gọi là phát hiện zero-day hiệu quả trong thực tế. Đây là so sánh kết quả test đã quy định, không phải giấy phép chọn detector cuối bằng unknown test.

[VERIFIED FROM EXPERIMENTS] Score-only AUROC: MCP **0,885415**, OCSVM **0,210445**, IF **0,783619**. IF có AUROC cao hơn OCSVM nhưng recall cuối tại ngưỡng đã khóa thấp hơn. [TECHNICAL INTERPRETATION] Xếp hạng toàn đường cong không thay cho đánh giá operating point. Không đảo chiều score OCSVM hoặc chọn lại ngưỡng dựa vào DDoS test để nâng điểm.

[TECHNICAL INTERPRETATION] “Strict LOACO” ở đây chỉ nghĩa heldout bị loại khỏi các thao tác fit theo protocol sửa; không đồng nghĩa toàn bộ benchmark không leakage. Không diễn giải chênh với LOACO lịch sử như chỉ sửa scaler: encoder, OOF/calibration và biến thể Stage 2 cũng khác.

## 6. Kết luận về hiệu quả và tính mới

- [VERIFIED FROM EXPERIMENTS] Đã chạy thành công pipeline thực nghiệm từ raw CSV tới final predictions, gồm đối chứng Stage 1, Stage 2 và một LOACO; xác nhận khả năng thực thi của revised_v1 trên máy hiện tại.
- [VERIFIED FROM EXPERIMENTS] XGB scaled là cấu hình binary mạnh nhất trong đợt này; meta-feature không đem lại cải thiện E2E nhất quán; lỗi gate gây mất toàn bộ mẫu của một số nhãn hiếm; MCP tốt hơn OCSVM/IF trên heldout DDoS tại ngưỡng đã khóa.
- [TECHNICAL INTERPRETATION] Các kết quả âm và phân tích lan truyền lỗi là bằng chứng hữu ích để định hình câu hỏi nghiên cứu. **Chưa chứng minh lợi ích AE, ưu thế tổng quát của meta-feature hoặc tính mới thuật toán.** Việc ghép AE/XGB/MLP và sửa leakage là đóng góp triển khai/phương pháp kiểm chứng, không tự tạo novelty khoa học.
- [REQUIRES FURTHER VERIFICATION] Cần đối chiếu tài liệu và các công trình nền trong review, đối chứng thích hợp và kiểm định/độ bất định trước khi viết tuyên bố đóng góp mới. Báo cáo này không thêm tài liệu tham khảo chưa kiểm chứng.

## 7. Pipeline ứng viên và thứ tự nghiên cứu tiếp theo

[VERIFIED FROM EXPERIMENTS] **Ứng viên được chọn đúng quy tắc trước chạy:** StandardScaler → dense AE → Stage 1 XGB latent + calibration → gate 0,5 → Stage 2 XGB `[z,p_attack]`; training p bằng nested OOF. Giữ XGB latent-only làm đối chứng bắt buộc. MCP là detector có kết quả LOACO DDoS tốt nhất đã quan sát, **chưa khóa làm detector tổng quát**. Không tự thay gate bằng XGB scaled trong run đã kết thúc.

[TECHNICAL INTERPRETATION] Ứng viên này là mốc thực nghiệm có thể tái lập để phát triển tiếp, chưa phải chuẩn khoa học cuối. Ưu tiên theo thứ tự:

1. **Chốt tính hợp lệ dữ liệu:** xác minh upstream release/Attempted, định nghĩa target và đơn vị độc lập; duyệt group/session/time split cùng cách xử lý lớp hiếm. Không sửa nhãn hoặc xóa test duplicates hậu nghiệm để nâng metric.
2. **Chốt thiết kế ablation mới trước test:** đánh giá gate XGB scaled dựa trên bằng chứng validation, đối chứng no-AE/flat multiclass nếu giữ luận điểm lợi ích kiến trúc; so latent-only/+p trong cùng họ classifier và ngân sách. Nếu đổi gate sinh p thì phải tạo OOF và refit Stage 2 tương ứng, không tráo artifact.
3. **Kiểm độ ổn định và calibration:** multi-seed, per-class support, CI cho macro-F1 theo đơn vị độc lập phù hợp; đo calibration/score shift và operating point trên validation. IID accuracy bootstrap hiện có không đủ để tuyên bố significance của Δ macro-F1 rất nhỏ.
4. **Mở rộng open-set theo kế hoạch duyệt:** nhiều heldout đủ support, fit lại toàn chain, báo final unknown lẫn known/benign false rejection; không dùng unknown test để chọn detector/threshold. Có tập đánh giá độc lập chưa sử dụng nếu khả thi.
5. **Sau đó đối chiếu hai dataset ngoài:** xác minh features/units/extractor/label ontology, cố định target và protocol. Tách rõ retrain riêng từng dataset với train-source/test-target không retrain; không zero-fill cho đủ 84 cột. Hoàn thiện frozen raw-to-final inference và benchmark tài nguyên trước claim hệ thống thực tế.

[REQUIRES FURTHER VERIFICATION] Các rủi ro chưa biến mất sau đợt chạy: feature-vector overlap qua split; test lịch sử và test đợt 1 đã xem; nguồn/Attempted chưa chốt; support hiếm; một seed/một heldout; thiếu flat/no-AE Stage 2, external experiments và latency thực. Không chạy thêm hoặc thay protocol trong lượt tổng kết này.

## 8. Lưu vết sau tổng kết

[VERIFIED FROM IMPLEMENTATION] Chỉ tạo tài liệu tổng kết này; không sửa source/config đã khóa, không sửa/xóa model hoặc kết quả, không tự rerun và không push Git. Toàn bộ bảng được trích từ artifacts đợt 1 và đối chiếu read-only. Việc theo dõi định kỳ kết thúc khi chuỗi đã hoàn tất; trạng thái automation được thông báo riêng trong chat.
