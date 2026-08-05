import os
import pandas as pd
from typing import Dict, List, Any, Optional

class OlistDataLoader:
    """
    Ultra-Fast Data Loader and Indexer for Olist Dataset.
    Uses vectorized pandas conversions to build O(1) hash maps in < 1 second.
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir

        self.orders: Dict[str, Dict[str, Any]] = {}
        self.customers: Dict[str, Dict[str, Any]] = {}
        self.customer_unique_map: Dict[str, List[str]] = {}
        self.customer_orders_map: Dict[str, List[Dict[str, Any]]] = {}
        self.items_by_order: Dict[str, List[Dict[str, Any]]] = {}
        self.payments_by_order: Dict[str, List[Dict[str, Any]]] = {}
        self.products: Dict[str, Dict[str, Any]] = {}
        self.sellers: Dict[str, Dict[str, Any]] = {}
        self.category_translation: Dict[str, str] = {}

        self._load_data()

    def _load_data(self):
        """Ultra-fast loading using to_dict('records')."""
        # 1. Category translation
        trans_file = os.path.join(self.data_dir, "product_category_name_translation.csv")
        if os.path.exists(trans_file):
            df_trans = pd.read_csv(trans_file)
            for rec in df_trans.to_dict('records'):
                if pd.notna(rec.get("product_category_name")) and pd.notna(rec.get("product_category_name_english")):
                    self.category_translation[str(rec["product_category_name"])] = str(rec["product_category_name_english"])

        # 2. Products
        products_file = os.path.join(self.data_dir, "olist_products_dataset.csv")
        if os.path.exists(products_file):
            df_prod = pd.read_csv(products_file)
            for rec in df_prod.to_dict('records'):
                pid = str(rec["product_id"])
                cat_raw = rec.get("product_category_name")
                cat_name = self.category_translation.get(str(cat_raw), str(cat_raw)) if pd.notna(cat_raw) else None
                self.products[pid] = {
                    "product_id": pid,
                    "product_category_name_raw": str(cat_raw) if pd.notna(cat_raw) else None,
                    "product_category_name": cat_name,
                }

        # 3. Sellers
        sellers_file = os.path.join(self.data_dir, "olist_sellers_dataset.csv")
        if os.path.exists(sellers_file):
            df_sellers = pd.read_csv(sellers_file)
            for rec in df_sellers.to_dict('records'):
                sid = str(rec["seller_id"])
                self.sellers[sid] = {
                    "seller_id": sid,
                    "seller_zip_code_prefix": int(rec["seller_zip_code_prefix"]) if pd.notna(rec.get("seller_zip_code_prefix")) else None,
                    "seller_city": str(rec["seller_city"]) if pd.notna(rec.get("seller_city")) else None,
                    "seller_state": str(rec["seller_state"]) if pd.notna(rec.get("seller_state")) else None,
                }

        # 4. Customers
        customers_file = os.path.join(self.data_dir, "olist_customers_dataset.csv")
        if os.path.exists(customers_file):
            df_cust = pd.read_csv(customers_file)
            for rec in df_cust.to_dict('records'):
                cid = str(rec["customer_id"])
                cuniq = str(rec["customer_unique_id"])
                cust_dict = {
                    "customer_id": cid,
                    "customer_unique_id": cuniq,
                    "customer_city": str(rec["customer_city"]) if pd.notna(rec.get("customer_city")) else None,
                    "customer_state": str(rec["customer_state"]) if pd.notna(rec.get("customer_state")) else None,
                }
                self.customers[cid] = cust_dict
                if cuniq not in self.customer_unique_map:
                    self.customer_unique_map[cuniq] = []
                self.customer_unique_map[cuniq].append(cid)

        # 5. Orders
        orders_file = os.path.join(self.data_dir, "olist_orders_dataset.csv")
        if os.path.exists(orders_file):
            df_orders = pd.read_csv(orders_file)
            for rec in df_orders.to_dict('records'):
                oid = str(rec["order_id"])
                cid = str(rec["customer_id"])
                order_dict = {
                    "order_id": oid,
                    "customer_id": cid,
                    "order_status": str(rec["order_status"]) if pd.notna(rec.get("order_status")) else None,
                    "order_purchase_timestamp": str(rec["order_purchase_timestamp"]) if pd.notna(rec.get("order_purchase_timestamp")) else None,
                    "order_approved_at": str(rec["order_approved_at"]) if pd.notna(rec.get("order_approved_at")) else None,
                    "order_delivered_carrier_date": str(rec["order_delivered_carrier_date"]) if pd.notna(rec.get("order_delivered_carrier_date")) else None,
                    "order_delivered_customer_date": str(rec["order_delivered_customer_date"]) if pd.notna(rec.get("order_delivered_customer_date")) else None,
                    "order_estimated_delivery_date": str(rec["order_estimated_delivery_date"]) if pd.notna(rec.get("order_estimated_delivery_date")) else None,
                }
                self.orders[oid] = order_dict

                cust_info = self.customers.get(cid)
                if cust_info:
                    cuniq = cust_info["customer_unique_id"]
                    if cuniq not in self.customer_orders_map:
                        self.customer_orders_map[cuniq] = []
                    self.customer_orders_map[cuniq].append(order_dict)

        # 6. Order items
        items_file = os.path.join(self.data_dir, "olist_order_items_dataset.csv")
        if os.path.exists(items_file):
            df_items = pd.read_csv(items_file)
            for rec in df_items.to_dict('records'):
                oid = str(rec["order_id"])
                item_dict = {
                    "order_id": oid,
                    "order_item_id": int(rec["order_item_id"]),
                    "product_id": str(rec["product_id"]),
                    "seller_id": str(rec["seller_id"]),
                    "shipping_limit_date": str(rec["shipping_limit_date"]) if pd.notna(rec.get("shipping_limit_date")) else None,
                    "price": float(rec["price"]),
                    "freight_value": float(rec["freight_value"]),
                }
                if oid not in self.items_by_order:
                    self.items_by_order[oid] = []
                self.items_by_order[oid].append(item_dict)

        # 7. Order payments
        payments_file = os.path.join(self.data_dir, "olist_order_payments_dataset.csv")
        if os.path.exists(payments_file):
            df_payments = pd.read_csv(payments_file)
            for rec in df_payments.to_dict('records'):
                oid = str(rec["order_id"])
                pay_dict = {
                    "order_id": oid,
                    "payment_sequential": int(rec["payment_sequential"]),
                    "payment_type": str(rec["payment_type"]),
                    "payment_installments": int(rec["payment_installments"]),
                    "payment_value": float(rec["payment_value"]),
                }
                if oid not in self.payments_by_order:
                    self.payments_by_order[oid] = []
                self.payments_by_order[oid].append(pay_dict)

    # --- Fast Lookup API ---

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        return self.orders.get(order_id)

    def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        return self.customers.get(customer_id)

    def get_customer_unique_id(self, customer_id: str) -> Optional[str]:
        cust = self.customers.get(customer_id)
        return cust["customer_unique_id"] if cust else None

    def get_related_orders(self, customer_unique_id: str, exclude_order_id: Optional[str] = None) -> List[Dict[str, Any]]:
        orders = self.customer_orders_map.get(customer_unique_id, [])
        if exclude_order_id:
            return [o for o in orders if o["order_id"] != exclude_order_id]
        return orders

    def get_order_items(self, order_id: str) -> List[Dict[str, Any]]:
        return self.items_by_order.get(order_id, [])

    def get_order_payments(self, order_id: str) -> List[Dict[str, Any]]:
        return self.payments_by_order.get(order_id, [])

    def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        return self.products.get(product_id)

    def get_category_name(self, product_id: str) -> Optional[str]:
        prod = self.products.get(product_id)
        return prod["product_category_name"] if prod else None

    def get_seller(self, seller_id: str) -> Optional[Dict[str, Any]]:
        return self.sellers.get(seller_id)
