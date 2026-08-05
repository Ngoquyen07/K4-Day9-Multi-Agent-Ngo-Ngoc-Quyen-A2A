from typing import Dict, Any, List, Optional
from src.data_loader import OlistDataLoader

class PaymentAgent:
    """
    Payment Agent:
    Retrieves payment records, computes total payments, reconciles against expected total,
    and identifies split payments.
    Enforces README schema: payment_ids max 5.
    """

    def __init__(self, data_loader: OlistDataLoader):
        self.data_loader = data_loader

    def analyze(self, order_id: str, expected_total_brl: Optional[float]) -> Dict[str, Any]:
        payments = self.data_loader.get_order_payments(order_id)
        if not payments:
            return {
                "payments": [],
                "payment_ids": [],
                "payment_total_brl": 0.0,
                "difference_brl": None,
                "reconciled": None,
                "payment_types": [],
                "is_split_payment": False,
            }

        payment_ids = [f"{order_id}:{p['payment_sequential']}" for p in payments][:5]

        payment_total_brl = 0.0
        payment_types = []

        for p in payments:
            payment_total_brl += p["payment_value"]
            ptype = p["payment_type"]
            if ptype not in payment_types:
                payment_types.append(ptype)

        payment_total_brl = round(payment_total_brl, 2)

        if expected_total_brl is not None:
            difference_brl = round(payment_total_brl - expected_total_brl, 2)
            reconciled = abs(difference_brl) <= 0.10
        else:
            difference_brl = None
            reconciled = None

        return {
            "payments": payments,
            "payment_ids": payment_ids,
            "payment_total_brl": payment_total_brl,
            "difference_brl": difference_brl,
            "reconciled": reconciled,
            "payment_types": payment_types,
            "is_split_payment": len(payments) >= 2,
        }
