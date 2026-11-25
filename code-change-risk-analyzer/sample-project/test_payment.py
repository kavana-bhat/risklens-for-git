from payment import process_payment


def test_valid_payment():
    result = process_payment(100)
    assert result == 118


def test_invalid_payment():
    result = process_payment(-100)
    assert result == 0