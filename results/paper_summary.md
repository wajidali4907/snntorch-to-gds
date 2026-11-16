# Paper results

All accuracies are from the bit-exact integer model (identical to RTL simulation; `spike_match` = every spike of every layer matched in Verilator). Area = ORFS/Yosys synthesized cell area, ASAP7, 1 GHz target, fully parallel (P = N_in).

## Unified results (one row per dataset; Δacc in points, saving vs. QAT baseline)

| dataset   |   baseline_acc |   baseline_area |   prune_Δacc |   prune_saving_% |   L1_Δacc |   L1_saving_% |   L1+log_Δacc |   L1+log_saving_% |   tuned_baseline_acc |   tuned_float_Δacc |   tuned_float_saving_% |   tuned_prune0.5_Δacc |   tuned_prune0.5_saving_% |   tuned_l1_1_Δacc |   tuned_l1_1_saving_% |   tuned_l1_3_Δacc |   tuned_l1_3_saving_% |   retuned_baseline_acc |   retuned_float_Δacc |   retuned_float_saving_% |   retuned_prune0.5_Δacc |   retuned_prune0.5_saving_% |   retuned_l1_1_Δacc |   retuned_l1_1_saving_% |   retuned_l1_3_Δacc |   retuned_l1_3_saving_% | L1+log_variant   |
|:----------|---------------:|----------------:|-------------:|-----------------:|----------:|--------------:|--------------:|------------------:|---------------------:|-------------------:|-----------------------:|----------------------:|--------------------------:|------------------:|----------------------:|------------------:|----------------------:|-----------------------:|---------------------:|-------------------------:|------------------------:|----------------------------:|--------------------:|------------------------:|--------------------:|------------------------:|:-----------------|
| yinyang   |           81.3 |          4286.5 |         -5.3 |             16.7 |       0.1 |          20.4 |          -0.2 |               1.4 |                 87.5 |              -19.3 |                    0.2 |                  -6.2 |                      20.8 |              -2.9 |                  14.6 |              -9.9 |                  24.5 |                   83.7 |                -14.6 |                     -0.3 |                    -6.5 |                        18.7 |                -2.6 |                    17.7 |                -3.3 |                    23.9 | log-pow2 λp=0.3  |
| braille   |           58.2 |          6645.6 |         -2.2 |             15   |      -4.5 |          40.9 |          -3.1 |              33.7 |                 60   |               -9.5 |                   -0.6 |                  -1.7 |                      19.5 |              -0.2 |                  37.8 |              -0.7 |                  43.8 |                  nan   |                nan   |                    nan   |                   nan   |                       nan   |               nan   |                   nan   |               nan   |                   nan   | log-pow2 λp=0.3  |
| ntidigits |           69.9 |          7461.6 |         -2.3 |             13.6 |      -1.1 |          27   |          -0.8 |              23.1 |                 71   |               -1.9 |                    0.7 |                  -0   |                      21.3 |              -0   |                  38.7 |               0.6 |                  49.6 |                  nan   |                nan   |                    nan   |                   nan   |                       nan   |               nan   |                   nan   |               nan   |                   nan   | log-pow2 λp=0.3  |

## yinyang

### Main comparison (mean over seeds; Δ and saving vs. QAT baseline)

| variant              |   n |   acc |   acc_sd |   Δacc_pts |   area |   area_sd |   area_saving_% |   zero_% |   pow2_%_of_nz | spike_match   |
|:---------------------|----:|------:|---------:|-----------:|-------:|----------:|----------------:|---------:|---------------:|:--------------|
| QAT baseline         |   3 |  81.3 |      2.1 |        0   |   4287 |        79 |             0   |      2.7 |           25.2 | all           |
| QAT + prune 50%      |   3 |  75.9 |      2.1 |       -5.3 |   3573 |        23 |            16.7 |     50   |           13.2 | all           |
| silicon-aware L1 λ=3 |   3 |  81.4 |      0.7 |        0.1 |   3412 |       105 |            20.4 |     21.1 |           28.5 | all           |

