import pandas as pd
from typing import Dict, Any, List, Optional
from src.data_loader import OlistDataLoader

class DeliveryAgent:
    """
    Delivery Agent:
    Analyzes delivery timestamps, delivery variance hours, and seller handoff SLA compliance.
    """

    def __init__(self, data_loader: OlistDataLoader):
        self.data_loader = data_loader

    def analyze(self, order_id: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        order = self.data_loader.get_order(order_id)
        if not order:
            return {
                "delivered_at": None,
                "estimated_delivery_at": None,
                "carrier_handoff_at": None,
                "delivery_variance_hours": None,
                "seller_handoff_analysis": [],
                "late_handoff_seller_ids": [],
                "is_late_delivery": False,
                "has_late_seller_handoff": False,
            }

        delivered_at_raw = order.get("order_delivered_customer_date")
        estimated_at_raw = order.get("order_estimated_delivery_date")
        carrier_handoff_raw = order.get("order_delivered_carrier_date")

        delivered_at = str(delivered_at_raw) if pd.notna(delivered_at_raw) else None
        estimated_delivery_at = str(estimated_at_raw) if pd.notna(estimated_at_raw) else None
        carrier_handoff_at = str(carrier_handoff_raw) if pd.notna(carrier_handoff_raw) else None

        delivery_variance_hours = None
        is_late_delivery = False

        if delivered_at and estimated_delivery_at:
            dt_del = pd.to_datetime(delivered_at)
            dt_est = pd.to_datetime(estimated_delivery_at)
            variance_sec = (dt_del - dt_est).total_seconds()
            delivery_variance_hours = round(variance_sec / 3600.0, 2)
            if delivery_variance_hours > 0:
                is_late_delivery = True

        seller_handoff_analysis = []
        late_handoff_seller_ids = []

        for item in items:
            sid = str(item.get("seller_id", ""))
            limit_raw = item.get("shipping_limit_date")
            limit_str = str(limit_raw) if pd.notna(limit_raw) else None

            handoff_variance = None
            late_handoff = False

            if carrier_handoff_at and limit_str:
                dt_handoff = pd.to_datetime(carrier_handoff_at)
                dt_limit = pd.to_datetime(limit_str)
                h_var_sec = (dt_handoff - dt_limit).total_seconds()
                handoff_variance = round(h_var_sec / 3600.0, 2)
                if handoff_variance > 0:
                    late_handoff = True
                    if sid and sid not in late_handoff_seller_ids:
                        late_handoff_seller_ids.append(sid)

            if sid:
                seller_handoff_analysis.append({
                    "seller_id": sid,
                    "shipping_limit_at": limit_str,
                    "handoff_variance_hours": handoff_variance,
                    "late_handoff": late_handoff,
                })

        has_late_seller_handoff = len(late_handoff_seller_ids) > 0

        return {
            "delivered_at": delivered_at,
            "estimated_delivery_at": estimated_delivery_at,
            "carrier_handoff_at": carrier_handoff_at,
            "delivery_variance_hours": delivery_variance_hours,
            "seller_handoff_analysis": seller_handoff_analysis,
            "late_handoff_seller_ids": late_handoff_seller_ids,
            "is_late_delivery": is_late_delivery,
            "has_late_seller_handoff": has_late_seller_handoff,
        }
