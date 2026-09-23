import re
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request
from pydantic import BeforeValidator

from app.db import connect_read, product_from_row, require_warehouse
from app.errors import ApiError
from app.models import Health, Product, ProductList, Warehouses

def integer_text(value):
    if isinstance(value, str) and not re.fullmatch(r"-?[0-9]+", value):
        raise ValueError("Укажите целое число.")
    return value


IntegerParam = Annotated[int, BeforeValidator(integer_text)]
router = APIRouter(prefix="/api")


@router.get("/health", response_model=Health)
def health(request: Request):
    with connect_read(request.app.state.settings.database_path) as db:
        for table in ("products", "warehouses", "stock"):
            db.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
    return Health(demo_mode=request.app.state.settings.demo_mode)


@router.get("/warehouses", response_model=Warehouses)
def warehouses(request: Request):
    with connect_read(request.app.state.settings.database_path) as db:
        items = [dict(row) for row in db.execute("SELECT id,name,city FROM warehouses ORDER BY position,id")]
        default = db.execute("SELECT value FROM catalog_meta WHERE key='default_warehouse_id'").fetchone()
        if not items or default is None or default[0] not in {item["id"] for item in items}:
            raise ApiError(503, "DATABASE_UNAVAILABLE", "Каталог складов не инициализирован.")
    return {"items": items, "default_warehouse_id": default[0]}


@router.get("/products", response_model=ProductList)
def products(
    request: Request,
    warehouse_id: str,
    q: Annotated[str, Query(max_length=200)] = "",
    limit: Annotated[IntegerParam, Query(ge=1, le=100)] = 20,
    offset: Annotated[IntegerParam, Query(ge=0)] = 0,
):
    query = q.strip().casefold()
    # instr вместо LIKE: %, _ и кавычки в артикуле являются обычными символами.
    where = "instr(CASEFOLD(p.sku),?)>0 OR instr(CASEFOLD(p.name),?)>0"
    with connect_read(request.app.state.settings.database_path) as db:
        require_warehouse(db, warehouse_id)
        total = db.execute(f"SELECT count(*) FROM products p WHERE {where}", (query, query)).fetchone()[0]
        rows = db.execute(
            f"SELECT p.payload,s.quantity FROM products p LEFT JOIN stock s ON s.product_id=p.id AND s.warehouse_id=? WHERE {where} ORDER BY CASE WHEN CASEFOLD(p.sku)=? THEN 0 ELSE 1 END,p.sku,p.id LIMIT ? OFFSET ?",
            (warehouse_id, query, query, query, limit, offset),
        ).fetchall()
    return {"items": [product_from_row(row, warehouse_id) for row in rows], "total": total, "limit": limit, "offset": offset, "warehouse_id": warehouse_id}


@router.get("/products/{id}", response_model=Product)
def product_detail(request: Request, id: Annotated[IntegerParam, Path(gt=0)], warehouse_id: str):
    with connect_read(request.app.state.settings.database_path) as db:
        require_warehouse(db, warehouse_id)
        row = db.execute("SELECT p.payload,s.quantity FROM products p LEFT JOIN stock s ON s.product_id=p.id AND s.warehouse_id=? WHERE p.id=?", (warehouse_id, id)).fetchone()
        if row is None:
            raise ApiError(404, "PRODUCT_NOT_FOUND", "Товар не найден.", {"product_id": id})
    return product_from_row(row, warehouse_id)
