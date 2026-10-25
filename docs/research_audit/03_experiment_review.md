# 03 — Kiểm kê thí nghiệm và độ tin cậy kết quả

Audit 24/10/2026, root duy nhất D:\CAO HOC\IDS System, commit 895cc8b.
Các số dưới đây dùng thang 0–1, làm tròn 6 chữ số, trừ số mẫu/ngưỡng/MSE ghi riêng. Không dùng kết quả chưa tồn tại. Những số “tính lại trong audit” là phép tính trên prediction có sẵn, không phải thí nghiệm training mới.

## 1. Inventory và điều kiện so sánh

Dataset của mọi experiment: cùng 5 daily CSV local thuộc họ CICIDS2017; provenance phiên bản chưa chốt. Cùng Phase2 split seed42: train1.467.762, validation314.521, test314.521. Main Stage 2 train359.987 attack, validation/test77.141 attack. LOACO-26 có known train attack293.387, known validation/test62.869, unknown test14.272. Không so trực tiếp các mẫu số này như một benchmark đồng nhất.

| Experiment ID / nhóm | Model, features | Split/chức năng | Artifact | Xác minh |
|---|---|---|---|---|
| AE main | Dense AE 84→16 | Main train; validation reconstruction | [artifacts/metadata/autoencoder/main/run.json](<D:/CAO HOC/IDS System/artifacts/metadata/autoencoder/main/run.json>) | Checkpoint/history/latent có; không replay model |
| AE loaco_26 | Dense AE 84→16 | Bỏ26 khỏi AE fit; scaler chung | [artifacts/metadata/autoencoder/loaco_26/run.json](<D:/CAO HOC/IDS System/artifacts/metadata/autoencoder/loaco_26/run.json>) | Có artifact; protocol chưa sạch |
| S1 main/xgboost_scaled | XGB,84 | Binary,5-fold OOF + final | [results/stage1/main/xgboost_scaled/metrics.json](<D:/CAO HOC/IDS System/results/stage1/main/xgboost_scaled/metrics.json>) | Test metric tính lại khớp |
| S1 main/xgboost_latent | XGB,16 | Binary,5-fold OOF + final | [results/stage1/main/xgboost_latent/metrics.json](<D:/CAO HOC/IDS System/results/stage1/main/xgboost_latent/metrics.json>) | Test metric tính lại khớp |
| S1 main/mlp_scaled | MLP,84 | Binary,5-fold OOF + final | [results/stage1/main/mlp_scaled/metrics.json](<D:/CAO HOC/IDS System/results/stage1/main/mlp_scaled/metrics.json>) | Test metric tính lại khớp |
| S1 main/mlp_latent | MLP,16 | Binary,5-fold OOF + final | [results/stage1/main/mlp_latent/metrics.json](<D:/CAO HOC/IDS System/results/stage1/main/mlp_latent/metrics.json>) | Test metric tính lại khớp |
| S1 loaco_26/xgboost_latent | XGB,16 | Known-only fit, test gồm unknown | [results/stage1/loaco_26/xgboost_latent/metrics.json](<D:/CAO HOC/IDS System/results/stage1/loaco_26/xgboost_latent/metrics.json>) | Metric khớp; scaler hạn chế |
| S2 main/latent_only | XGB,16 | 26 lớp attack | [results/stage2/main/latent_only/metrics.json](<D:/CAO HOC/IDS System/results/stage2/main/latent_only/metrics.json>) | Index, probabilities, metric khớp |
| S2 main/latent_plus_pattack_xgb | XGB,17 | 26 lớp; scalar meta-feature | [results/stage2/main/latent_plus_pattack_xgb/metrics.json](<D:/CAO HOC/IDS System/results/stage2/main/latent_plus_pattack_xgb/metrics.json>) | Có sử dụng P_attack thật |
| S2 main/latent_plus_pattack_mlp | MLP,17 | 26 lớp; scalar meta-feature | [results/stage2/main/latent_plus_pattack_mlp/metrics.json](<D:/CAO HOC/IDS System/results/stage2/main/latent_plus_pattack_mlp/metrics.json>) | Có sử dụng P_attack thật |
| S2 loaco_26/latent_only | XGB,16 | 25 lớp known | [results/stage2/loaco_26/latent_only/metrics.json](<D:/CAO HOC/IDS System/results/stage2/loaco_26/latent_only/metrics.json>) | Không có ID26 trong class_ids |
| N loaco_26/max_probability | 1-maxp từ S2 | Unknown vs known attack; q95 known-val | [results/novelty/loaco_26/heldout_26/metrics.json](<D:/CAO HOC/IDS System/results/novelty/loaco_26/heldout_26/metrics.json>) | Tính lại metric/ngưỡng khớp |
| N loaco_26/one_class_svm | RBF OCSVM,latent | Known-attack fit, cap20.000 | Cùng novelty metrics; model.joblib | Metric khớp đến sai số lưu float32 |
| N loaco_26/isolation_forest | IF,latent | Known-attack fit,cap100.000,n_estimators300 | Cùng novelty metrics; model.joblib | Metric khớp đến sai số lưu float32 |
| P eval_main_latent_only | S1 XGB latent + S2 latent | Closed-set, toàn314.521 test | [results/pipeline/eval_main_latent_only/metrics.json](<D:/CAO HOC/IDS System/results/pipeline/eval_main_latent_only/metrics.json>) | CSV hash/labels/recompose/metric khớp |
| P eval_main_pattack_xgb | Cùng S1 + S2 latent+p XGB | Closed-set, cùng test | [results/pipeline/eval_main_pattack_xgb/metrics.json](<D:/CAO HOC/IDS System/results/pipeline/eval_main_pattack_xgb/metrics.json>) | Như trên |
| P eval_main_pattack_mlp | Cùng S1 + S2 latent+p MLP | Closed-set, cùng test | [results/pipeline/eval_main_pattack_mlp/metrics.json](<D:/CAO HOC/IDS System/results/pipeline/eval_main_pattack_mlp/metrics.json>) | Như trên |
| P loaco_26 | S1/S2 LOACO + maxprob | Open-set, toàn test | [results/pipeline/loaco_26/metrics.json](<D:/CAO HOC/IDS System/results/pipeline/loaco_26/metrics.json>) | Final metric khớp; isolated unknown metric cần tách |

