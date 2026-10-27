# Đợt huấn luyện mới — so sánh novelty cố định

Trạng thái: completed. Ứng viên kNN được đề xuất sau khi đã xem test lịch sử.
Đây là kiểm tra độ ổn định theo seed trên split cố định, KHÔNG phải test độc lập.

| Held-out | Seed | Gate | Method | Detected/support | Precision | Recall | F1 | Known FRR | E2E macro-F1 |
|---|---|---|---|---|---|---|---|---|---|
| 9 | 42 | fixed | max_probability | 5753/23770 | 0.686761 | 0.242028 | 0.357918 | 0.049109 | 0.765951 |
| 9 | 42 | recall | max_probability | 5819/23770 | 0.685798 | 0.244804 | 0.360812 | 0.049165 | 0.768922 |
| 9 | 42 | fixed | mahalanobis | 6091/23770 | 0.698349 | 0.256247 | 0.374923 | 0.049090 | 0.678782 |
| 9 | 42 | recall | mahalanobis | 6356/23770 | 0.700617 | 0.267396 | 0.387065 | 0.049240 | 0.699114 |
| 9 | 42 | fixed | knn_distance | 21623/23770 | 0.893143 | 0.909676 | 0.901334 | 0.048041 | 0.792281 |
| 9 | 42 | recall | knn_distance | 22325/23770 | 0.890436 | 0.939209 | 0.914172 | 0.048435 | 0.803526 |
| 9 | 43 | fixed | max_probability | 8455/23770 | 0.762467 | 0.355700 | 0.485097 | 0.049165 | 0.797780 |
| 9 | 43 | recall | max_probability | 8871/23770 | 0.769117 | 0.373202 | 0.502549 | 0.049221 | 0.791389 |
| 9 | 43 | fixed | mahalanobis | 6030/23770 | 0.693821 | 0.253681 | 0.371523 | 0.049615 | 0.717066 |
| 9 | 43 | recall | mahalanobis | 8106/23770 | 0.748200 | 0.341018 | 0.468501 | 0.049877 | 0.713941 |
| 9 | 43 | fixed | knn_distance | 18068/23770 | 0.870034 | 0.760118 | 0.811370 | 0.050083 | 0.790045 |
| 9 | 43 | recall | knn_distance | 20819/23770 | 0.880408 | 0.875852 | 0.878124 | 0.050608 | 0.788068 |
| 9 | 44 | fixed | max_probability | 10252/23770 | 0.794852 | 0.431300 | 0.559180 | 0.049503 | 0.794742 |
| 9 | 44 | recall | max_probability | 10415/23770 | 0.795524 | 0.438157 | 0.565081 | 0.049596 | 0.813739 |
| 9 | 44 | fixed | mahalanobis | 6716/23770 | 0.713027 | 0.282541 | 0.404712 | 0.050402 | 0.705351 |
| 9 | 44 | recall | mahalanobis | 7224/23770 | 0.724065 | 0.303912 | 0.428127 | 0.050589 | 0.704417 |
| 9 | 44 | fixed | knn_distance | 22666/23770 | 0.895358 | 0.953555 | 0.923541 | 0.049240 | 0.799390 |
| 9 | 44 | recall | knn_distance | 23374/23770 | 0.894836 | 0.983340 | 0.937003 | 0.049596 | 0.791379 |
| 25 | 42 | fixed | max_probability | 7164/23860 | 0.733415 | 0.300251 | 0.426074 | 0.048010 | 0.743283 |
| 25 | 42 | recall | max_probability | 7706/23860 | 0.736289 | 0.322967 | 0.448989 | 0.048516 | 0.769357 |
| 25 | 42 | fixed | mahalanobis | 1818/23860 | 0.408539 | 0.076194 | 0.128435 | 0.048723 | 0.639273 |
| 25 | 42 | recall | mahalanobis | 1855/23860 | 0.405376 | 0.077745 | 0.130468 | 0.048948 | 0.656574 |
| 25 | 42 | fixed | knn_distance | 14401/23860 | 0.844435 | 0.603562 | 0.703964 | 0.049004 | 0.781936 |
| 25 | 42 | recall | knn_distance | 14968/23860 | 0.843553 | 0.627326 | 0.719546 | 0.049286 | 0.821728 |
| 25 | 43 | fixed | max_probability | 7681/23860 | 0.746743 | 0.321920 | 0.449892 | 0.048366 | 0.776720 |
| 25 | 43 | recall | max_probability | 9227/23860 | 0.772199 | 0.386714 | 0.515345 | 0.048573 | 0.796012 |
| 25 | 43 | fixed | mahalanobis | 1727/23860 | 0.399769 | 0.072381 | 0.122569 | 0.048460 | 0.698471 |
| 25 | 43 | recall | mahalanobis | 1738/23860 | 0.394462 | 0.072842 | 0.122975 | 0.048591 | 0.685101 |
| 25 | 43 | fixed | knn_distance | 12379/23860 | 0.820290 | 0.518818 | 0.635619 | 0.050506 | 0.823699 |
| 25 | 43 | recall | knn_distance | 13961/23860 | 0.831854 | 0.585122 | 0.687006 | 0.050618 | 0.841172 |
| 25 | 44 | fixed | max_probability | 5244/23860 | 0.665398 | 0.219782 | 0.330424 | 0.048929 | 0.768601 |
| 25 | 44 | recall | max_probability | 9367/23860 | 0.772727 | 0.392582 | 0.520649 | 0.049342 | 0.778030 |
| 25 | 44 | fixed | mahalanobis | 1104/23860 | 0.300163 | 0.046270 | 0.080180 | 0.048179 | 0.684233 |
| 25 | 44 | recall | mahalanobis | 1321/23860 | 0.334008 | 0.055365 | 0.094985 | 0.048347 | 0.661705 |
| 25 | 44 | fixed | knn_distance | 6348/23860 | 0.719483 | 0.266052 | 0.388459 | 0.046170 | 0.791661 |
| 25 | 44 | recall | knn_distance | 10719/23860 | 0.807032 | 0.449246 | 0.577190 | 0.046339 | 0.811374 |
| 26 | 42 | fixed | max_probability | 3102/14272 | 0.501131 | 0.217349 | 0.303196 | 0.048943 | 0.792861 |
| 26 | 42 | recall | max_probability | 3129/14272 | 0.501041 | 0.219240 | 0.305015 | 0.048975 | 0.787957 |
| 26 | 42 | fixed | mahalanobis | 901/14272 | 0.223407 | 0.063131 | 0.098443 | 0.049675 | 0.714120 |
| 26 | 42 | recall | mahalanobis | 920/14272 | 0.224172 | 0.064462 | 0.100131 | 0.049850 | 0.691680 |
| 26 | 42 | fixed | knn_distance | 14043/14272 | 0.816311 | 0.983955 | 0.892327 | 0.049913 | 0.822048 |
| 26 | 42 | recall | knn_distance | 14223/14272 | 0.814418 | 0.996567 | 0.896332 | 0.050168 | 0.813844 |
| 26 | 43 | fixed | max_probability | 3283/14272 | 0.514335 | 0.230031 | 0.317889 | 0.049118 | 0.761385 |
| 26 | 43 | recall | max_probability | 3420/14272 | 0.521103 | 0.239630 | 0.328294 | 0.049182 | 0.809416 |
| 26 | 43 | fixed | mahalanobis | 365/14272 | 0.106321 | 0.025575 | 0.041231 | 0.048641 | 0.677695 |
| 26 | 43 | recall | mahalanobis | 396/14272 | 0.111991 | 0.027747 | 0.044474 | 0.048816 | 0.711506 |
| 26 | 43 | fixed | knn_distance | 13740/14272 | 0.816108 | 0.962724 | 0.883374 | 0.048975 | 0.797177 |
| 26 | 43 | recall | knn_distance | 14182/14272 | 0.813795 | 0.993694 | 0.894792 | 0.049325 | 0.799162 |
| 26 | 44 | fixed | max_probability | 4036/14272 | 0.567252 | 0.282791 | 0.377426 | 0.048768 | 0.787104 |
| 26 | 44 | recall | max_probability | 4066/14272 | 0.566295 | 0.284893 | 0.379079 | 0.048848 | 0.783531 |
| 26 | 44 | fixed | mahalanobis | 2162/14272 | 0.406162 | 0.151485 | 0.220669 | 0.049977 | 0.693856 |
| 26 | 44 | recall | mahalanobis | 2166/14272 | 0.401706 | 0.151766 | 0.220301 | 0.050231 | 0.695385 |
| 26 | 44 | fixed | knn_distance | 14191/14272 | 0.821096 | 0.994325 | 0.899445 | 0.048577 | 0.793145 |
| 26 | 44 | recall | knn_distance | 14244/14272 | 0.816603 | 0.998038 | 0.898250 | 0.049023 | 0.796016 |

Vai trò metrics: final_unknown_metrics là kết quả sau gate; score_only_unknown_metrics bỏ qua gate và benign.
Đọc error_decomposition, per-class support/F1, class_rejection.json và compact predictions trong từng evaluation.
summary.json: mean/std/min/max theo heldout; paired delta cùng seed. Không cộng 3 seed thành 3 tập test độc lập.
Không chọn lại k, gate budget, threshold hoặc mô hình theo bảng test này.

## Giới hạn đã khóa

- candidate motivated by historical test: exploratory method-development evidence
- same fixed stratified split; seed varies fitting AND kNN reference, not split
- repeated seeds are not new independent test rows; no significance/superiority claim
- known validation reused for upstream stopping and novelty calibration
- feature-vector overlap remains; raw release provenance unverified; Attempted preserved
- no external dataset, chronological split or real-world zero-day confirmation
- unknown=-1, never recover the unseen attack semantic name
- known-validation recall gate cannot guarantee unknown retention
- CUDA training not guaranteed bitwise deterministic