### λ sweep (seed 0)

| variant           |   n |   acc |   acc_sd |   Δacc_pts |   area |   area_sd |   area_saving_% |   zero_% |   pow2_%_of_nz | spike_match   |
|:------------------|----:|------:|---------:|-----------:|-------:|----------:|----------------:|---------:|---------------:|:--------------|
| L1 λ=0.3 (seed 0) |   1 |  81.1 |        0 |       -0.2 |   3522 |         0 |            17.8 |     12.4 |           23.6 | all           |
| L1 λ=1 (seed 0)   |   1 |  82.2 |        0 |        0.9 |   3469 |         0 |            19.1 |     16   |           26.6 | all           |
| L1 λ=3 (seed 0)   |   1 |  80.4 |        0 |       -0.9 |   3312 |         0 |            22.7 |     22.8 |           28.8 | all           |
| L1 λ=10 (seed 0)  |   1 |  74.2 |        0 |       -7.1 |   2933 |         0 |            31.6 |     35.6 |           30   | all           |

### New log-domain power-of-two term

| variant                  |   n |   acc |   acc_sd |   Δacc_pts |   area |   area_sd |   area_saving_% |   zero_% |   pow2_%_of_nz | spike_match   |
|:-------------------------|----:|------:|---------:|-----------:|-------:|----------:|----------------:|---------:|---------------:|:--------------|
| L1 λ=3 only              |   3 |  81.4 |      0.7 |        0.1 |   3412 |       105 |            20.4 |     21.1 |           28.5 | all           |
| L1 λ=3 + log-pow2 λp=0.3 |   3 |  81.1 |      0.2 |       -0.2 |   4224 |        46 |             1.4 |      6.8 |           37.6 | all           |
| L1 λ=3 + log-pow2 λp=1   |   3 |  78.8 |      2.2 |       -2.5 |   4236 |        13 |             1.2 |      3.9 |           47.8 | all           |
| L1 λ=3 + log-pow2 λp=3   |   3 |  69.5 |      8.7 |      -11.7 |   4193 |        64 |             2.2 |      3.9 |           60   | all           |

### Hidden-layer size (seed 0; saving vs. hidden-128 baseline)

| variant                          |   n |   acc |   acc_sd |   Δacc_pts |   area |   area_sd |   area_saving_% |   zero_% |   pow2_%_of_nz | spike_match   |
|:---------------------------------|----:|------:|---------:|-----------:|-------:|----------:|----------------:|---------:|---------------:|:--------------|
| hidden 32: QAT baseline          |   1 |  77.5 |        0 |       -3.8 |   1203 |         0 |            71.9 |      1.8 |           18.2 | all           |
| hidden 32: silicon-aware L1 λ=3  |   1 |  76.1 |        0 |       -5.2 |    846 |         0 |            80.3 |     23.2 |           20.9 | all           |
| hidden 64: QAT baseline          |   1 |  77.5 |        0 |       -3.8 |   2232 |         0 |            47.9 |      2   |           25.1 | all           |
| hidden 64: silicon-aware L1 λ=3  |   1 |  67.8 |        0 |      -13.5 |   1692 |         0 |            60.5 |     21.7 |           21.1 | all           |
| hidden 128: QAT baseline         |   1 |  80   |        0 |       -1.3 |   4262 |         0 |             0.6 |      3   |           26.7 | all           |
| hidden 128: silicon-aware L1 λ=3 |   1 |  80.4 |        0 |       -0.9 |   3312 |         0 |            22.7 |     22.8 |           28.8 | all           |
| hidden 256: QAT baseline         |   1 |  84.9 |        0 |        3.6 |   8360 |         0 |           -95   |      4.9 |           27.7 | all           |
| hidden 256: silicon-aware L1 λ=3 |   1 |  80.2 |        0 |       -1.1 |   6931 |         0 |           -61.7 |     18.7 |           29.1 | all           |

### After placement + global route (seed 0)

