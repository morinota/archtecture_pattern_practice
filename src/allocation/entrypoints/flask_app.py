from datetime import datetime
from typing import Dict, List, Tuple

from flask import Flask, Response, jsonify, request
from hypothesis import event
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import config
from adapters import orm, repository
from domain import events, model
from service_layer import handler, messagebus, unit_of_work

orm.start_mappers()
get_session = sessionmaker(bind=create_engine(config.get_postgres_uri()))
app = Flask(__name__)


@app.route("/allocate", methods=["POST"])
def allocate_endpoint() -> Tuple[Dict[str, str], int]:
    """図4-4よりflask APIは 詳細Repositoryと Service Layerに依存.
    返り値:適切なステータスコードを持ついくつかのJSONレスポンス."""

    # requestからorder lineの情報を取得.
    orderid: str = request.json["orderid"]
    sku: str = request.json["sku"]
    qty: int = request.json["qty"]

    try:
        event = events.AllocationRequired(orderid, sku, qty)
        results = messagebus.handle(event, unit_of_work.SqlAlchemyUnitOfWork())
        batchref = results.pop(0)
    except handler.InvalidSku as e:
        return {"message": str(e)}, 400

    return {"batchref": batchref}, 201


@app.route("/add_batch", methods=["POST"])
def add_batch() -> Tuple[str, int]:
    session = get_session()
    repo = repository.SqlAlchemyRepository(session)
    eta = request.json["eta"]
    if eta is not None:
        eta = datetime.fromisoformat(eta).date()
    handler.add_batch(request.json["ref"], request.json["sku"], request.json["qty"], eta, repo, session)
    return "OK", 201
