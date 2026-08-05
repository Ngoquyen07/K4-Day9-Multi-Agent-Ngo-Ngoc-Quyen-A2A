import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import time
from src.data_loader import OlistDataLoader

def test_data_loader():
    print("Testing OlistDataLoader initialization & performance...")
    start_time = time.time()
    loader = OlistDataLoader(data_dir="data")
    elapsed = time.time() - start_time
    print(f"Data Loaded and Indexed in {elapsed:.2f} seconds.")

    print(f"Total Orders: {len(loader.orders)}")
    print(f"Total Customers: {len(loader.customers)}")
    print(f"Total Products: {len(loader.products)}")
    print(f"Total Sellers: {len(loader.sellers)}")

    assert len(loader.orders) > 0, "Orders dataset should not be empty"
    assert len(loader.customers) > 0, "Customers dataset should not be empty"
    assert len(loader.items_by_order) > 0, "Items dataset should not be empty"
    assert len(loader.payments_by_order) > 0, "Payments dataset should not be empty"

    # Test sample lookup
    sample_order_id = next(iter(loader.orders.keys()))
    order = loader.get_order(sample_order_id)
    assert order is not None, f"Order {sample_order_id} should exist"
    print("\nSample Order:", order)

    customer_id = order["customer_id"]
    customer_unique_id = loader.get_customer_unique_id(customer_id)
    print(f"Customer ID: {customer_id} -> Customer Unique ID: {customer_unique_id}")
    assert customer_unique_id is not None, "Customer unique ID should not be None"

    items = loader.get_order_items(sample_order_id)
    payments = loader.get_order_payments(sample_order_id)
    related_orders = loader.get_related_orders(customer_unique_id, exclude_order_id=sample_order_id)

    print(f"Items count: {len(items)}")
    print(f"Payments count: {len(payments)}")
    print(f"Related Orders count: {len(related_orders)}")

    print("\nAll Data Loader Tests PASSED!")

if __name__ == "__main__":
    test_data_loader()
