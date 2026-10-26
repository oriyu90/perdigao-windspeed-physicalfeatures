import pytest


def test_confirm_guard_blocks_before_unseal():
    from perdigao_attr import confirm_guard

    assert not confirm_guard.is_unsealed()
    with pytest.raises(PermissionError, match="CONFIRM_GUARD"):
        confirm_guard.confirm_target_summary()
    with pytest.raises(PermissionError, match="sealed"):
        confirm_guard.require_unsealed()
