"""
Creates a small Git repo with a realistic history so you can demo the tool.

    python demo/make_demo_repo.py /tmp/shop-demo
    python main.py --repo /tmp/shop-demo --commit HEAD

The last commit adds a coupon feature through three layers (pricing -> cart ->
checkout) and edits `add_tax`. Only the old checkout path has a test, so the
TEST GAP ANALYSIS section has real gaps to find.
"""
import os
import subprocess
import sys

dest = sys.argv[1] if len(sys.argv) > 1 else "shop-demo"
os.makedirs(dest, exist_ok=True)


def git(*args):
    subprocess.run(["git", *args], cwd=dest, check=True,
                   capture_output=True, text=True)


def write(path, text):
    full = os.path.join(dest, path)
    os.makedirs(os.path.dirname(full) or dest, exist_ok=True)
    with open(full, "w") as fh:
        fh.write(text)


def commit(msg):
    git("add", "-A")
    git("-c", "user.name=Demo", "-c", "user.email=demo@example.com",
        "commit", "-m", msg)


git("init", "-q")

write("shop/__init__.py", "")
write("shop/pricing.py", '''def apply_discount(price, percent):
    return price - price * percent / 100


def add_tax(price, rate=0.18):
    return price + price * rate
''')
write("shop/cart.py", '''from shop.pricing import add_tax, apply_discount


def total(items, discount=0):
    subtotal = sum(items)
    return add_tax(apply_discount(subtotal, discount))
''')
write("shop/checkout.py", '''from shop.cart import total


def checkout(items, discount=0):
    amount = total(items, discount)
    return {"status": "paid", "amount": round(amount, 2)}


def refund(order_id):
    return {"status": "refunded", "order": order_id}
''')
write("tests/test_checkout.py", '''from shop.checkout import checkout


def test_checkout_simple():
    assert checkout([100])["status"] == "paid"
''')
commit("Initial shop")

write("shop/pricing.py", '''def apply_discount(price, percent):
    return price - price * percent / 100


def add_tax(price, rate=0.18):
    return price + price * rate


def free_shipping(price):
    return price > 50
''')
commit("Add free shipping rule")

write("shop/pricing.py", '''def apply_discount(price, percent):
    if percent < 0 or percent > 100:
        raise ValueError("bad discount")
    return price - price * percent / 100


def add_tax(price, rate=0.18):
    return price + price * rate


def free_shipping(price):
    return price > 50
''')
commit("Validate discount range")

write("shop/pricing.py", '''def apply_discount(price, percent):
    if percent < 0 or percent > 100:
        raise ValueError("bad discount")
    return price - price * percent / 100


def add_tax(price, rate=0.18):
    return round(price + price * rate, 2)


def free_shipping(price):
    return price > 50


def apply_coupon(price, code):
    if code == "SAVE10":
        return price - 10
    return price
''')
write("shop/cart.py", '''from shop.pricing import add_tax, apply_coupon, apply_discount


def total(items, discount=0):
    subtotal = sum(items)
    return add_tax(apply_discount(subtotal, discount))


def total_with_coupon(items, code):
    return add_tax(apply_coupon(sum(items), code))
''')
write("shop/checkout.py", '''from shop.cart import total, total_with_coupon


def checkout(items, discount=0):
    amount = total(items, discount)
    return {"status": "paid", "amount": round(amount, 2)}


def checkout_with_coupon(items, code):
    amount = total_with_coupon(items, code)
    return {"status": "paid", "amount": round(amount, 2)}


def refund(order_id):
    return {"status": "refunded", "order": order_id}
''')
commit("Add coupon support")
print("demo repo created at", dest)
