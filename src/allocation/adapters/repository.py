import abc
from typing import List, Set

# domain modelに依存
from sqlalchemy.orm.session import Session

from src.allocation.adapters import orm
from src.allocation.domain import model


class AbstractRepository(abc.ABC):
    """最も単純なリポジトリは，新しいアイテムをリポジトリに登録するための `add()` と,
    以前に登録されたアイテムを返すための `get()` の2つのメソッドを持つ.
    """

    def __init__(self) -> None:
        self.seen: Set[model.Product] = set()

    def add(self, product: model.Product) -> None:
        self._add(product)
        self.seen.add(product)

    def get(self, sku: str) -> model.Product:
        product = self._get(sku)
        if product:
            self.seen.add(product)
        return product

    def get_by_batchref(self, batchref: str) -> model.Product:
        product = self._get_by_batchref(batchref)
        if product:
            self.seen.add(product)
        return product

    @abc.abstractmethod
    def _add(self, product: model.Product) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def _get(self, sku: str) -> model.Product:
        raise NotImplementedError

    @abc.abstractmethod
    def _get_by_batchref(self, batchref: str) -> model.Product:
        raise NotImplementedError


class SqlAlchemyRepository(AbstractRepository):
    def __init__(self, session: Session):
        self.session = session

    def _add(self, batch):
        self.session.add(batch)

    def _get(self, sku: str):
        return self.session.query(model.Batch).filter_by(reference=sku).one()

    def _get_by_batchref(self, batchref: str) -> model.Product:
        return (
            self.session.query(model.Product)
            .join(model.Batch)
            .filter(
                orm.batches.c.reference == batchref,
            )
            .first()
        )

    def list(self):
        return self.session.query(model.Batch).all()
