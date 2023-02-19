from typing import Any, Callable, Dict, List, Type

from src.allocation.adapters.my_email import send_mail
from src.allocation.domain import events
from src.allocation.service_layer import handler, unit_of_work


def handle(
    event: events.Event,
    uow: unit_of_work.AbstractUnitOfWork,  # messagebusが起動する度にuowが渡されるようになった.
) -> List[Any]:
    """messagebusの役割を持つ関数?"""
    results = []
    queue = [event]  # 最初のイベントの処理を開始するとき、キューを開始する.
    while queue:
        event = queue.pop(0)  # eventをqueueの先頭から取得し、対応するhandlerを呼び出す.
        for handler in HANDLERS[type(event)]:
            results.append(handler(event, uow))  # messagebusは、UoWを各ハンドラに受け渡す.
            queue.extend(uow.collect_new_events())  # 各ハンドラの終了後、新たに発生したeventを収集し、queue に追加する.

    return results


def send_out_of_stock_notification(event: events.OutOfStock):
    send_mail(
        "stock@made.com",
        f"Out of stock for {event.sku}",
    )


HANDLERS: Dict[Type[events.Event], List[Callable]] = {
    events.BatchCreated: [handler.add_batch],
    events.BatchQuantityChanged: [handler.change_batch_quantity],
    events.AllocationRequired: [handler.allocate],
    events.OutOfStock: [send_out_of_stock_notification],
}