Có 18 mục thực nghiệm/chức năng trong inventory; không phải 18 independent training repetitions. Maxprob không có fit model riêng. Các pipeline tái sử dụng artifacts upstream. Metadata sao chép metrics không được đếm thành run bổ sung.

## 2. Autoencoder

| Run | N train | N validation | Best epoch / số epoch | Best validation MSE | Latent |
|---|---:|---:|---:|---:|---|
| main | 1467762 | 314521 | 100 / 100 | 0.0584128613 | 2096804 ×16,float32 |
| loaco_26 | 1401162 | 300249 | 99 / 100 | 0.0523065002 | 2096804 ×16,float32 |

Mảng latent hữu hạn trong kiểm tra snapshot. Loss không cùng population, không dùng để kết luận LOACO encoder tốt hơn. elapsed_seconds=0.0 là trường chưa được ghi đo, không phải huấn luyện không mất thời gian. Chưa benchmark tái dựng model từ checkpoint.

## 3. Stage 1 — binary

| Run/model | Accuracy | Balanced acc | Precision | Recall/DR | F1 | AUROC | AP (key pr_auc) |
|---|---:|---:|---:|---:|---:|---:|---:|
| loaco_26/xgboost_latent | 0.998283 | 0.996837 | 0.998997 | 0.993998 | 0.996491 | 0.999986 | 0.999959 |
| main/mlp_latent | 0.998690 | 0.998301 | 0.997123 | 0.997537 | 0.997330 | 0.999902 | 0.999734 |
| main/mlp_scaled | 0.999695 | 0.999570 | 0.999430 | 0.999326 | 0.999378 | 0.999959 | 0.999844 |
| main/xgboost_latent | 0.999676 | 0.999518 | 0.999468 | 0.999209 | 0.999339 | 0.999995 | 0.999986 |
| main/xgboost_scaled | 0.999930 | 0.999923 | 0.999806 | 0.999909 | 0.999857 | 1.000000 | 1.000000 |

