import os
import pandas as pd
from typing import Dict, Any, List, Optional

class OlistDataLoader:
    """
    Olist Data Loader:
    Indexes 9 Olist CSV files in data/ into memory Hash Maps for O(1) retrieval.
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir

        self.orders: Dict[str, Dict[str, Any]] = {}
        self.customers: Dict[str, Dict[str, Any]] = {}
        self.customer_orders_map: Dict[str, List[str]] = {}
        self.order_items_map: Dict[str, List[Dict[str, Any]]] = {}
        self.order_payments_map: Dict[str, List[Dict[str, Any]]] = {}
        self.products: Dict[str, Dict[str, Any]] = {}
        self.sellers: Dict[str, Dict[str, Any]] = {}
        self.category_translation: Dict[str, str] = {}

        self._load_all()

    def _load_all(self):
        # 1. Category translations
        trans_path = os.path.join(self.data_dir, "product_category_name_translation.csv")
        if os.path.exists(trans_path):
            df_trans = pd.read_csv(trans_path)
            for _, row in df_trans.iterrows():
                pt = str(row["product_category_name"]).strip()
                en = str(row["product_category_name_english"]).strip()
                self.category_translation[pt] = en

        # 2. Customers
        cust_path = os.path.join(self.data_dir, "olist_customers_dataset.csv")
        if os.path.exists(cust_path):
            df_cust = pd.read_csv(cust_path)
            for rec in df_cust.to_dict("records"):
                cid = str(rec["customer_id"])
                self.customers[cid] = rec

        # 3. Orders
        ord_path = os.path.join(self.data_dir, "olist_orders_dataset.csv")
        if os.path.exists(ord_path):
            df_ord = pd.read_csv(ord_path)
            for rec in df_ord.to_dict("records"):
                oid = str(rec["order_id"])
                self.orders[oid] = rec

                cid = str(rec["customer_id"])
                cust = self.customers.get(cid)
                if cust:
                    cuniq = str(cust.get("customer_unique_id", ""))
                    if cuniq:
                        if cuniq not in self.customer_orders_map:
                            self.customer_orders_map[cuniq] = []
                        self.customer_orders_map[cuniq].append(oid)

        # 4. Order Items
        items_path = os.path.join(self.data_dir, "olist_order_items_dataset.csv")
        if os.path.exists(items_path):
            df_items = pd.read_csv(items_path)
            for rec in df_items.to_dict("records"):
                oid = str(rec["order_id"])
                if oid not in self.order_items_map:
                    self.order_items_map[oid] = []
                self.order_items_map[oid].append(rec)

        # 5. Order Payments
        pay_path = os.path.join(self.data_dir, "olist_order_payments_dataset.csv")
        if os.path.exists(pay_path):
            df_pay = pd.read_csv(pay_path)
            for rec in df_pay.to_dict("records"):
                oid = str(rec["order_id"])
                if oid not in self.order_payments_map:
                    self.order_payments_map[oid] = []
                self.order_payments_map[oid].append(rec)

        # 6. Products
        prod_path = os.path.join(self.data_dir, "olist_products_dataset.csv")
        if os.path.exists(prod_path):
            df_prod = pd.read_csv(prod_path)
            for rec in df_prod.to_dict("records"):
                pid = str(rec["product_id"])
                self.products[pid] = rec

        # 7. Sellers
        sell_path = os.path.join(self.data_dir, "olist_sellers_dataset.csv")
        if os.path.exists(sell_path):
            df_sell = pd.read_csv(sell_path)
            for rec in df_sell.to_dict("records"):
                sid = str(rec["seller_id"])
                self.sellers[sid] = rec

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        return self.orders.get(order_id)

    def get_customer_by_id(self, customer_id: str) -> Optional[Dict[str, Any]]:
        return self.customers.get(customer_id)

    def get_customer_orders(self, customer_unique_id: str) -> List[str]:
        return self.customer_orders_map.get(customer_unique_id, [])

    def get_order_items(self, order_id: str) -> List[Dict[str, Any]]:
        return self.order_items_map.get(order_id, [])

    def get_order_payments(self, order_id: str) -> List[Dict[str, Any]]:
        return self.order_payments_map.get(order_id, [])

    def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        return self.products.get(product_id)

    def get_seller(self, seller_id: str) -> Optional[Dict[str, Any]]:
        return self.sellers.get(seller_id)

    def get_category_english(self, category_raw: str) -> str:
        if not category_raw or pd.isna(category_raw):
            return "unknown"
        cat_str = str(category_raw).strip()
        return self.category_translation.get(cat_str, cat_str)