| run         |   acc |   area |   grt_stdcell |   grt_core |   grt_wns |   grt_saving_% |
|:------------|------:|-------:|--------------:|-----------:|----------:|---------------:|
| yinyang_qat |  80   | 4261.7 |        4841.7 |    10610   |    -283.1 |            0   |
| yy_l1_3     |  80.4 | 3312.1 |        3690.6 |     8249.7 |    -190.3 |           23.8 |

### Main comparison with TUNED baselines (mean over seeds; vs. tuned QAT)

| variant                                  |   n |   acc |   acc_sd |   Δacc_pts |   area |   area_sd |   area_saving_% |   zero_% |   pow2_%_of_nz | spike_match   |
|:-----------------------------------------|----:|------:|---------:|-----------:|-------:|----------:|----------------:|---------:|---------------:|:--------------|
| tuned: no QAT (float train, round after) |   3 |  68.2 |      5.3 |      -19.3 |   4449 |        19 |             0.2 |      1.5 |           15.4 | all           |
| tuned: QAT baseline                      |   3 |  87.5 |      4.1 |        0   |   4459 |        35 |             0   |      1.6 |           14.4 | all           |
| tuned: QAT + prune 50%                   |   3 |  81.3 |      2.6 |       -6.2 |   3533 |        33 |            20.8 |     50   |            5.7 | all           |
| tuned: silicon-aware L1 λ=1              |   3 |  84.7 |      4.4 |       -2.9 |   3809 |       172 |            14.6 |     21.5 |           18.2 | all           |
| tuned: silicon-aware L1 λ=3              |   3 |  77.7 |      4.6 |       -9.9 |   3365 |       350 |            24.5 |     35.3 |           22.1 | all           |

### Main comparison with MULTI-SEED re-tuned baseline (mean over seeds; vs. re-tuned QAT)

| variant                                     |   n |   acc |   acc_sd |   Δacc_pts |   area |   area_sd |   area_saving_% |   zero_% |   pow2_%_of_nz | spike_match   |
|:--------------------------------------------|----:|------:|---------:|-----------:|-------:|----------:|----------------:|---------:|---------------:|:--------------|
| re-tuned: no QAT (float train, round after) |   3 |  69.1 |      3.8 |      -14.6 |   4323 |        16 |            -0.3 |      2.8 |           23.4 | all           |
| re-tuned: QAT baseline                      |   3 |  83.7 |      1.2 |        0   |   4312 |        22 |             0   |      2.4 |           22.6 | all           |
| re-tuned: QAT + prune 50%                   |   3 |  77.2 |      1.4 |       -6.5 |   3505 |        11 |            18.7 |     50   |            8.9 | all           |
| re-tuned: silicon-aware L1 λ=1              |   3 |  81.1 |      2   |       -2.6 |   3548 |        78 |            17.7 |     18.9 |           25.6 | all           |
| re-tuned: silicon-aware L1 λ=3              |   3 |  80.4 |      1.7 |       -3.3 |   3280 |       134 |            23.9 |     30.1 |           27.6 | all           |

## braille

### Main comparison (mean over seeds; Δ and saving vs. QAT baseline)

| variant              |   n |   acc |   acc_sd |   Δacc_pts |   area |   area_sd |   area_saving_% |   zero_% |   pow2_%_of_nz | spike_match   |
|:---------------------|----:|------:|---------:|-----------:|-------:|----------:|----------------:|---------:|---------------:|:--------------|
| QAT baseline         |   3 |  58.2 |      1.7 |        0   |   6646 |        19 |             0   |     24.1 |           80.7 | all           |
| QAT + prune 50%      |   3 |  56   |      1.7 |       -2.2 |   5650 |       113 |            15   |     50.4 |           70.7 | all           |
| silicon-aware L1 λ=3 |   3 |  53.7 |      1.5 |       -4.5 |   3929 |       159 |            40.9 |     57.5 |           79.4 | all           |

### λ sweep (seed 0)