| Run/model | Val F1 | TN | FP | FN | TP | FPR=FP/(TN+FP) | FNR=FN/(FN+TP) |
|---|---:|---:|---:|---:|---:|---:|---:|
| loaco_26/xgboost_latent | 0.998640 | 237303 | 77 | 463 | 76678 | 0.000324 | 0.006002 |
| main/mlp_latent | 0.997167 | 237158 | 222 | 190 | 76951 | 0.000935 | 0.002463 |
| main/mlp_scaled | 0.999319 | 237336 | 44 | 52 | 77089 | 0.000185 | 0.000674 |
| main/xgboost_latent | 0.999222 | 237339 | 41 | 61 | 77080 | 0.000173 | 0.000791 |
| main/xgboost_scaled | 0.999844 | 237365 | 15 | 7 | 77134 | 0.000063 | 0.000091 |

Ngưỡng tất cả0,5. Binary test có237.380 benign +77.141 attack, kể cả LOACO. Với LOACO, validation không chứa DDoS nên không có cùng population với test.

Diễn giải: raw-scaled XGBoost có FP15/FN7, tốt hơn latent XGBoost FP41/FN61 trên split này; raw-scaled MLP cũng tốt hơn latent MLP ở binary F1. Không được tuyên bố latent luôn tăng hiệu quả. Không được từ một seed và cấu hình duy nhất suy ra XGBoost luôn hơn MLP; cũng chưa có latency để chứng minh trade-off tốc độ.

Các main pipeline đã có vẫn dùng Stage 1 XGB latent, không tự động là cấu hình Stage 1 tốt nhất trong bảng. Thay gate sang XGB scaled sau khi đã xem test sẽ là thay protocol hậu nghiệm nếu không chạy evaluation mới được quản lý.

## 4. Stage 2 — oracle known-attack subset

| Run/experiment | Val Macro-F1 | Test accuracy | Test balanced acc | Test Macro-F1 | Test weighted-F1 |
|---|---:|---:|---:|---:|---:|
| loaco_26/latent_only | 0.867050 | 0.977334 | 0.880604 | 0.890117 | 0.977464 |
| main/latent_only | 0.880938 | 0.981851 | 0.913968 | 0.902392 | 0.981961 |
| main/latent_plus_pattack_mlp | 0.731635 | 0.939578 | 0.907199 | 0.757557 | 0.942203 |
| main/latent_plus_pattack_xgb | 0.858131 | 0.981825 | 0.929167 | 0.910874 | 0.981922 |

Class_ids main =1..26, LOACO=1..25; probability file chứa mọi314.521 test rows để pipeline sử dụng. Metric trên bảng chỉ tính known attack rows. Sự hiện diện của probabilities cho benign không có nghĩa Stage 2 được train benign.

Latent-only có validation Macro-F1 cao nhất trong ba main experiments. Latent+p XGB có test Macro-F1 cao hơn, nhưng validation thấp hơn. Do đó lựa chọn theo validation vẫn là latent-only trong phạm vi ablation này; không được dùng test để đảo lựa chọn hoặc kết luận meta-feature chắc chắn cải thiện.

Thiếu MLP latent-only nên chưa tách được hiệu ứng “đổi classifier” và “thêm meta-feature” đối với MLP. So sánh latent-only XGB vs latent+p XGB mới giữ nguyên model family. Hai meta-feature run đều dùng P_attack của main/stage1_xgboost_latent, không phải P_attack của MLP.

## 5. End-to-end

| Pipeline | Accuracy | Balanced acc | Macro-F1 | Weighted-F1 | FP benign / FN attack / wrong attack sau gate |
|---|---:|---:|---:|---:|---|
| eval_main_latent_only | 0.995298 | 0.830134 | 0.840758 | 0.995308 | 41 / 61 / 1377 |
| eval_main_pattack_xgb | 0.995285 | 0.829956 | 0.837458 | 0.995292 | 41 / 61 / 1381 |
| eval_main_pattack_mlp | 0.984958 | 0.809420 | 0.734622 | 0.985591 | 41 / 61 / 4629 |
| loaco_26 | 0.954331 | 0.812768 | 0.793589 | 0.955034 | 77 / 463 / 13824 |

Main latent-only: tổng1.479 lỗi; pattack-XGB1.483; pattack-MLP4.731. Chênh lệch4 lỗi giữa hai XGB không phải bằng chứng có ý nghĩa thống kê.

