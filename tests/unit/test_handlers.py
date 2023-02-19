import abc
from datetime import date
from typing import List

from src.allocation.adapters import repository
from src.allocation.domain import events, model
from src.allocation.service_layer import handler, messagebus, unit_of_work


class FakeRepository(repository.AbstractRepository):
    def __init__(self, products: List[model.Product]):
        super().__init__()
        self._products = set(products)

    def _add(self, product):
        self._products.add(product)

    def _get(self, sku):
        return next((p for p in self._products if p.sku == sku), None)

    def _get_by_batchref(self, batchref) -> model.Product:
        return next((p for p in self._products for b in p.batches if b.reference == batchref), None)


class FakeSession(abc.ABC):
    committed: bool = False

    def commit(self) -> None:
        self.committed = True


class FakeUnitOfWork(unit_of_work.AbstractUnitOfWork):
    def __init__(self):
        self.products = FakeRepository([])
        # FakeUnitOfWorkとFakeRepositoryは、realのUnitOfWorkとRepositoryクラスと同じように、
        # 密に結合している.
        self.committed = False

    def _commit(self):
        self.committed = True

    def rollback(self):
        pass


class FakeUnitOfWorkWithFakeMessageBus(FakeUnitOfWork):
    def __init__(self):
        super().__init__()
        self.events_published: List[events.Event] = []

    def publish_events(self):
        for product in self.products.seen:
            while product.events:
                self.events_published.append(product.events.pop(0))


class TestAddBatch:
    def test_add_batch_for_new_product(self) -> None:
        uow = FakeUnitOfWork()
        messagebus.handle(
            event=events.BatchCreated("b1", "CRUNCHY-ARMCHAIR", 100, None),
            uow=uow,
        )
        assert uow.products.get("CRUNCHY-ARMCHAIR") is not None
        assert uow.committed

    def test_add_batch_for_existing_product(self) -> None:
        uow = FakeUnitOfWork()
        messagebus.handle(
            event=events.BatchCreated("b1", "GARISH-RUG", 100, None),
            uow=uow,
        )
        messagebus.handle(
            event=events.BatchCreated("b2", "GARISH-RUG", 99, None),
            uow=uow,
        )
        assert "b2" in [b.reference for b in uow.products.get("GARISH-RUG").batches]


class TestAllocate:
    def test_returns_allocation(self) -> None:
        uow = FakeUnitOfWork()
        messagebus.handle(
            events.BatchCreated("batch1", "COMPLICATED-LAMP", 100, None),
            uow,
        )
        [result] = messagebus.handle(
            events.AllocationRequired("o1", "COMPLICATED-LAMP", 10),
            uow,
        )  # API layerのallocate_endpoint()とdomain modelのallocate()の間に位置する処理
        assert result == "batch1"


class TestChangeBatchQuantity:
    def test_changes_available_quantity(self):
        uow = FakeUnitOfWork()
        messagebus.handle(
            events.BatchCreated("batch1", "ADORABLE-SETTEE", 100, None),
            uow,
        )
        [batch] = uow.products.get(
            sku="ADORABLE-SETTEE"
        ).batches  # listの1要素を変数として代入(参照渡し...!)してる(あんまり見たことない書き方だったのでコメント).
        assert batch.available_quantity == 100

        change_batch_quantity_event = events.BatchQuantityChanged(
            ref="batch1",
            qty=50,
        )
        messagebus.handle(change_batch_quantity_event, uow)

        assert batch.available_quantity == 50

    def test_reallocates_if_necessary(self):
        uow = FakeUnitOfWork()
        event_history = [
            events.BatchCreated("batch1", "INDIFFERENT-TABLE", 50, None),
            events.BatchCreated("batch2", "INDIFFERENT-TABLE", 50, date.today()),
            events.AllocationRequired("order1", "INDIFFERENT-TABLE", 20),
            events.AllocationRequired("order2", "INDIFFERENT-TABLE", 20),
        ]
        for event in event_history:
            messagebus.handle(event, uow)
        [batch1, batch2] = uow.products.get(sku="INDIFFERENT-TABLE").batches
        assert batch1.available_quantity == 10
        assert batch2.available_quantity == 50

        change_batch_quantity_event = events.BatchQuantityChanged(
            ref="batch1",
            qty=25,
        )
        messagebus.handle(change_batch_quantity_event, uow)

        # order1 or order2 will be deallocated, so we'll have 25 - 20
        assert batch1.available_quantity == 5
        # and 20 will be reallocated to the next batch
        assert batch2.available_quantity == 30


def test_reallocates_if_necessary_isolated() -> None:
    uow = FakeUnitOfWorkWithFakeMessageBus()

    # test setup as before
    event_history = [
        events.BatchCreated("batch1", "INDIFFERENT-TABLE", 50, None),
        events.BatchCreated("batch2", "INDIFFERENT-TABLE", 50, date.today()),
        events.AllocationRequired("order1", "INDIFFERENT-TABLE", 20),
        events.AllocationRequired("order2", "INDIFFERENT-TABLE", 20),
    ]
    for e in event_history:
        messagebus.handle(e, uow)

    [batch1, batch2] = uow.products.get(sku="INDIFFERENT-TABLE").batches
    assert batch1.available_quantity == 10
    assert batch2.available_quantity == 50

    messagebus.handle(events.BatchQuantityChanged("batch1", 25), uow)

    # assert on new events emitted rather than downstream side-effects
    [reallocation_event] = uow.events_published
    assert isinstance(reallocation_event, events.AllocationRequired)
    assert reallocation_event.orderid in {"order1", "order2"}
    assert reallocation_event.sku == "INDIFFERENT-TABLE"
