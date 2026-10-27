# Mahalanobis vs MCP — matched frozen upstream

Primary comparison: recall gate; fixed gate is a secondary ablation.

| Heldout | Gate | Method | Detected/support | Precision | Recall | F1 | Known FRR | Benign unknown | Gate-blocked unknown |
|---|---|---|---|---|---|---|---|---|---|
| 9 | fixed | mcp | 5753/23770 | 0.686761 | 0.242028 | 0.357918 | 0.049109 | 3 | 2147 |
| 9 | fixed | mahalanobis | 6091/23770 | 0.698349 | 0.256247 | 0.374923 | 0.049090 | 11 | 2147 |
| 9 | recall | mcp | 5819/23770 | 0.685798 | 0.244804 | 0.360812 | 0.049165 | 42 | 1445 |
| 9 | recall | mahalanobis | 6356/23770 | 0.700617 | 0.267396 | 0.387065 | 0.049240 | 88 | 1445 |
| 25 | fixed | mcp | 7164/23860 | 0.733415 | 0.300251 | 0.426074 | 0.048010 | 46 | 768 |
| 25 | fixed | mahalanobis | 1818/23860 | 0.408539 | 0.076194 | 0.128435 | 0.048723 | 36 | 768 |
| 25 | recall | mcp | 7706/23860 | 0.736289 | 0.322967 | 0.448989 | 0.048516 | 175 | 187 |
| 25 | recall | mahalanobis | 1855/23860 | 0.405376 | 0.077745 | 0.130468 | 0.048948 | 113 | 187 |
| 26 | fixed | mcp | 3102/14272 | 0.501131 | 0.217349 | 0.303196 | 0.048943 | 11 | 229 |
| 26 | fixed | mahalanobis | 901/14272 | 0.223407 | 0.063131 | 0.098443 | 0.049675 | 9 | 229 |
| 26 | recall | mcp | 3129/14272 | 0.501041 | 0.219240 | 0.305015 | 0.048975 | 37 | 49 |
| 26 | recall | mahalanobis | 920/14272 | 0.224172 | 0.064462 | 0.100131 | 0.049850 | 50 | 49 |

No superiority/significance claim: one seed, previously inspected test, shared validation.
