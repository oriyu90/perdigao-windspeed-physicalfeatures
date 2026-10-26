def test_imports_and_version():
    import sys

    import perdigao_attr

    assert sys.version_info[:2] == (3, 12), f"must run under Python 3.12, got {sys.version}"
    assert perdigao_attr.MASTER_SEED == 2026091501
