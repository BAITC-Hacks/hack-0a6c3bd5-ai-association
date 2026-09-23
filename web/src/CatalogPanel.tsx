import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  FileText,
  LoaderCircle,
  Package,
  RefreshCw,
  Search,
  X,
} from "lucide-react";
import {
  apiErrorMessage,
  getProduct,
  getProducts,
  getWarehouses,
  localAssetUrl,
  type Product,
  type ProductListResponse,
  type ProductSnapshot,
  type Warehouse,
} from "./api";

interface CatalogPanelProps {
  focusRequest: number;
  initialQuery?: string;
}

const pageSize = 6;
const numberFormat = new Intl.NumberFormat("ru-RU");
const dateFormat = new Intl.DateTimeFormat("ru-RU", {
  timeZone: "Asia/Almaty",
});
const money = (value: number | null) =>
  value === null ? "Цена не указана" : `${numberFormat.format(value)} ₸`;
const quantity = (value: number | null, unit: string) =>
  value === null
    ? "Нет данных"
    : value === 0
      ? `0 ${unit} — нет в наличии`
      : `${numberFormat.format(value)} ${unit}`;
const warehouseLabel = (warehouse: Warehouse) =>
  warehouse.name === warehouse.city
    ? warehouse.name
    : `${warehouse.city} · ${warehouse.name}`;
const propertyLabels: Record<string, string> = {
  BRAND_PRIORITY: "Приоритет бренда",
  BLOG_POST_ID: "Публикация источника",
  CML2_ARTICLE: "Артикул",
  NOVINKA: "Новинка",
  SPETSPREDLOZHENIE: "Специальное предложение",
  RECOMMEND: "Рекомендации источника",
  CML2_BAR_CODE: "Штрихкод",
  CML2_TRAITS: "Реквизиты источника",
  CML2_TAXES: "Налог в данных источника",
  KRATNOST_MIN: "Минимальная кратность",
  KRATNOST_MAKS: "Максимальная кратность",
  KATEGORIYA: "Категория",
  KOLICHESTVOVREZERVE: "Резерв по данным источника",
  IMYAKARTINKI: "Имя изображения в источнике",
  ARTIKULPOSTAVSHCHIKA: "Артикул поставщика",
  OBYEM: "Тип товара в источнике",
  KOLICHESTVO_POLYUSOV: "Количество полюсов",
  NOMINALNAYA_OTKLYUCHAYUSHCHAYA_SPOSOBNOST:
    "Номинальная отключающая способность",
  NOMINALNOE_NAPRYAZHENIE: "Номинальное напряжение",
  VYKHODNOE_NAPRYAZHENIE_: "Выходное напряжение",
  NOMINALNYY_TOK: "Номинальный ток",
  TIP_USTANOVKI: "Тип установки",
  TORGOVAYA_MARKA: "Торговая марка",
};

function SnapshotLabel({ snapshot }: { snapshot: ProductSnapshot }) {
  const captured = new Date(snapshot.captured_at);
  const date = Number.isNaN(captured.getTime())
    ? "Дата не указана"
    : dateFormat.format(captured);
  const source =
    snapshot.source === "ekt_catalog"
      ? "Каталог ekt.kz"
      : snapshot.source_url
        ? "Снимок каталога"
        : "Учебная позиция";
  return (
    <div className="apicatalog-snapshot">
      <CalendarDays size={13} />
      <span>
        {source} · {date}
      </span>
    </div>
  );
}

function ProductVisual({ product }: { product: Product }) {
  const imageUrl = localAssetUrl(product.image_url);
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [imageUrl]);
  return (
    <div className="apicatalog-visual">
      {imageUrl && !failed ? (
        <img
          src={imageUrl}
          alt={product.name}
          loading="lazy"
          onError={() => setFailed(true)}
        />
      ) : (
        <>
          <Package size={44} strokeWidth={1.2} aria-hidden="true" />
          <span>Изображение не предоставлено</span>
        </>
      )}
    </div>
  );
}

