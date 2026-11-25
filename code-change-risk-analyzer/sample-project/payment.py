
def process_payment(amount):
    if amount <= 0:
   def validate_payment(amount):
    if amount > 0:
        return True
    return False


def process_payment(amount):
    if validate_payment(amount):
        return "Payment processed"
    return "Invalid payment"


def refund_payment(amount):
    if amount > 0:
        return "Refund processed"
    return "Invalid refund"     return 0

    return amount * 1.18