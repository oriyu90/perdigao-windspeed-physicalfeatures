# Perdigão physics-feature attribution study v1.1 — public code & artifact release (anonymized)

> Status: **CALIBRATION_FAILED** (calibration gate not met; max detection 0.73) → primary analysis
> **not executed (withheld)**. This folder is an anonymized, data-free organization of a read-only
> copy of the internally frozen repository `perdigao_attribution_v1.1`
> (HEAD `e2e3563`, manifest `381b0422…`). The frozen original has not been modified.

## What this is (3 lines)

- **Question**: reproduce / test the claim of Vassallo et al. (2021, *Wind Energy Science*) that
  physics-based input features improve wind-speed forecasting error, using the Perdigão campaign
  tower tse13. Plan v1.1 re-runs the v1.0 study after fixing the group-definition bug
  (`P=Xp24` fitted alone → `P=R+Xp`).
- **Method**: an attribution design with synthetically planted signals (fully synthetic vs.
  partial-synthesis group comparisons), applied under a frozen protocol with named programs and
  dual-implementation concordance checks.
- **Result**: the calibration gate (detection ≥ 80% and FP ≤ 7.5%) **failed in all 9 conditions
  (max 0.73)** → the primary statistics on confirm data were never run and never unsealed
  (**DELIVERED, WITHHELD**).

## Layout

```
public_release/
├── README.md / README.en.md    ← this file (JP / EN)
├── LICENSE (MIT) / LICENSE-DOCS.md (CC BY 4.0)
├── CITATION.cff
├── code/                       ← runnable repo (same layout as the frozen original, paths scrubbed)
│   ├── src/perdigao_attr/  scripts/  tests/  configs/  environment/
│   ├── pyproject.toml  uv.lock  run_all.sh
│   └── data/README.md          ← how to obtain the data (not bundled)
├── docs/
│   ├── guides/                 ← phase guides, 8 files (00–05, 07–08; 06/09 are internal, not released)
│   ├── plan_v1.1.md            ← study plan (scrubbed)
│   └── provenance/             ← freeze info, integrity notes, scrub log
├── results/
│   ├── tables/                 ← calibration outputs (all 9 conditions)
│   ├── figures/                ← gate summary figures + sources
│   └── reports/                ← final report (md/html/pdf), executive summary, limitations
└── extras/
    └── dev_reference/          ← post-F6 exploratory measurement (development window only)
```

## Setup

```bash
cd code
uv sync --locked                  # Python 3.12; numpy 2.5.3 / pandas 3.0.6 / scikit-learn 1.9.1
uv run python -m pytest tests/ -q # 18/18 PASS (env/group/metric/time-contract/guard checks + bundled artifacts)
```

> Note: `run_all.sh` is an F1-era fail-closed stub. `./run_all.sh --frozen --from-raw`
> **stops with exit code 3 by design** (frozen-design enforcement; the full pipeline lives in
> `scripts/`). Use the staged commands below in this public copy.

Staged runs after obtaining the data (see `docs/guides/`):

```bash
uv run python scripts/p1_audit.py        # F2 data audit & freeze (builds data/raw + SHA ledger)
uv run python scripts/p2_reproduce.py    # F3 reproduction of the original study (~2h12m)
uv run python scripts/p4_calibrate_v11.py --bundle core4x1 --dforms quad,linear,regime --snrs 0.5,1.0 --reps 100 --resume  # F4 calibration gate → code/tables/
```

`scripts/p6_report_v11.py` (regenerating the F6 final report) expects the frozen-repo layout file
`code/manifests/freeze_manifest.json`, which is not bundled here; see the errata section in
`docs/provenance/provenance.md`.

## Data (not bundled)

Perdigão observations (NCAR EOL dataset **536.011**, DOI `10.26023/ZDMJ-D1TY-FG14`, **Version 1.2**)
are redistributed by license, not bundled. Ordering steps, time range, and integrity expectations
(175 files / 527,015,036 bytes / SHA-256 recorded) are in **`code/data/README.md`**.

## Results at a glance

| Item | Content | Files |
|---|---|---|
| Calibration gate | All 9 conditions FAIL (detection max 0.73 < 0.80; FP condition passed) | `tables/calibration_summary_core4x1_all.csv`, `figures/calibration_bars.png` |
| Raw calibration rows | 2,700 rows (9 × 300) | `tables/calibration_rows_core4x1.csv` |
| Final report | WITHHELD, 18/18 tests, delivered package | `reports/final_report.md` (authoritative: md; html identical; pdf is a 3-page print record — cover + 2 figures) |
| Code↔paper mapping | dual-implementation concordance | `docs/provenance/paper_code_concordance.md` (+ identical CSV) |

Note: the unsuffixed `tables/calibration_results_core4x1.csv`, `tables/calibration_summary_core4x1.csv`,
and `reports/calibration_core4x1.md` are artifacts of a **5-rep pilot (smoke) run** (run_id
`2026-10-10T002428`, n_valid=5). The official 100-rep values are in
`calibration_summary_core4x1_all.csv` and the `calibration_*_{dform}_{m}.*` files (pilot
quad/mobs SNR1.0 detection is 0.8; the official value is 0.73). A matching annotation is
prepended to `reports/calibration_core4x1.md`.

## License & citation

- **Code (code/)**: [MIT](LICENSE)
- **Docs, figures, tables**: [CC BY 4.0](LICENSE-DOCS.md) — code files (`*.py`, also under
  `extras/dev_reference/scripts/`) are MIT regardless of location
- See `CITATION.cff`. You must cite the source paper
  **Vassallo, D., Krishnamurthy, R., and Fernando, H. J. S. (2021), Wind Energy Science 6, 295–309,
  DOI: 10.5194/wes-6-295-2021** and the dataset **NCAR EOL 536.011 (DOI: 10.26023/ZDMJ-D1TY-FG14)**.
  The original authors' reference code (`dvassall/Forecasting_Error_Codes`) is referenced only
  (no license stated; not copied or redistributed).

## Scope of interpretation

Per the ban list in `docs/plan_v1.1.md` (§F6), the study asks a narrowly scoped question about a
physics-specific inductive bias under finite samples with named models. No causal claims, no
"physics helps / physics is useless" claims, and no operational or generalization claims are made
anywhere in the reports.

## Anonymization & modifications

- Usernames, absolute paths, and internal session records have been removed (log in
  `docs/provenance/provenance.md`). Of the 14 files covered by the freeze manifest,
  `audit/paper_code_concordance.csv` is exempt from hash checks by the freeze rule; of the
  remaining 13, **12 are bundled here and byte-identical to the frozen original**
  (5 `code/configs/*` + `code/uv.lock`, the tables `sites.csv` / `missing_audit.csv` under
  `results/tables/`, and 3 `audit/*` + `manifests/splits.parquet` inside
  `freeze_bundle_public.zip`). The last one, `manifests/raw_files.jsonl`
  (SHA ledger of the 175 raw data files), is not bundled — verify it against the frozen original.
  `scripts/p1_audit.py` constants, the artifact paths in 2 `code/tests/` files (adapted to the
  public `results/` layout; see the provenance addendum), and in-text paths in `docs/` were also
  altered, so
  re-verification of the freeze against *this public copy alone* is not meaningful (see provenance).
- `extras/dev_reference/` is an exploratory, non-preregistered reference measurement on the
  development window with real target values; it does **not** change the shipped verdicts
  (CALIBRATION_FAILED / DELIVERED / WITHHELD).
- `docs/plan_v1.1.md` still references internal session guides (06/09) that are not included
  in this release.
