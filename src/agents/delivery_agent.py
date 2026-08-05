from typing import Dict, Any, List, Optional
from datetime import datetime
from src.data_loader import OlistDataLoader

def parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        return datetime.strptime(dt_str.strip(), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

class DeliveryAgent:
    """
    Delivery Agent:
    Parses order timestamps, computes delivery_variance_hours and seller handoff variance.
    Identifies late sellers and carrier delay.
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

        delivered_at_str = order.get("order_delivered_customer_date")
        estimated_at_str = order.get("order_estimated_delivery_date")
        carrier_handoff_at_str = order.get("order_delivered_carrier_date")

        dt_delivered = parse_datetime(delivered_at_str)
        dt_estimated = parse_datetime(estimated_at_str)
        dt_carrier = parse_datetime(carrier_handoff_at_str)

        delivery_variance_hours: Optional[float] = None
        is_late_delivery = False

        if dt_delivered and dt_estimated:
            diff_sec = (dt_delivered - dt_estimated).total_seconds()
            delivery_variance_hours = round(diff_sec / 3600.0, 2)
            is_late_delivery = dt_delivered > dt_estimated

        seller_handoff_analysis = []
        late_handoff_seller_ids = []
        has_late_seller_handoff = False

        if items and dt_carrier:
            # Group items by seller_id to find earliest shipping_limit_date per seller
            seller_limits: Dict[str, datetime] = {}
            seller_limit_strs: Dict[str, str] = {}

            for item in items:
                sid = item["seller_id"]
                limit_str = item.get("shipping_limit_date")
                dt_limit = parse_datetime(limit_str)
                if dt_limit:
                    if sid not in seller_limits or dt_limit < seller_limits[sid]:
                        seller_limits[sid] = dt_limit
                        seller_limit_strs[sid] = limit_str

            for sid, dt_limit in seller_limits.items():
                handoff_diff_sec = (dt_carrier - dt_limit).total_seconds()
                handoff_variance_hours = round(handoff_diff_sec / 3600.0, 2)
                late_handoff = dt_carrier > dt_limit

                if late_handoff:
                    late_handoff_seller_ids.append(sid)
                    has_late_seller_handoff = True

                seller_handoff_analysis.append({
                    "seller_id": sid,
                    "shipping_limit_at": seller_limit_strs[sid],
                    "handoff_variance_hours": handoff_variance_hours,
                    "late_handoff": late_handoff,
                })

        return {
            "delivered_at": delivered_at_str,
            "estimated_delivery_at": estimated_at_str,
            "carrier_handoff_at": carrier_handoff_at_str,
            "delivery_variance_hours": delivery_variance_hours,
            "seller_handoff_analysis": seller_handoff_analysis,
            "late_handoff_seller_ids": late_handoff_seller_ids,
            "is_late_delivery": is_late_delivery,
            "has_late_seller_handoff": has_late_seller_handoff,
        }
