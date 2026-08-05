from typing import Dict, Any, List
from src.data_loader import OlistDataLoader

class CustomerAgent:
    """
    Customer Agent:
    Investigates customer identity, customer_unique_id, and related order history.
    """

    def __init__(self, data_loader: OlistDataLoader):
        self.data_loader = data_loader

    def analyze(self, order_id: str, scope: Dict[str, Any]) -> Dict[str, Any]:
        include_history = scope.get("include_customer_history", True)

        order = self.data_loader.get_order(order_id)
        if not order:
            return {
                "customer_unique_id": "",
                "related_order_ids": [],
                "has_repeat_customer": False,
            }

        customer_id = str(order.get("customer_id", ""))
        customer = self.data_loader.get_customer_by_id(customer_id)
        customer_unique_id = str(customer.get("customer_unique_id", "")) if customer else ""

        related_order_ids = []
        if include_history and customer_unique_id:
            all_orders = self.data_loader.get_customer_orders(customer_unique_id)
            related_order_ids = [oid for oid in all_orders if oid != order_id]

        has_repeat_customer = len(related_order_ids) > 0

        return {
            "customer_unique_id": customer_unique_id,
            "related_order_ids": related_order_ids,
            "has_repeat_customer": has_repeat_customer,
        }