| variant          |   n |   acc |   acc_sd |   Δacc_pts |   area |   area_sd |   area_saving_% |   zero_% |   pow2_%_of_nz | spike_match   |
|:-----------------|----:|------:|---------:|-----------:|-------:|----------:|----------------:|---------:|---------------:|:--------------|
| L1 λ=1 (seed 0)  |   1 |  56.3 |        0 |       -1.9 |   4434 |         0 |            33.3 |     51.6 |           80.2 | all           |
| L1 λ=3 (seed 0)  |   1 |  55.7 |        0 |       -2.4 |   4135 |         0 |            37.8 |     54.9 |           80.5 | all           |
| L1 λ=10 (seed 0) |   1 |  52.2 |        0 |       -6   |   3649 |         0 |            45.1 |     62   |           79.3 | all           |

### New log-domain power-of-two term

| variant                  |   n |   acc |   acc_sd |   Δacc_pts |   area |   area_sd |   area_saving_% |   zero_% |   pow2_%_of_nz | spike_match   |
|:-------------------------|----:|------:|---------:|-----------:|-------:|----------:|----------------:|---------:|---------------:|:--------------|
| L1 λ=3 only              |   3 |  53.7 |      1.5 |       -4.5 |   3929 |       159 |            40.9 |     57.5 |           79.4 | all           |
| L1 λ=3 + log-pow2 λp=0.3 |   1 |  55.1 |      0   |       -3.1 |   4403 |         0 |            33.7 |     50.2 |           81.8 | all           |
| L1 λ=3 + log-pow2 λp=1   |   3 |  54.6 |      1.7 |       -3.5 |   4140 |        59 |            37.7 |     52.8 |           83.5 | all           |
| L1 λ=3 + log-pow2 λp=3   |   1 |  53.8 |      0   |       -4.4 |   4035 |         0 |            39.3 |     52.8 |           87   | all           |

### Hidden-layer size (seed 0; saving vs. hidden-128 baseline)

| variant                          |   n |   acc |   acc_sd |   Δacc_pts |   area |   area_sd |   area_saving_% |   zero_% |   pow2_%_of_nz | spike_match   |
|:---------------------------------|----:|------:|---------:|-----------:|-------:|----------:|----------------:|---------:|---------------:|:--------------|
| hidden 64: QAT baseline          |   1 |  53.3 |        0 |       -4.8 |   3935 |         0 |            40.8 |     18.2 |           76.1 | all           |
| hidden 64: silicon-aware L1 λ=3  |   1 |  49   |        0 |       -9.2 |   2619 |         0 |            60.6 |     52.9 |           75.8 | all           |
| hidden 128: QAT baseline         |   1 |  58.1 |        0 |       -0.1 |   6620 |         0 |             0.4 |     25   |           81.3 | all           |
| hidden 128: silicon-aware L1 λ=3 |   1 |  55.7 |        0 |       -2.4 |   4135 |         0 |            37.8 |     54.9 |           80.5 | all           |
| hidden 256: QAT baseline         |   1 |  59   |        0 |        0.8 |   8156 |         0 |           -22.7 |     41.4 |           85.8 | all           |
| hidden 256: silicon-aware L1 λ=3 |   1 |  58.1 |        0 |       -0.1 |   5674 |         0 |            14.6 |     66.6 |           83.8 | all           |

### After placement + global route (seed 0)

| run          |   acc |   area |   grt_stdcell |   grt_core |   grt_wns |   grt_saving_% |
|:-------------|------:|-------:|--------------:|-----------:|----------:|---------------:|
| braille_qat  |  58.1 | 6619.8 |        7861.5 |    16524.3 |    -368.2 |            0   |
| braille_l1_3 |  55.7 | 4135.3 |        4834.1 |    10317.3 |    -249.8 |           38.5 |

### Main comparison with TUNED baselines (mean over seeds; vs. tuned QAT)

