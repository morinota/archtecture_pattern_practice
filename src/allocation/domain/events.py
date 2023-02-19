from dataclasses import dataclass
from datetime import date
from typing import Optional


class Event:
    pass


@dataclass
class OutOfStock(Event):
    """在庫がない状況を表すevent"""

    sku: str


@dataclass
class BatchCreated(Event):
    """新しいBatchを追加するEvent"""

    ref: str
    sku: str
    qty: int
    eta: Optional[date] = None


@dataclass
class AllocationRequired(Event):
    """orderlineをbatchに割り当てるevent"""

    orderid: str
    sku: str
    qty: int


@dataclass
class BatchQuantityChanged(Event):
    """特定のBatchのQuantityを変更するevent"""

    ref: str
    qty: int