Accuracy95% CI đã lưu, bootstrap IID1.000 lần (không tính lại trong audit):

| Pipeline | CI đã lưu |
|---|---|
| eval_main_latent_only | [0.9950623512,0.9955201745] |
| eval_main_pattack_xgb | [0.9950654313,0.9955106378] |
| eval_main_pattack_mlp | [0.9845320582,0.9853684098] |
| loaco_26 | [0.9535864979,0.9550460175] |

CI này chỉ mô tả resampling rows với predictions cố định; không phản ánh variation do train seed hay dependence giữa flow/session. Không kết luận hai model khác biệt từ hai CI chồng lấp/không chồng lấp; cần paired difference phù hợp và cluster unit nếu có.

### 5.1 Lớp hiếm bị accuracy che lấp

Tính từ predictions/probabilities đã lưu của main latent-only:

| Nhãn | N test | Stage 2 oracle F1 | End-to-end F1 | End-to-end recall |
|---|---:|---:|---:|---:|
| Infiltration | 5 | 0.750000 | 0.000000 | 0.000000 |
| Web Attack - SQL Injection | 2 | 0.666667 | 0.000000 | 0.000000 |
| Web Attack - SQL Injection - Attempted | 1 | 0.000000 | 0.000000 | 0.000000 |
| SSH-Patator - Attempted | 4 | 0.750000 | 0.666667 | 0.500000 |
| Infiltration - Attempted | 7 | 0.933333 | 0.727273 | 0.571429 |
| Web Attack - XSS - Attempted | 98 | 0.693333 | 0.678571 | 0.775510 |

Mức accuracy = 0,995298 và weighted-F1 = 0,995308 không loại trừ việc bỏ sót hoàn toàn một số lớp. Chênh lệch oracle/end-to-end thể hiện gate có thể làm mất lợi ích phân lớp của Stage 2. Không tự động quy mọi giảm F1 cho gate FN vì false-positive phân bổ giữa lớp cũng ảnh hưởng precision.

## 6. LOACO-26 novelty và final unknown

Nguồn: [results/novelty/loaco_26/heldout_26/metrics.json](<D:/CAO HOC/IDS System/results/novelty/loaco_26/heldout_26/metrics.json>); threshold file theo method trong [artifacts/thresholds/loaco_26/heldout_26](<D:/CAO HOC/IDS System/artifacts/thresholds/loaco_26/heldout_26>). Các số sau là novelty score-only trên77.141 TRUE ATTACK rows, trong đó14.272 unknown; không có benign/gate trong mẫu số.

| Method | Threshold | Unknown recall | Unknown F1 | Known rejection | AUROC | AP |
|---|---:|---:|---:|---:|---:|---:|
| max_probability | 0.173024 | 0.260650 | 0.352690 | 0.049357 | 0.785392 | 0.466447 |
| one_class_svm | -7.327475 | 0.118694 | 0.177689 | 0.049325 | 0.548214 | 0.221639 |
| isolation_forest | 0.372567 | 0.030199 | 0.048283 | 0.050104 | 0.850716 | 0.396175 |

Ở operating point đặt theo q95 known-validation, maxprob có recall tốt hơn IF/OCSVM cho DDoS trong run này; IF có AUROC cao nhất nhưng recall rất thấp tại threshold đã chọn. Ranking toàn đường cong không đảm bảo tốt tại một mức false rejection. Đây là quan sát exploratory, không phải kết quả chọn method trên test được dùng như xác nhận độc lập.

Tính lại từ final predictions trong [results/pipeline/loaco_26/test_predictions.csv.gz](<D:/CAO HOC/IDS System/results/pipeline/loaco_26/test_predictions.csv.gz>):

| Đại lượng | Giá trị | Mẫu số/ý nghĩa |
|---|---:|---|
| Unknown đúng cuối pipeline | 3528 | ID26 thật được final=-1 |
| Unknown recall cuối pipeline | 0.247197 | 3528/14272 |
| Unknown precision trên toàn test | 0.532207 | False unknown gồm known attacks và benign |
| Unknown F1 trên toàn test | 0.337592 | Từ final=-1 trên mọi test |
| Unknown bị Stage 1 chặn | 372 | Bị gán BENIGN trước novelty |
| Benign bị gán UNKNOWN | 14 | False unknown từ benign |