function RequestState({
  loading,
  error,
  retry,
}: {
  loading?: boolean;
  error?: string;
  retry?: () => void;
}) {
  return (
    <div
      className={`apicatalog-state ${error ? "apicatalog-error" : ""}`}
      role={error ? "alert" : "status"}
    >
      {loading ? (
        <>
          <LoaderCircle
            size={24}
            className="apicatalog-spinner"
            aria-hidden="true"
          />
          <p>Загружаем данные каталога…</p>
        </>
      ) : (
        <>
          <p>{error}</p>
          <button className="secondary-button" onClick={retry}>
            <RefreshCw size={15} />
            Повторить
          </button>
        </>
      )}
    </div>
  );
}

function ProductDialog({
  productId,
  warehouse,
  close,
}: {
  productId: number;
  warehouse: Warehouse;
  close: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [product, setProduct] = useState<Product | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError("");
    setProduct(null);
    getProduct(productId, warehouse.id, controller.signal)
      .then((value) => {
        if (active) setProduct(value);
      })
      .catch((caught) => {
        if (active && !controller.signal.aborted)
          setError(apiErrorMessage(caught));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [productId, warehouse.id, retry]);

  return (
    <dialog
      ref={dialog}
      className="dialog apicatalog-dialog"
      aria-labelledby="apicatalog-dialog-title"
      onClose={close}
      onPointerDown={(event) => {
        if (event.target !== event.currentTarget) return;
        const bounds = event.currentTarget.getBoundingClientRect();
        if (
          event.clientX < bounds.left ||
          event.clientX > bounds.right ||
          event.clientY < bounds.top ||
          event.clientY > bounds.bottom
        )
          close();
      }}
    >
      <div className="dialog-head">
        <h2 id="apicatalog-dialog-title">Карточка товара</h2>
        <button
          className="icon-button"
          aria-label="Закрыть карточку"
          onClick={close}
        >
          <X size={20} />
        </button>
      </div>
      {loading ? (
        <RequestState loading />
      ) : error ? (
        <RequestState
          error={error}
          retry={() => setRetry((value) => value + 1)}
        />
      ) : (
        product && (
          <>
            <div className="apicatalog-detail-hero">
              <ProductVisual product={product} />
              <div className="apicatalog-detail-heading">
                <span className="product-sku">АРТ. {product.sku}</span>
                <h3>{product.name}</h3>
                <p className="apicatalog-card-price">
                  {money(product.price_kzt)}
                  {product.price_kzt !== null && (
                    <small> / {product.unit}</small>
                  )}
                </p>
                <SnapshotLabel snapshot={product.snapshot} />
              </div>
            </div>
            <dl className="apicatalog-facts">
              <div>
                <dt>Выбранный склад</dt>
                <dd>{warehouseLabel(warehouse)}</dd>
              </div>
              <div>
                <dt>Остаток на этом складе</dt>
                <dd>{quantity(product.available_quantity, product.unit)}</dd>
              </div>
              <div>
                <dt>Общий остаток в источнике</dt>
                <dd>{quantity(product.total_quantity, product.unit)}</dd>
              </div>
              <div>
                <dt>Минимальное количество</dt>
                <dd>
                  {product.min_order_quantity === null
                    ? "Не указано"
                    : `${numberFormat.format(product.min_order_quantity)} ${product.unit}`}
                </dd>
              </div>
            </dl>
            <section className="apicatalog-section">
              <h3>Описание источника</h3>
              <p>{product.description || "Описание не предоставлено."}</p>
            </section>
            <section className="apicatalog-section">
              <h3>Характеристики из карточки</h3>
              {product.properties.length ? (
                <div className="apicatalog-properties">
                  {product.properties.map((property, index) => (
                    <div key={`${property.source_field}-${index}`}>
                      <div className="apicatalog-property-name">
                        <strong>
                          {propertyLabels[property.name] || property.name}
                        </strong>
                        <code>{property.source_field}</code>
                      </div>
                      <span>{property.value || "Не указано"}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p>Характеристики не предоставлены.</p>
              )}
            </section>
            <section className="apicatalog-section">
              <h3>Документы</h3>
              {product.documents.length ? (
                <ul className="apicatalog-documents">
                  {product.documents.map((document, index) => {
                    const url = localAssetUrl(document.url);
                    return (
                      <li key={`${document.url}-${index}`}>
                        <FileText size={17} aria-hidden="true" />
                        <div>
                          {url ? (
                            <a
                              href={url}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              {document.title ||
                                (document.kind === "certificate"
                                  ? "Сертификат"
                                  : "Технический лист")}
                            </a>
                          ) : (
                            <span>{document.title || "Документ"}</span>
                          )}
                          <small>
                            {url
                              ? document.kind === "certificate"
                                ? "Сертификат · локальный файл"
                                : "Технический лист · локальный файл"
                              : "Локальная копия не предоставлена"}
                          </small>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p>
                  Документы не предоставлены. Наличие сертификата не
                  подтверждено.
                </p>
              )}
            </section>
            <p className="apicatalog-source-note">
              Данные относятся к дате снимка, единицы учёта заданы для демо.
              Описание и характеристики приведены отдельно; соответствие вашему
              запросу ещё не проверено.
            </p>
          </>
        )
      )}
    </dialog>
  );
}

export default function CatalogPanel({
  focusRequest,
  initialQuery = "",
}: CatalogPanelProps) {
  const searchInput = useRef<HTMLInputElement>(null);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [warehouseId, setWarehouseId] = useState("");
  const [warehouseLoading, setWarehouseLoading] = useState(true);
  const [warehouseError, setWarehouseError] = useState("");
  const [warehouseRetry, setWarehouseRetry] = useState(0);
  const [query, setQuery] = useState(initialQuery.slice(0, 200));
  const [offset, setOffset] = useState(0);
  const [result, setResult] = useState<ProductListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [productId, setProductId] = useState<number | null>(null);
  const selectedWarehouse = warehouses.find(
    (warehouse) => warehouse.id === warehouseId,
  );

  useEffect(() => {
    if (focusRequest > 0) searchInput.current?.focus();
  }, [focusRequest]);

  useEffect(() => {
    setQuery(initialQuery.slice(0, 200));
    setOffset(0);
  }, [initialQuery]);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setWarehouseLoading(true);
    setWarehouseError("");
    getWarehouses(controller.signal)
      .then((value) => {
        if (!active) return;
        if (!value.items.length) {
          setWarehouseError("В каталоге пока нет складов.");
          return;
        }
        setWarehouses(value.items);
        setWarehouseId((current) =>
          value.items.some((warehouse) => warehouse.id === current)
            ? current
            : value.items.some(
                  (warehouse) => warehouse.id === value.default_warehouse_id,
                )
              ? value.default_warehouse_id
              : value.items[0].id,
        );
      })
      .catch((caught) => {
        if (active && !controller.signal.aborted)
          setWarehouseError(apiErrorMessage(caught));
      })
      .finally(() => {
        if (active) setWarehouseLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [warehouseRetry]);

  useEffect(() => {
    if (!warehouseId) return;
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError("");
    setResult(null);
    const timer = window.setTimeout(() => {
      getProducts(
        { warehouseId, query: query.trim(), limit: pageSize, offset },
        controller.signal,
      )
        .then((value) => {
          if (active) setResult(value);
        })
        .catch((caught) => {
          if (active && !controller.signal.aborted)
            setError(apiErrorMessage(caught));
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [warehouseId, query, offset, retry]);

  function changeQuery(value: string) {
    setQuery(value);
    setOffset(0);
  }

  return (
    <section className="apicatalog" aria-label="Каталог товаров">
      <div className="apicatalog-toolbar">
        <label className="catalog-search apicatalog-search">
          <Search size={18} aria-hidden="true" />
          <input
            ref={searchInput}
            value={query}
            maxLength={200}
            onChange={(event) => changeQuery(event.target.value)}
            placeholder="Название или артикул товара"
            aria-label="Поиск по названию или артикулу"
            autoComplete="off"
          />
          {query && (
            <button
              type="button"
              className="icon-button"
              aria-label="Очистить поиск"
              onClick={() => {
                changeQuery("");
                searchInput.current?.focus();
              }}
            >
              <X size={16} />
            </button>
          )}
        </label>
        <label className="apicatalog-warehouse">
          <span>Склад</span>
          <select
            value={warehouseId}
            disabled={warehouseLoading || !warehouses.length}
            onChange={(event) => {
              setWarehouseId(event.target.value);
              setOffset(0);
            }}
            aria-label="Склад для проверки наличия"
          >
            {!warehouses.length && (
              <option value="">
                {warehouseLoading
                  ? "Загружаем склады…"
                  : "Нет данных о складах"}
              </option>
            )}
            {warehouses.map((warehouse) => (
              <option key={warehouse.id} value={warehouse.id}>
                {warehouseLabel(warehouse)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="apicatalog-summary">
        <p className="apicatalog-count" aria-live="polite">
          {result
            ? `Найдено в загруженном наборе: ${numberFormat.format(result.total)}`
            : "Каталог загруженного набора"}
        </p>
        <span className="apicatalog-source-note">
          Наличие показано для выбранного склада, на дату снимка.
        </span>
      </div>

      {warehouseLoading ? (
        <RequestState loading />
      ) : warehouseError ? (
        <RequestState
          error={warehouseError}
          retry={() => setWarehouseRetry((value) => value + 1)}
        />
      ) : loading ? (
        <RequestState loading />
      ) : error ? (
        <RequestState
          error={error}
          retry={() => setRetry((value) => value + 1)}
        />
      ) : (
        result && (
          <>
            {result.items.length ? (
              <div className="apicatalog-grid">
                {result.items.map((product) => (
                  <article className="apicatalog-card" key={product.id}>
                    <ProductVisual product={product} />
                    <div className="apicatalog-card-body">
                      <span className="product-sku">АРТ. {product.sku}</span>
                      <h3>{product.name}</h3>
                      <p className="apicatalog-card-price">
                        {money(product.price_kzt)}
                        {product.price_kzt !== null && (
                          <small> / {product.unit}</small>
                        )}
                      </p>
                      <div className="apicatalog-stock">
                        <span>На выбранном складе</span>
                        <strong>
                          {quantity(product.available_quantity, product.unit)}
                        </strong>
                      </div>
                      <SnapshotLabel snapshot={product.snapshot} />
                      <button
                        className="secondary-button apicatalog-open"
                        onClick={() => setProductId(product.id)}
                      >
                        Открыть карточку
                        <ArrowRight size={16} />
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="empty-state apicatalog-empty">
                <Search size={34} />
                <h2>Товары не найдены</h2>
                <p>
                  {query.trim()
                    ? "Попробуйте другое название или артикул."
                    : "В загруженном наборе пока нет товаров."}
                </p>
                {query && (
                  <button
                    className="secondary-button"
                    onClick={() => changeQuery("")}
                  >
                    Сбросить поиск
                  </button>
                )}
              </div>
            )}
            {result.total > 0 && (
              <nav
                className="apicatalog-pagination"
                aria-label="Страницы каталога"
              >
                <button
                  className="secondary-button"
                  disabled={result.offset === 0}
                  onClick={() =>
                    setOffset(Math.max(0, result.offset - result.limit))
                  }
                >
                  <ArrowLeft size={15} />
                  Назад
                </button>
                <span className="apicatalog-page">
                  {result.offset + 1}–
                  {Math.min(result.offset + result.items.length, result.total)}{" "}
                  из {numberFormat.format(result.total)}
                </span>
                <button
                  className="secondary-button"
                  disabled={result.offset + result.items.length >= result.total}
                  onClick={() => setOffset(result.offset + result.limit)}
                >
                  Далее
                  <ArrowRight size={15} />
                </button>
              </nav>
            )}
          </>
        )
      )}
      {productId !== null && selectedWarehouse && (
        <ProductDialog
          productId={productId}
          warehouse={selectedWarehouse}
          close={() => setProductId(null)}
        />
      )}
    </section>
  );
}
