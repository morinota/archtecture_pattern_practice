from dataclasses import dataclass
from datetime import date
from tkinter.messagebox import NO
from typing import List, Optional


@dataclass(frozen=True)  # これで、__eq__と__hash__を定義しなくて良くなる.
class OrderLine:
    orderid: str
    sku: str
    qty: int


class Batch:
    def __init__(self, ref: str, sku: str, qty: int, eta: Optional[date]):
        self.reference = ref
        self.sku = sku
        self.eta = eta
        self._purchased_quantity = qty
        self._allocations = set()  # type: Set[OrderLine]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Batch):  # otherがBatchオブジェクトではないケース
            return False
        return other.reference == self.reference  # "オブジェクトを一意に識別するid"が一致している限りTrue

    def __hash__(self) -> int:
        return hash(self.reference)  # "オブジェクトを一意に識別するid"に基づいてハッシュ値を作る.

    def __gt__(self, other: "Batch") -> bool:
        """オブジェクト間で大小関係を定義する.sorted(List[Batch])の時などに適用される.
        - True = selfの方が大きい(降順側になる).
        - False = otherの方が大きい. (昇順側になる.)
        """
        if self.eta is None:
            return False
        if other.eta is None:
            return True

        return self.eta > other.eta

    def allocate(self, line: OrderLine):
        """注文が入った場合は、バッチで利用可能な個数を減らす."""
        self.available_quantity -= line.qty

    def can_allocate(self, line: OrderLine) -> bool:
        """オーダーラインを割り当て可能かを返す"""
        return self.sku == line.sku and self.available_quantity >= line.qty

    def deallocate(self, line: OrderLine):
        """バッチへの注文の割り当てを外す"""
        if line in self._allocations:
            self._allocations.remove(line)

    @property
    def allocated_quantity(self) -> int:
        return sum(line.qty for line in self._allocations)

    @property
    def available_quantity(self) -> int:
        return self._purchased_quantity - self.allocated_quantity


class OutOfStock(Exception):
    pass


def allocate(line: OrderLine, batches: List[Batch]) -> str:
    """ある優先順でbatch在庫達を並び替え、
    最も優先順位の高いbatch在庫にオーダーラインを割り当てる.
    """
    try:
        batch = next(b for b in sorted(batches) if b.can_allocate(line))
        batch.allocate(line)
        return batch.reference
    except StopIteration:
        raise OutOfStock(f"Out of stock for sku {line.sku}")