Phải phân biệt với score-only recall = 0,260650/F1 = 0,352690. Script06 hiện đặt score-only vào trường open_set_metrics khiến người đọc dễ hiểu sai. End_to_end_metrics của cùng file vẫn tính đúng final class labels.

Đây chưa phải kết quả strict LOACO hợp lệ vì scaler tiếp xúc unknown train. Không diễn giải “phát hiện zero-day đạt26,07%” không kèm điều kiện. Chưa có pipeline final artifact cho IF và OCSVM; không bịa số end-to-end của hai phương pháp.

## 7. Kiểm chứng số liệu và bất nhất

- Test metrics5 Stage 1,4 Stage 2 và4 pipeline khớp số thực lưu trong JSON khi tính lại.
- Tái ghép P_attack + Stage 2 + novelty cho4 pipeline khớp từng predicted label trong CSV; row_hash và true_label đều khớp Phase2 test.
- Validation Stage 2 được kiểm tra lại trong audit snapshot ban đầu tại cùng commit; index và metric khớp. Trong lượt xác nhận root mới, validation table đọc từ artifact, test được tính lại.
- Maxprob q95 đúng tuyệt đối. OCSVM q95 từ score float32 lệch2,777e-5, IF lệch1,435e-8 so threshold lưu ở độ chính xác cao hơn; AP lệch tối đa khoảng1,07e-7. Source cast score sang float32 khi ghi; không nên diễn giải sai số này như leakage.
- Requirement thực tế xgboost==3.2.0 và môi trường3.2.0, trong khi guide nói3.4.2. Đây là documentation drift, không bằng chứng package cài sai.
- PHASE_2_REPORT là lịch sử giai đoạn, không chứng minh current chưa train. TRAINING_GUIDE checklist cũ chưa phản ánh4 pipeline/LOACO đã có.
- Chưa có complete config snapshot/commit/env hash kèm từng model; metadata hiện tại không chứng minh package nào được dùng lúc train.
- Chưa đo train time, peak VRAM/RAM, throughput, p50/p95 latency; mọi khẳng định tối ưu/real-time đều chưa đủ bằng chứng.
- Audit không chạy lại training hoặc model forward, nên “metric tái tính được” không đồng nghĩa “model checkpoint đã tái sinh cùng prediction”.

## 8. Baseline và thí nghiệm còn thiếu

| Câu hỏi nghiên cứu | Đã có | Thiếu để kết luận |
|---|---|---|
| AE có lợi? | Stage 1 84 vs16 | Raw/scaled Stage 2 và cascade, latency, nén-vs-hiệu quả |
| Cascade hơn single-stage? | 3 cascade | Single-stage multiclass gồm BENIGN, cùng schema/split/budget |
| P_attack có lợi? | XGB latent vs latent+p | OOF sạch, multiple seeds; MLP latent-only |
| Calibration cần? | Platt fitted | Uncalibrated control, Brier/ECE/reliability trên validation |
| Gate chọn ra sao? | Threshold cố định0,5 | Validation threshold sweep theo FPR budget, khóa trước test |
| Mất cân bằng đã giải quyết? | Weights + một vài kết quả | Per-class CI/support, audit labels, repeated splits không leakage |
| Unknown generalization? | DDoS heldout | Scaler sạch + nhiều heldout eligible, aggregate theo class |
| Hiệu quả tính toán? | CUDA/AMP config | Benchmark thống nhất có synchronize/warmup, tính cả AE |
| Cross-dataset? | Mục tiêu | Schema/unit/label mapping và run độc lập thứ hai |

Không cần thêm model phức tạp trước khi giải quyết correctness. Thí nghiệm sửa protocol phải dùng run-id mới, không ghi đè main/loaco_26; dữ liệu test cũ đã được xem nên ghi rõ exploratory và quản lý confirmatory evaluation mới.

## 9. Phụ lục — mã kiểm tra read-only đã chạy tại đúng root

Chạy từ PowerShell trong D:\CAO HOC\IDS System bằng interpreter .venv\Scripts\python.exe với -B. Đoạn Python dưới được truyền qua -c trong RAM; không ghi script vào project. Nó chỉ đọc artifact và tính metric; không import trainer để fit, không gọi model inference. Unit tests chạy riêng bằng “.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v”, kết quả16/16 PASS.

