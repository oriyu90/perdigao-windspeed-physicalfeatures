"""v1.1 group-definition regression tests (F1 mandatory, F4 re-verified).

Contracts from PLAN_v1.1 sec.6:
- total dim: Xrp_total == Xrs_total == Xrg_total (R included).
- added: core4x1 +4/48, top6x2 +12/56, full24 +24/68.
- common mask identical across groups.
- P_only fit path banned (legacy v1.0 bug: rf_p on Xp24 alone).
- scaler note: median/IQR fit separately per group per fold-train (doc contract).
"""
import numpy as np
import pytest
import yaml
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Public-release copy: the revised concordance CSV lives under ../docs/provenance
# (frozen-repo layout keeps it in REPO/audit). The frozen layout wins when it exists.
AUDIT = REPO / "audit" if (REPO / "audit").exists() else REPO.parent / "docs" / "provenance"


def test_group_total_added_dims():
    from perdigao_attr.groups import BUNDLES, build_design_matrices

    assert BUNDLES["core4x1"]["added"] == 4 and BUNDLES["core4x1"]["total"] == 48
    assert BUNDLES["top6x2"]["added"] == 12 and BUNDLES["top6x2"]["total"] == 56
    assert BUNDLES["full24"]["added"] == 24 and BUNDLES["full24"]["total"] == 68
    for bundle in ("core4x1", "top6x2", "full24"):
        d = build_design_matrices(n_rows=64, bundle=bundle)
        # total dim一致 (R込み)
        assert d["Xrp"].shape[1] == d["Xrs"].shape[1] == d["Xrg"].shape[1] == d["total"]
        # added一致
        assert d["Xp"].shape[1] == d["Xs"].shape[1] == d["Xg"].shape[1] == d["added"]
        # R+Xp 連結であること (単独Xpではない)
        assert d["Xrp"].shape[1] == 44 + d["added"]


def test_common_mask_identical():
    from perdigao_attr.groups import build_design_matrices, common_mask

    d = build_design_matrices(n_rows=96, bundle="core4x1")
    m = d["common_mask"]
    assert m.dtype == bool and m.shape == (96,)
    # mask は全群の有限行から同一に計算される
    m2 = common_mask(d["Xrp"], d["Xrs"], d["Xrg"])
    assert (m == m2).all()
    # NaN を混ぜると同一に落ちる
    d2 = build_design_matrices(n_rows=32, bundle="full24")
    Xrp = d2["Xrp"].copy()
    Xrp[0, 0] = np.nan
    m3 = common_mask(Xrp, d2["Xrs"], d2["Xrg"])
    assert not m3[0] and m3.sum() == 31


def test_p_only_path_banned():
    from perdigao_attr import groups

    with pytest.raises(RuntimeError, match="P_ONLY_BANNED"):
        groups.fit_p_only(np.zeros((8, 24)))
    # 旧 run_rep_fold の単独Xp分岐が残っていないこと (文字列監査)
    src = (REPO / "src" / "perdigao_attr" / "groups.py").read_text()
    assert "P_ONLY_BANNED" in src
    assert "R+Xp" in src


def test_p_subset_and_feature_dag_consistent():
    dag = yaml.safe_load((REPO / "configs" / "feature_dag.yaml").read_text())
    assert len(dag["features"]) == 12
    assert "group_definition" in dag["rules"] and "R+Xp" in dag["rules"]["group_definition"]
    sub = yaml.safe_load((REPO / "configs" / "p_subset.yaml").read_text())
    assert sub["core4x1"]["added"] == 4 and sub["core4x1"]["total"] == 48
    assert sub["top6x2"]["added"] == 12 and sub["top6x2"]["total"] == 56
    assert sub["full24"]["added"] == 24 and sub["full24"]["total"] == 68
    assert set(sub["core4x1"]["features"]) == {"TI", "N2", "Ri_g", "tke"}
    assert set(sub["top6x2"]["features"]) == {"TI", "N2", "Ri_g", "Ri_f", "tke", "u_star_norm"}


def test_paper_code_concordance_has_six_plus_items():
    import csv

    with open(AUDIT / "paper_code_concordance.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 12
    assert {"MATCH", "CONFLICT", "PAPER_ONLY", "CODE_ONLY", "UNSPECIFIED"} >= set(r["verdict"] for r in rows)
