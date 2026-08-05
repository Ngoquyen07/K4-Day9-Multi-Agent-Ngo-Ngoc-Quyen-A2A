from typing import Dict, Any, List
from src.data_loader import OlistDataLoader

class CustomerAgent:
    """
    Customer Agent:
    Retrieves customer identity (customer_unique_id) and historical/related orders.
    Enforces README limit: max 5 related_order_ids.
    """

    def __init__(self, data_loader: OlistDataLoader):
        self.data_loader = data_loader

    def analyze(self, order_id: str, scope: Dict[str, Any]) -> Dict[str, Any]:
        order = self.data_loader.get_order(order_id)
        if not order:
            return {
                "customer_unique_id": None,
                "related_order_ids": [],
                "has_repeat_customer": False,
            }

        customer_id = order.get("customer_id")
        customer_unique_id = self.data_loader.get_customer_unique_id(customer_id) if customer_id else None

        related_order_ids = []
        has_repeat_customer = False

        if customer_unique_id and scope.get("include_customer_history", True):
            related_orders = self.data_loader.get_related_orders(customer_unique_id, exclude_order_id=order_id)
            related_order_ids = [o["order_id"] for o in related_orders]
            has_repeat_customer = len(related_order_ids) > 0
            # Enforce max 5 related order IDs according to README schema limit
            related_order_ids = related_order_ids[:5]

        return {
            "customer_unique_id": customer_unique_id,
            "related_order_ids": related_order_ids,
            "has_repeat_customer": has_repeat_customer,
        }
