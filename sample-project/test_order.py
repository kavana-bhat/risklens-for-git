from order import create_order


def test_create_order():
    result = create_order(100)
    assert result == 118