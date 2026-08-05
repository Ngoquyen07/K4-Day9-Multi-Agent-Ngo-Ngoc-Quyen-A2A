from typing import Dict, Any, List
from src.data_loader import OlistDataLoader

class OrderProductAgent:
    """
    Order & Product Agent:
    Retrieves item IDs, seller IDs, product IDs, item total, freight total,
    expected total BRL, and translated category names.
    """

    def __init__(self, data_loader: OlistDataLoader):
        self.data_loader = data_loader

    def analyze(self, order_id: str, scope: Dict[str, Any]) -> Dict[str, Any]:
        include_product_ctx = scope.get("include_product_context", True)

        items = self.data_loader.get_order_items(order_id)

        item_ids = []
        product_ids = []
        seller_ids = []
        category_names = []

        item_total_brl = 0.0
        freight_total_brl = 0.0

        for item in items:
            seq = item.get("order_item_id")
            item_ids.append(f"{order_id}:{seq}")

            pid = str(item.get("product_id", ""))
            if pid and pid not in product_ids:
                product_ids.append(pid)

            sid = str(item.get("seller_id", ""))
            if sid and sid not in seller_ids:
                seller_ids.append(sid)

            price = float(item.get("price", 0.0))
            freight = float(item.get("freight_value", 0.0))

            item_total_brl += price
            freight_total_brl += freight

            if include_product_ctx and pid:
                prod = self.data_loader.get_product(pid)
                if prod:
                    cat_raw = prod.get("product_category_name")
                    cat_en = self.data_loader.get_category_english(cat_raw)
                    if cat_en and cat_en not in category_names:
                        category_names.append(cat_en)

        item_total_brl = round(item_total_brl, 2)
        freight_total_brl = round(freight_total_brl, 2)
        expected_total_brl = round(item_total_brl + freight_total_brl, 2)

        is_multi_item = len(items) > 1
        is_multi_seller = len(seller_ids) > 1
        is_multi_category = len(category_names) > 1

        return {
            "items": items,
            "item_ids": item_ids,
            "product_ids": product_ids,
            "seller_ids": seller_ids,
            "category_names": category_names,
            "item_total_brl": item_total_brl,
            "freight_total_brl": freight_total_brl,
            "expected_total_brl": expected_total_brl,
            "is_multi_item": is_multi_item,
            "is_multi_seller": is_multi_seller,
            "is_multi_category": is_multi_category,
        }
