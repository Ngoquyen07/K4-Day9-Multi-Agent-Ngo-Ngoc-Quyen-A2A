from typing import Dict, Any, List
from src.data_loader import OlistDataLoader

class OrderProductAgent:
    """
    Order & Product Agent:
    Retrieves order items, sellers, products, categories, and item/freight totals.
    Enforces README array limits: max 5 items, max 3 sellers, max 5 products, max 5 categories.
    """

    def __init__(self, data_loader: OlistDataLoader):
        self.data_loader = data_loader

    def analyze(self, order_id: str, scope: Dict[str, Any]) -> Dict[str, Any]:
        items = self.data_loader.get_order_items(order_id)
        if not items:
            return {
                "items": [],
                "item_ids": [],
                "seller_ids": [],
                "product_ids": [],
                "category_names": [],
                "item_total_brl": None,
                "freight_total_brl": None,
                "expected_total_brl": None,
                "is_multi_item": False,
                "is_multi_seller": False,
                "is_multi_category": False,
            }

        item_ids = [f"{order_id}:{item['order_item_id']}" for item in items][:5]

        seller_set = []
        product_set = []
        category_set = []

        item_total_brl = 0.0
        freight_total_brl = 0.0

        for item in items:
            item_total_brl += item["price"]
            freight_total_brl += item["freight_value"]

            sid = item["seller_id"]
            if sid not in seller_set:
                seller_set.append(sid)

            pid = item["product_id"]
            if pid not in product_set:
                product_set.append(pid)

            if scope.get("include_product_context", True):
                cat = self.data_loader.get_category_name(pid)
                if cat and cat not in category_set:
                    category_set.append(cat)

        item_total_brl = round(item_total_brl, 2)
        freight_total_brl = round(freight_total_brl, 2)
        expected_total_brl = round(item_total_brl + freight_total_brl, 2)

        return {
            "items": items,
            "item_ids": item_ids,
            "seller_ids": seller_set[:3],
            "product_ids": product_set[:5],
            "category_names": category_set[:5],
            "item_total_brl": item_total_brl,
            "freight_total_brl": freight_total_brl,
            "expected_total_brl": expected_total_brl,
            "is_multi_item": len(items) >= 2,
            "is_multi_seller": len(seller_set) >= 2,
            "is_multi_category": len(category_set) >= 2,
        }