| variant                                  |   n |   acc |   acc_sd |   Δacc_pts |   area |   area_sd |   area_saving_% |   zero_% |   pow2_%_of_nz | spike_match   |
|:-----------------------------------------|----:|------:|---------:|-----------:|-------:|----------:|----------------:|---------:|---------------:|:--------------|
| tuned: no QAT (float train, round after) |   3 |  50.5 |      1.7 |       -9.5 |   7037 |        19 |            -0.6 |     17.4 |           73.9 | all           |
| tuned: QAT baseline                      |   3 |  60   |      0.9 |        0   |   6999 |        55 |             0   |     18.2 |           71.5 | all           |
| tuned: QAT + prune 50%                   |   3 |  58.3 |      1   |       -1.7 |   5634 |        82 |            19.5 |     50.4 |           55.2 | all           |
| tuned: silicon-aware L1 λ=1              |   3 |  59.9 |      0.7 |       -0.2 |   4354 |       176 |            37.8 |     52.3 |           69.9 | all           |
| tuned: silicon-aware L1 λ=3              |   3 |  59.3 |      1.1 |       -0.7 |   3932 |       213 |            43.8 |     57.6 |           70.7 | all           |

## ntidigits

### Main comparison (mean over seeds; Δ and saving vs. QAT baseline)

| variant              |   n |   acc |   acc_sd |   Δacc_pts |   area |   area_sd |   area_saving_% |   zero_% |   pow2_%_of_nz | spike_match   |
|:---------------------|----:|------:|---------:|-----------:|-------:|----------:|----------------:|---------:|---------------:|:--------------|
| QAT baseline         |   3 |  69.9 |      0.7 |        0   |   7462 |        21 |             0   |     19.5 |           79.6 | all           |
| QAT + prune 50%      |   3 |  67.6 |      2.8 |       -2.3 |   6449 |        76 |            13.6 |     50.2 |           67.1 | all           |
| silicon-aware L1 λ=3 |   3 |  68.7 |      0.2 |       -1.1 |   5444 |       152 |            27   |     43   |           82.4 | all           |

### λ sweep (seed 0)

| variant          |   n |   acc |   acc_sd |   Δacc_pts |   area |   area_sd |   area_saving_% |   zero_% |   pow2_%_of_nz | spike_match   |
|:-----------------|----:|------:|---------:|-----------:|-------:|----------:|----------------:|---------:|---------------:|:--------------|
| L1 λ=1 (seed 0)  |   1 |  70   |        0 |        0.1 |   6166 |         0 |            17.4 |     34.3 |           82.7 | all           |
| L1 λ=3 (seed 0)  |   1 |  68.5 |        0 |       -1.3 |   5659 |         0 |            24.2 |     40.2 |           82.7 | all           |
| L1 λ=10 (seed 0) |   1 |  57.4 |        0 |      -12.5 |   4884 |         0 |            34.5 |     49.3 |           83.9 | all           |

### New log-domain power-of-two term

| variant                  |   n |   acc |   acc_sd |   Δacc_pts |   area |   area_sd |   area_saving_% |   zero_% |   pow2_%_of_nz | spike_match   |
|:-------------------------|----:|------:|---------:|-----------:|-------:|----------:|----------------:|---------:|---------------:|:--------------|
| L1 λ=3 only              |   3 |  68.7 |      0.2 |       -1.1 |   5444 |       152 |            27   |     43   |           82.4 | all           |
| L1 λ=3 + log-pow2 λp=0.3 |   1 |  69.1 |      0   |       -0.8 |   5740 |         0 |            23.1 |     36   |           86.5 | all           |
| L1 λ=3 + log-pow2 λp=1   |   3 |  68.2 |      1.6 |       -1.7 |   5683 |        30 |            23.8 |     35.7 |           89.8 | all           |
| L1 λ=3 + log-pow2 λp=3   |   1 |  70.2 |      0   |        0.3 |   5943 |         0 |            20.4 |     32.6 |           94   | all           |

### Hidden-layer size (seed 0; saving vs. hidden-128 baseline)

