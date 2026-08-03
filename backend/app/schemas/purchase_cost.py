from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PurchaseCostHistoryResponse(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str
    supplier_id: UUID
    supplier_name: str
    purchase_order_id: UUID
    purchase_order_number: str
    goods_receipt_id: UUID
    receipt_number: str
    quantity: float
    unit_cost: float
    previous_stock: float
    new_stock: float
    previous_average_cost: float
    new_average_cost: float
    created_at: datetime
