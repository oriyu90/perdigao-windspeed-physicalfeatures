import math


def test_rmse_mae_fixture():
    from perdigao_attr.metrics import legacy_labelled_rmse, mae, rmse

    assert rmse([0, 3, 4]) == math.sqrt(25 / 3)
    assert mae([0, 3, 4]) == 7 / 3
    # legacy misnomer equals MAE, not RMSE
    assert legacy_labelled_rmse([0, 3, 4]) == mae([0, 3, 4])
    assert legacy_labelled_rmse([0, 3, 4]) != rmse([0, 3, 4])
