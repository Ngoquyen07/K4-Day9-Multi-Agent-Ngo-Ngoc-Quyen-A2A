from typing import Dict, Any, List
from src.data_loader import OlistDataLoader

class PaymentAgent:
    """
    Payment Agent:
    Reconciles payment transactions against expected order total BRL.
    """

    def __init__(self, data_loader: OlistDataLoader):
        self.data_loader = data_loader

    def analyze(self, order_id: str, expected_total_brl: float) -> Dict[str, Any]:
        payments = self.data_loader.get_order_payments(order_id)

        payment_ids = []
        payment_types = []
        payment_total_brl = 0.0

        for pay in payments:
            seq = pay.get("payment_sequential")
            payment_ids.append(f"{order_id}:{seq}")

            ptype = str(pay.get("payment_type", ""))
            if ptype and ptype not in payment_types:
                payment_types.append(ptype)

            val = float(pay.get("payment_value", 0.0))
            payment_total_brl += val

        payment_total_brl = round(payment_total_brl, 2)
        difference_brl = round(payment_total_brl - expected_total_brl, 2)

        # Reconciled if absolute difference is <= 0.10 BRL per README Section 4
        reconciled = abs(difference_brl) <= 0.10
        is_split_payment = len(payments) > 1

        return {
            "payments": payments,
            "payment_ids": payment_ids,
            "payment_types": payment_types,
            "payment_total_brl": payment_total_brl,
            "difference_brl": difference_brl,
            "reconciled": reconciled,
            "is_split_payment": is_split_payment,
        }
