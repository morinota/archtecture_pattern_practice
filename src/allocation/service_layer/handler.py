from datetime import date
from typing import List, Optional

from src.allocation.domain import events
from src.allocation.domain.model import Batch, OrderLine, Product
from src.allocation.service_layer import unit_of_work


class InvalidSku(Exception):
    pass


def is_valid_sku(sku: str, batches: List[Batch]) -> bool:
    return sku in {b.sku for b in batches}


def add_batch(event: events.BatchCreated, uow: unit_of_work.AbstractUnitOfWork):
    # @chap9: service layer functionから event handlerへ変更
    with uow:
        product = uow.products.get(sku=event.sku)
        if product is None:
            product = Product(event.sku, batches=[])
            uow.products.add(product)
        product.batches.append(
            Batch(
                event.ref,
                event.sku,
                event.qty,
                event.eta,
            )
        )
        uow._commit()


def allocate(
    event: events.AllocationRequired,
    uow: unit_of_work.AbstractUnitOfWork,
) -> str:
    """service layer function.
    (repositoryに依存している) = "テストがFakeRepositoryを与えても、
    FlaskアプリがSqlAlchemyRepositoryを与えても動作すること"を意味する.
    OrderLine型を受け取るのではなくprimitiveなデータ型を受け取る -> Domain への依存を切り離す為.
    """
    line = OrderLine(event.orderid, event.sku, event.qty)
    with uow:
        product = uow.products.get(sku=line.sku)
        if product is None:
            raise InvalidSku(f"Invalid sku {line.sku}")
        batchref = product.allocate(line)
        uow._commit()
    return batchref


def reallocate(line: OrderLine, uow: unit_of_work.AbstractUnitOfWork) -> str:
    with uow:
        batch = uow.batches.get(reference=line.sku)
        if batch is None:
            raise InvalidSku(f"Invalid sku {line.sku}")
        batch.deallocate(line)
        allocate(line)
        uow._commit()


def change_batch_quantity(
    event: events.BatchQuantityChanged,
    uow: unit_of_work.AbstractUnitOfWork,
):
    with uow:
        product = uow.products.get_by_batchref(batchref=event.ref)
        product.change_batch_quantity(ref=event.ref, qty=event.qty)
        uow.commit()


def send_out_of_stock_notification(
    event: events.OutOfStock,
    uow: unit_of_work.AbstractUnitOfWork,
):
    email.send_mail(
        "stock@made.com",
        f"Out of stock for {event.sku}",
    )
