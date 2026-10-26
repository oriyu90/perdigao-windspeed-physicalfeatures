import pandas as pd
import pytest


def test_time_contract_valid_and_invalid():
    from perdigao_attr.data.fixture import build_issue_frame
    from perdigao_attr.time_contract import validate_frame

    df = build_issue_frame(n=8)
    assert len(df) == 8  # validates on build

    bad = df.copy()
    bad.loc[bad.index[0], "max_input_time"] = bad.loc[bad.index[0], "issue_time"] + pd.Timedelta(minutes=5)
    with pytest.raises(ValueError, match="time-contract"):
        validate_frame(bad)

    bad2 = df.copy()
    bad2.loc[bad2.index[1], "target_start"] = bad2.loc[bad2.index[1], "issue_time"]
    with pytest.raises(ValueError, match="time-contract"):
        validate_frame(bad2)