| variant                          |   n |   acc |   acc_sd |   Δacc_pts |   area |   area_sd |   area_saving_% |   zero_% |   pow2_%_of_nz | spike_match   |
|:---------------------------------|----:|------:|---------:|-----------:|-------:|----------:|----------------:|---------:|---------------:|:--------------|
| hidden 64: QAT baseline          |   1 |  70.8 |        0 |        0.9 |   3995 |         0 |            46.5 |     18.2 |           76.3 | all           |
| hidden 64: silicon-aware L1 λ=3  |   1 |  64.2 |        0 |       -5.6 |   3380 |         0 |            54.7 |     31.6 |           79   | all           |
| hidden 128: QAT baseline         |   1 |  70.8 |        0 |        0.9 |   7433 |         0 |             0.4 |     19.7 |           80.5 | all           |
| hidden 128: silicon-aware L1 λ=3 |   1 |  68.5 |        0 |       -1.3 |   5659 |         0 |            24.2 |     40.2 |           82.7 | all           |
| hidden 256: QAT baseline         |   1 |  72.8 |        0 |        3   |  13807 |         0 |           -85   |     22.3 |           85.6 | all           |
| hidden 256: silicon-aware L1 λ=3 |   1 |  73.5 |        0 |        3.6 |  11379 |         0 |           -52.5 |     37.4 |           86.7 | all           |

### After placement + global route (seed 0)

| run            |   acc |   area |   grt_stdcell |   grt_core |   grt_wns |   grt_saving_% |
|:---------------|------:|-------:|--------------:|-----------:|----------:|---------------:|
| ntidigits_qat  |  70.8 | 7433   |        8905.5 |    18539.8 |    -259.7 |            0   |
| ntidigits_l1_3 |  68.5 | 5658.6 |        6700.2 |    14126.3 |    -184.7 |           24.8 |

### Main comparison with TUNED baselines (mean over seeds; vs. tuned QAT)

| variant                                  |   n |   acc |   acc_sd |   Δacc_pts |   area |   area_sd |   area_saving_% |   zero_% |   pow2_%_of_nz | spike_match   |
|:-----------------------------------------|----:|------:|---------:|-----------:|-------:|----------:|----------------:|---------:|---------------:|:--------------|
| tuned: no QAT (float train, round after) |   3 |  69.1 |      1.5 |       -1.9 |   8338 |        19 |             0.7 |     15.1 |           65.2 | all           |
| tuned: QAT baseline                      |   3 |  71   |      0.6 |        0   |   8399 |        41 |             0   |     15.4 |           65.2 | all           |
| tuned: QAT + prune 50%                   |   3 |  71   |      1.8 |       -0   |   6609 |        24 |            21.3 |     50.3 |           42.8 | all           |
| tuned: silicon-aware L1 λ=1              |   3 |  71   |      0.6 |       -0   |   5151 |       262 |            38.7 |     51   |           68.1 | all           |
| tuned: silicon-aware L1 λ=3              |   3 |  71.6 |      0.6 |        0.6 |   4231 |       369 |            49.6 |     61.7 |           66.2 | all           |

## Controlled power-of-two test (0% zeros)

Layer 16x32, 8-bit, 0% zeros, |w| in [3,63], clock 1000.0 ps, P = fully parallel, seeds [0, 1, 2]. Change % is relative to pow2_frac = 0.

|   pow2_frac |   area_mean |   area_std |   measured |   measured_std |   eq2_calibrated |   eq2_c1_eq_c0 |   count_model |
|------------:|------------:|-----------:|-----------:|---------------:|-----------------:|---------------:|--------------:|
|        0    |     1140.97 |       5.07 |       0    |           0    |             0    |           0    |          0    |
|        0.25 |     1053.32 |       6.37 |      -7.68 |           0.32 |            23.08 |         -13.34 |         -4.92 |
|        0.5  |      985.06 |       1.55 |     -13.66 |           0.25 |            47.48 |         -27.17 |         -9.84 |
|        0.75 |      888.75 |       8.4  |     -22.11 |           0.69 |            68.32 |         -39.25 |        -14.76 |
|        1    |      785.66 |       7.86 |     -31.14 |           0.83 |            93.39 |         -53.26 |        -19.69 |

