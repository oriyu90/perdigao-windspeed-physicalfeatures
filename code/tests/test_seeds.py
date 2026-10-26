def test_seeds_deterministic_and_namespaced():
    from perdigao_attr.seeds import derive_generator, derive_seed

    a = derive_seed(2026091501, "split", 0)
    b = derive_seed(2026091501, "split", 0)
    c = derive_seed(2026091501, "split", 1)
    d = derive_seed(2026091501, "rf", 0)
    assert a == b
    assert a != c
    assert a != d
    g1 = derive_generator(2026091501, "bootstrap", 3).normal(size=5)
    g2 = derive_generator(2026091501, "bootstrap", 3).normal(size=5)
    assert list(g1) == list(g2)

    import pytest

    with pytest.raises(ValueError):
        derive_seed(2026091501, "unknown_ns", 0)