Có thể gán đoạn dưới vào biến PowerShell auditCode kiểu here-string, rồi gọi “& .\.venv\Scripts\python.exe -B -c $auditCode”; kiểm tra $LASTEXITCODE. Không chạy các training scripts để tái tính audit.

```python
import sys,json,hashlib,importlib.metadata as im
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.metrics import classification_report,precision_score,recall_score,f1_score
R=Path.cwd()
assert str(R)==r'D:\CAO HOC\IDS System'
sys.path.insert(0,str(R))
sys.stdout.reconfigure(encoding='utf-8')
from src.preprocessing import load_scaler
from src.metrics import binary_metrics,multiclass_metrics,open_set_metrics
from src.evaluation import compose_pipeline_predictions
def out(k,v): print(json.dumps({'section':k,'value':v},ensure_ascii=False,default=lambda x:x.item() if isinstance(x,np.generic) else x.tolist()),flush=True)
def j(p): return json.loads((R/p).read_text(encoding='utf-8'))
def a(p): return np.load(R/p,mmap_mode='r',allow_pickle=False)
y=a('data/processed/attack_label_ids.npy'); b=a('data/processed/binary_labels.npy'); s=a('data/processed/split_ids.npy'); h=a('data/processed/row_hashes.npy'); x=a('data/processed/features_raw.npy'); xs=a('data/processed/features_scaled.npy')
ix=[np.flatnonzero(s==i) for i in range(3)]
out('scope',{'cwd':str(R),'python':sys.version,'packages':{p:im.version(p) for p in ['numpy','pandas','scikit-learn','torch','xgboost','joblib']}})
out('data',{'shape':x.shape,'split_counts':[len(i) for i in ix],'binary_match':np.array_equal(b,y!=0),'unique_row_hash':len(np.unique(h)),'labels':j('artifacts/metadata/label_mapping.json'),'distribution':{str(c):[int((y[i]==c).sum()) for i in ix] for c in np.unique(y)}})
manifest=[]
for e in j('artifacts/metadata/raw_manifest.json'):
 p=R/'CICIDS2017'/e['file'];d=hashlib.sha256()
 with p.open('rb') as f:
  while z:=f.read(8388608): d.update(z)
 manifest.append({'file':p.name,'sha256_matches':d.hexdigest()==e['sha256']})
out('manifest',manifest)
sc=load_scaler(R/'artifacts/preprocessors/scaler.joblib')
su=np.zeros(84); kn=np.zeros(84); count=0; fh=np.empty(len(x),dtype='uint64');nf=[0,0]
for start in range(0,len(x),100000):
 stop=min(start+100000,len(x));z=x[start:stop];mask=s[start:stop]==0;known=mask&(y[start:stop]!=26)
 su+=z[mask].sum(axis=0,dtype='float64');kn+=z[known].sum(axis=0,dtype='float64');count+=int(known.sum())
 fh[start:stop]=pd.util.hash_pandas_object(pd.DataFrame(z),index=False).to_numpy()
 nf[0]+=int((~np.isfinite(z)).sum());nf[1]+=int((~np.isfinite(xs[start:stop])).sum())
sample=np.arange(0,len(x),997)
out('scaler',{'n':sc.n_samples_seen_,'known_without26':count,'heldout_train':int(((y==26)&(s==0)).sum()),'mean_diff':float(abs(su/len(ix[0])-sc.mean_).max()),'known_mean_shift_max_in_sd':float(abs((kn/count-sc.mean_)/sc.scale_).max()),'sample_transform_diff':float(abs(sc.transform(x[sample])-xs[sample]).max()),'nonfinite_raw_scaled':nf})
order=ix[0][np.argsort(fh[ix[0]])];th=fh[order]
for name,i in zip(['val','test'],ix[1:]):
 p=np.searchsorted(th,fh[i]);valid=p<len(th);p=np.minimum(p,len(th)-1);valid&=th[p]==fh[i]
 cand=i[valid];partner=order[p[valid]];eq=np.all(x[cand]==x[partner],axis=1)
 out('feature_overlap',{'split':name,'exact_rows':int(eq.sum()),'cross_label_pairs':int((y[cand[eq]]!=y[partner[eq]]).sum())})
for path in sorted((R/'results/stage1').rglob('metrics.json')):
 m=json.loads(path.read_text(encoding='utf-8'));p=a(f'data/processed/experiments/{m["run_id"]}/stage1_{m["model"]}_{m["representation"]}_p_attack_all.npy')
 calc=binary_metrics(b[ix[2]],p[ix[2]])
 out('stage1',{'path':str(path.relative_to(R)),'test':calc,'validation':m['validation_metrics'],'matches':calc==m['test_metrics']})
for path in sorted((R/'results/stage2').rglob('metrics.json')):
 d=path.parent;m=json.loads(path.read_text(encoding='utf-8'));p=np.load(d/'test_probabilities.npy',mmap_mode='r');ti=np.load(d/'test_indices.npy');c=np.load(d/'class_ids.npy');mask=y[ti]!=0
 if m['held_out_label_id'] is not None: mask&=y[ti]!=m['held_out_label_id']
 calc=multiclass_metrics(y[ti][mask],c[p.argmax(axis=1)][mask])
 out('stage2',{'path':str(path.relative_to(R)),'test':calc,'validation':m['validation_metrics'],'matches':calc==m['known_test_metrics'],'index_match':np.array_equal(ti,ix[2]),'shape':p.shape,'nonfinite':int((~np.isfinite(p)).sum()),'row_sum_error':float(abs(p.sum(1)-1).max())})
for name,run,exp in [('eval_main_latent_only','main','latent_only'),('eval_main_pattack_xgb','main','latent_plus_pattack_xgb'),('eval_main_pattack_mlp','main','latent_plus_pattack_mlp'),('loaco_26','loaco_26','latent_only')]:
 d=R/'results/pipeline'/name;m=json.loads((d/'metrics.json').read_text(encoding='utf-8'));f=pd.read_csv(d/'test_predictions.csv.gz',dtype={'row_hash':'uint64'});p=a(f'data/processed/experiments/{run}/stage1_xgboost_latent_p_attack_all.npy');pro=a(f'results/stage2/{run}/{exp}/test_probabilities.npy');c=a(f'results/stage2/{run}/{exp}/class_ids.npy')
 scores=a('results/novelty/loaco_26/heldout_26/max_probability_test_scores.npy') if run=='loaco_26' else None
 pred=compose_pipeline_predictions(p[ix[2]],pro,c,scores,m['novelty_threshold'],m['stage1_threshold']);calc=multiclass_metrics(f.evaluation_label_id,pred);truth=y[ix[2]];gate=p[ix[2]]>=m['stage1_threshold']
 v={'name':name,'metrics':calc,'metrics_match':calc==m['end_to_end_metrics'],'recompose_matches_csv':np.array_equal(pred,f.predicted_label_id),'hash_match':np.array_equal(h[ix[2]],f.row_hash),'truth_match':np.array_equal(truth,f.true_label_id),'benign_gate':int(((truth==0)&gate).sum()),'missed_attack':int(((truth!=0)&~gate).sum()),'passed_attack_wrong':int(((truth!=0)&gate&(pred!=f.evaluation_label_id.to_numpy())).sum())}
 if run=='loaco_26':
  u=truth==26;det=pred==-1;v['unknown_final']={'precision':precision_score(u,det),'recall':recall_score(u,det),'f1':f1_score(u,det),'detected':int((u&det).sum()),'unknown_missed_gate':int((u&~gate).sum()),'benign_unknown':int(((truth==0)&det).sum())}
 out('pipeline',v)
for method,saved in j('results/novelty/loaco_26/heldout_26/metrics.json')['metrics'].items():
 th=j(f'artifacts/thresholds/loaco_26/heldout_26/{method}.json');v=a(f'results/novelty/loaco_26/heldout_26/{method}_validation_scores.npy');t=a(f'results/novelty/loaco_26/heldout_26/{method}_test_scores.npy');mask=y[ix[2]]!=0
 out('novelty',{'method':method,'threshold':th,'q95':float(np.quantile(v,.95)),'computed':open_set_metrics(y[ix[2]][mask]==26,t[mask],th['threshold']),'saved':saved})
out('invalid_probe',compose_pipeline_predictions(np.array([np.nan]),np.array([[np.nan,1.]]),np.array([1,2]),None,None,.5))

```