## Controlled power-of-two test (50% zeros)

Layer 16x32, 8-bit, 50% zeros, |w| in [3,63], clock 1000.0 ps, P = fully parallel, seeds [0, 1, 2]. Change % is relative to pow2_frac = 0.

|   pow2_frac |   area_mean |   area_std |   measured |   measured_std |   eq2_calibrated |   eq2_c1_eq_c0 |   count_model |
|------------:|------------:|-----------:|-----------:|---------------:|-----------------:|---------------:|--------------:|
|        0    |      826.93 |       3.57 |       0    |           0    |             0    |           0    |          0    |
|        0.25 |      794.32 |       7.1  |      -3.94 |           1.22 |            14.96 |         -11.98 |         -3.33 |
|        0.5  |      766    |      12.34 |      -7.37 |           1.57 |            30.81 |         -24.06 |         -6.66 |
|        0.75 |      711.65 |      10.81 |     -13.94 |           1.11 |            44.45 |         -34.99 |         -9.99 |
|        1    |      654.93 |       4.79 |     -20.8  |           0.56 |            60.02 |         -46.72 |        -13.32 |

## Controlled power-of-two test (80% zeros)

Layer 16x32, 8-bit, 80% zeros, |w| in [3,63], clock 1000.0 ps, P = fully parallel, seeds [0, 1, 2]. Change % is relative to pow2_frac = 0.

|   pow2_frac |   area_mean |   area_std |   measured |   measured_std |   eq2_calibrated |   eq2_c1_eq_c0 |   count_model |
|------------:|------------:|-----------:|-----------:|---------------:|-----------------:|---------------:|--------------:|
|        0    |      649.79 |       3.14 |       0    |           0    |             0    |           0    |          0    |
|        0.25 |      635.4  |      13.75 |      -2.22 |           1.82 |             8.07 |         -10.13 |         -1.72 |
|        0.5  |      613.58 |       5.49 |      -5.57 |           0.71 |            15.17 |         -18.72 |         -3.37 |
|        0.75 |      601.58 |       9.36 |      -7.42 |           1.36 |            20.55 |         -25.36 |         -5.02 |
|        1    |      582.26 |       9.8  |     -10.4  |           1.08 |            27.34 |         -33.39 |         -6.74 |

## Controlled power-of-two test (128-input layer)

Layer 8x128, 8-bit, 50% zeros, |w| in [3,63], clock 1000.0 ps, P = fully parallel, seeds [0, 1, 2]. Change % is relative to pow2_frac = 0.

|   pow2_frac |   area_mean |   area_std |   measured |   measured_std |   eq2_calibrated |   eq2_c1_eq_c0 |   count_model |
|------------:|------------:|-----------:|-----------:|---------------:|-----------------:|---------------:|--------------:|
|        0    |      893.42 |       5.42 |       0    |           0    |             0    |           0    |          0    |
|        0.25 |      811.94 |      12.03 |      -9.12 |           1.24 |            16.74 |         -10.51 |         -4.92 |
|        0.5  |      727.28 |       3.29 |     -18.59 |           0.86 |            36.5  |         -22.93 |         -9.84 |
|        0.75 |      632.82 |       2.17 |     -29.17 |           0.19 |            61.03 |         -37.82 |        -14.76 |
|        1    |      507.56 |       1.8  |     -43.19 |           0.35 |            85.01 |         -52.2  |        -19.69 |

## Fitted cost model

```json
{
 "base_um2": 527.5615181678953,
 "c_nz_um2_per_nonzero_weight": 0.5309410063806415,
 "c_p2_um2_per_nonpow2_weight": 1.228079165629742,
 "r2": 0.9958549251697699,
 "n_runs": 45,
 "max_abs_err_um2": 25.00946580980542,
 "note": "layer 16x32, 8-bit, ASAP7 ORFS synth, clock 1000 ps; pow2 distance = sin^2(pi*log2|w|)"
}
```
