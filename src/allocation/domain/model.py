from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Set

from src.allocation.domain import events
from src.allocation.domain.events import Event, OutOfStock


@dataclass(unsafe_hash=True)  # これで、__eq__と__hash__を定義せずとも、Value Objectを明示的にできる.
class OrderLine:
    orderid: str
    sku: str
    qty: int


class Batch:
    def __init__(self, ref: str, sku: str, qty: int, eta: Optional[date]):
        self.reference = ref
        self.sku = sku
        self.eta = eta
        self._purchased_quantity = qty  # 総量
        self._allocations: Set[OrderLine] = set()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Batch):
            return False
        return other.reference == self.reference  # "オブジェクトを一意に識別するid"が一致している限りTrue -> Entity

    def __hash__(self) -> int:
        return hash(self.reference)  # "オブジェクトを一意に識別するid"に基づいてハッシュ値を作る.

    def __gt__(self, other: "Batch") -> bool:
        """オブジェクト間で大小関係を定義する.sorted(List[Batch])の時などに適用される.
        - True = selfの方が大きい(selfが降順側になる).
        - False = otherの方が大きい. (selfが昇順側になる.)
        """
        if self.eta is None:
            return False
        if other.eta is None:
            return True

        return self.eta > other.eta

    def allocate(self, line: OrderLine):
        """注文が入った場合は、バッチで利用可能な個数を減らす."""
        if self.can_allocate(line):
            self._allocations.add(line)

    def can_allocate(self, line: OrderLine) -> bool:
        """オーダーラインを割り当て可能かを返す"""
        return self.sku == line.sku and self.available_quantity >= line.qty

    def deallocate(self, line: OrderLine):
        """バッチへの注文の割り当てを外す"""
        if line in self._allocations:
            self._allocations.remove(line)

    def deallocate_one(self) -> OrderLine:
        """一番最後尾の割り当てを外す"""
        return self._allocations.pop()

    @property
    def allocated_quantity(self) -> int:
        return sum(line.qty for line in self._allocations)

    @property
    def available_quantity(self) -> int:
        return self._purchased_quantity - self.allocated_quantity


class Product:
    """Aggregate クラス= 全ての操作が一貫した状態(consistent state)で終了する事を確認する境界線"""

    def __init__(self, sku: str, batches: List[Batch], version_number: int = 0) -> None:
        """
        Parameters
        ----------
        sku : str
            `Product`の主な識別子(=ユニークなインスタンスを識別する情報)はsku.
        batches : List[Batch]
             `Product` クラスは、そのskuに対応する `batches` のcollection への参照を保持する
        version_number : int, optional
            version number によるOptimistic Locking, by default 0
        """
        self.sku = sku
        self.batches = batches
        self.version_number = version_number
        self.events: List[Event] = []

    def allocate(self, line: OrderLine) -> str:
        """`allocate()` Domain Service を `Product` 集合体のメソッドに移動させてくる. = Domain Service
        Domain Service
        ある優先順でbatch在庫達を並び替え、
        最も優先順位の高いbatch在庫にオーダーラインを割り当てる.
        """
        try:
            batch: Batch = next(b for b in sorted(self.batches) if b.can_allocate(line))
            batch.allocate(line)
            self.version_number += 1  # allocateする度にversion numberをincrement
            return batch.reference
        except StopIteration:
            self.events.append(OutOfStock(line.sku))
            return None

    def change_batch_quantity(self, ref: str, qty: int):
        batch = next(b for b in self.batches if b.reference == ref)
        batch._purchased_quantity = qty
        while batch.available_quantity < 0:
            line = batch.deallocate_one()
            self.events.append(events.AllocationRequired(line.orderid, line.sku, line.qty))
