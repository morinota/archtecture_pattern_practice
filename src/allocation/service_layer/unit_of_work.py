import abc
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session

from src.allocation.adapters.repository import AbstractRepository, SqlAlchemyRepository
from src.allocation.config import get_postgres_uri
from src.allocation.domain import events


class AbstractUnitOfWork(abc.ABC):
    """Abstract Base Class(クラスが何をする必要があるのかを明示的に示す為に作る)"""

    products: AbstractRepository  # このpropertyによってbatchesリポジトリにアクセスできる.

    def __enter__(self) -> "AbstractUnitOfWork":
        """context managerの為のmethod.
        withブロックに入る時に実行されるmagic method.
        """
        return self

    def __exit__(self, *args):
        """context managerの為のmethod.
        withブロックを出る時に実行されるmagic method.
        """
        self.rollback()

    def commit(self):
        """準備ができたら、このメソッドを呼び出して、明示的に作業をコミットする."""
        self._commit()
        self.collect_new_events()

    def collect_new_events(self) -> Iterator[events.Event]:
        """各Product(Aggregate)クラス毎に溜まったEventを取得する."""
        for product in self.products.seen:
            while product.events:
                yield product.events.pop(0)  # eventsの先頭から(queue的な取り出し方)

    @abc.abstractmethod
    def _commit(self):
        raise NotImplementedError

    @abc.abstractmethod
    def rollback(self):
        """コミットしない場合、またはエラーを発生させてコンテキストマネージャを終了する場合、ロールバックを行う"""
        raise NotImplementedError


DEFAULT_SESSION_FACTORY = sessionmaker(
    bind=create_engine(
        get_postgres_uri(),
        isolation_level="REPEATABLE READ",
    )
)


class SqlAlchemyUnitOfWork(AbstractUnitOfWork):
    def __init__(self, session_factory=DEFAULT_SESSION_FACTORY) -> None:
        self.session_factory = session_factory

    def __enter__(self):
        """データベースセッションを開始し、そのセッションを使用できる
        実際のリポジトリのインスタンスを作成する役割を担う"""
        self.session: Session = self.session_factory()
        self.batches = SqlAlchemyRepository(self.session)
        return super().__enter__()

    def __exit__(self, *args):
        super().__exit__(*args)
        self.session.close()

    def _commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()
