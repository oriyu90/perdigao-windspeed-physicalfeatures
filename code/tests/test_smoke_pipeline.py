import hashlib


def test_fixture_hash_stable_same_seed(tmp_path):
    import xarray as xr

    from perdigao_attr.data.fixture import build_issue_frame, make_fixture

    p1 = tmp_path / "a.nc"
    p2 = tmp_path / "b.nc"
    make_fixture(p1, seed_index=0)
    make_fixture(p2, seed_index=0)
    h1 = hashlib.sha256(p1.read_bytes()).hexdigest()
    h2 = hashlib.sha256(p2.read_bytes()).hexdigest()
    assert h1 == h2

    # content sanity: 5-min monotonic time, required vars
    ds = xr.open_dataset(p1, engine="netcdf4")
    assert {"U100", "U20"} <= set(ds.variables)
    dt = ds["time"].to_index().to_series().diff().dropna().unique()
    assert len(dt) == 1 and dt[0].total_seconds() == 300
    ds.close()

    # issue frame obeys contract
    df = build_issue_frame(n=12)
    assert ((df["max_input_time"] <= df["issue_time"]) & (df["issue_time"] < df["target_start"])).all()
