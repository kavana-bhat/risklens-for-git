from payment import process_payment


def create_order(amount):
    payment = process_payment(amount)

    if payment == "Payment processed":
        return amount + 18

    return 0


def cancel_order(order_id):
    return "Order cancelled: " + str(order_id)