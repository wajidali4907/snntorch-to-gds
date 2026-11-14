| run         | method      | variant                            |   lam |   prune |   acc | spike_match   |   zero |   pow2 |   other |   area |   d_acc_pts |   area_saving_% |
|:------------|:------------|:-----------------------------------|------:|--------:|------:|:--------------|-------:|-------:|--------:|-------:|------------:|----------------:|
| yinyang_qat | qat         | qat                                |   0   |     0   |  80   | True          |     27 |    232 |     637 | 4261.7 |         0   |             0   |
| yy_eq2_1    | qat_silicon | qat_silicon (full Eq. 2)           |   1   |     0   |  79.4 | True          |     53 |    332 |     511 | 4197.5 |        -0.6 |             1.5 |
| yy_eq2_3    | qat_silicon | qat_silicon (full Eq. 2)           |   3   |     0   |  80.7 | True          |     81 |    361 |     454 | 4219.7 |         0.7 |             1   |
| yy_l1_0.3   | qat_silicon | qat_silicon (zero term only, c1=0) |   0.3 |     0   |  81.1 | True          |    111 |    185 |     600 | 3522   |         1.1 |            17.4 |
| yy_l1_1     | qat_silicon | qat_silicon (zero term only, c1=0) |   1   |     0   |  82.2 | True          |    143 |    200 |     553 | 3468.7 |         2.2 |            18.6 |
| yy_l1_10    | qat_silicon | qat_silicon (zero term only, c1=0) |  10   |     0   |  74.2 | True          |    319 |    173 |     404 | 2932.9 |        -5.8 |            31.2 |
| yy_l1_3     | qat_silicon | qat_silicon (zero term only, c1=0) |   3   |     0   |  80.4 | True          |    204 |    199 |     493 | 3312.1 |         0.4 |            22.3 |
| yy_prune0.5 | qat_prune   | qat_prune                          |   0   |     0.5 |  73.1 | True          |    448 |     73 |     375 | 3568.3 |        -6.9 |            16.3 |
| yy_prune0.7 | qat_prune   | qat_prune                          |   0   |     0.7 |  60.6 | True          |    627 |     32 |     237 | 2587.1 |       -19.4 |            39.3 |
| yy_prune0.9 | qat_prune   | qat_prune                          |   0   |     0.9 |  36.6 | True          |    805 |      6 |      85 | 1029.3 |       -43.4 |            75.8 |
