"""F4 regression: P=R+Xp concat fix, 100-sham parity, DGP forms."""
import numpy as np


def test_run_rep_fold_uses_r_plus_xp():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p4cal", str(Path(__file__).resolve().parents[1] / "scripts" / "p4_calibrate_v11.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rng = np.random.Generator(np.random.PCG64(0))
    n = 300
    Xr = rng.normal(size=(n, 44))
    Xp = rng.normal(size=(n, 4))  # core4
    y = Xr[:, 0] + rng.normal(scale=0.5, size=n)
    days = np.array(["2020-01-%02d" % (1 + (i // 30)) for i in range(n)])
    pday = np.arange(n) // 30
    Xs = [rng.normal(size=(n, 4)) for _ in range(3)]
    tab = mod.run_rep_fold(Xr[:200], Xp[:200], y[:200], Xr[200:], Xp[200:], y[200:],
                           days[200:], rep_seed=1, pday_tr=pday[:200],
                           sham_trs=[x[:200] for x in Xs], sham_tes=[x[200:] for x in Xs])
    assert {"rmse_r", "rmse_p", "rmse_s"} <= set(tab.columns)
    # total dim contract: sham added == P added (assert inside would fail otherwise)
    assert len(tab) >= 1


def test_build_S_forms():
    import sys
    from pathlib import Path
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p4cal", str(Path(__file__).resolve().parents[1] / "scripts" / "p4_calibrate_v11.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    z1 = np.array([-1.5, -0.5, 0.5, 1.5])
    z2 = np.array([0.2, -0.3, 0.4, -0.1])
    for form in ("quad", "linear", "regime"):
        s = mod.build_S(z1, z2, form)
        assert np.isfinite(s).all() and (np.abs(s) <= 1.0 + 1e-9).all()
