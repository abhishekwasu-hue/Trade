# नकाशा A1: "अंदाज" आकड्यांची IS sensitivity (फक्त अहवाल)

IS random 40 दिवस (seed 20261009). निकाल hindsight फक्त गटांसाठी: SL = structural invalidation ∓ 0.25 MR, target 3R, ≤ 3 sessions. **कोणतंही मूल्य निवडलं नाही.**

Baseline: {'signals': 17, 'TARGET': 3, 'SL': 12, 'TIME': 2, 'exp_R': -0.24}

## `commitment_vs_pause` (आत्ता 1.5)

| मूल्य | signals | TARGET | SL | TIME | exp R | Jaccard (baseline शी) |
|---|---|---|---|---|---|---|
| 1.3 | 20 | 3 | 14 | 3 | -0.24 | 0.85 |
| 1.5 | 17 | 3 | 12 | 2 | -0.24 | 1.0 |
| 2.0 | 9 | 2 | 4 | 3 | 0.27 | 0.37 |

## `area_tol_mr` (आत्ता 0.3)

| मूल्य | signals | TARGET | SL | TIME | exp R | Jaccard (baseline शी) |
|---|---|---|---|---|---|---|
| 0.2 | 15 | 3 | 10 | 2 | -0.14 | 0.88 |
| 0.3 | 17 | 3 | 12 | 2 | -0.24 | 1.0 |
| 0.4 | 19 | 4 | 12 | 3 | -0.05 | 0.89 |

## `commit_strength_min_mr` (आत्ता 1.2)

| मूल्य | signals | TARGET | SL | TIME | exp R | Jaccard (baseline शी) |
|---|---|---|---|---|---|---|
| 1.0 | 14 | 3 | 9 | 2 | -0.08 | 0.82 |
| 1.2 | 17 | 3 | 12 | 2 | -0.24 | 1.0 |
| 1.5 | 12 | 3 | 7 | 2 | 0.08 | 0.45 |

## `pause_range_max_mr` (आत्ता 1.0)

| मूल्य | signals | TARGET | SL | TIME | exp R | Jaccard (baseline शी) |
|---|---|---|---|---|---|---|
| 0.8 | 15 | 3 | 9 | 3 | 0.01 | 0.68 |
| 1.0 | 17 | 3 | 12 | 2 | -0.24 | 1.0 |
| 1.2 | 18 | 3 | 14 | 1 | -0.31 | 0.67 |

## `pause_body_max` (आत्ता 0.5)

| मूल्य | signals | TARGET | SL | TIME | exp R | Jaccard (baseline शी) |
|---|---|---|---|---|---|---|
| 0.4 | 18 | 3 | 12 | 3 | -0.16 | 0.94 |
| 0.5 | 17 | 3 | 12 | 2 | -0.24 | 1.0 |
| 0.6 | 18 | 3 | 13 | 2 | -0.28 | 0.94 |

## `commit_close_max` (आत्ता 0.3)

| मूल्य | signals | TARGET | SL | TIME | exp R | Jaccard (baseline शी) |
|---|---|---|---|---|---|---|
| 0.2 | 15 | 3 | 10 | 2 | -0.14 | 0.78 |
| 0.3 | 17 | 3 | 12 | 2 | -0.24 | 1.0 |
| 0.4 | 18 | 3 | 13 | 2 | -0.28 | 0.94 |

**सापेक्ष तुलनेचा प्रस्ताव (Abhi निर्णय):** area_tol / commit strength / pause range आधीच MR (median range, अलीकडच्या 20 bars) च्या पटीत आहेत — म्हणजे बाजाराच्या अलीकडच्या चालीशी सापेक्ष. commitment_vs_pause हा pause bars शी सापेक्ष. उरलेला प्रश्न: MR ऐवजी impulse आकाराशी (उदा. touch = impulse च्या x%) तुलना हवी का — अहवालानंतर ठरवायचं.
