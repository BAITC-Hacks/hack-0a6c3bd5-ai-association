import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronRight,
  CircleHelp,
  FileCheck2,
  FileUp,
  LayoutGrid,
  LoaderCircle,
  MapPin,
  MessageSquare,
  Package,
  RefreshCw,
  Search,
  ShieldCheck,
  ShoppingBag,
  X,
  Zap,
} from "lucide-react";
import clsx from "clsx";
import CatalogPanel from "./CatalogPanel";
import ChatPanel from "./ChatPanel";
import CartPanel from "./CartPanel";
import UploadPanel from "./UploadPanel";
import { useCommerce } from "./useCommerce";
import { isRemoval, usePendingProposal } from "./proposal";
import { DecisionBar, StepRail, useCompactScreen } from "./path";
import { money, plural } from "./format";

type Section = "workspace" | "catalog" | "cart" | "upload";
function readSection(): Section {
  if (location.pathname === "/cart") return "cart";
  const view = new URLSearchParams(location.search).get("view");
  return view === "catalog" || view === "upload" ? view : "workspace";
}
function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <span />
      <span />
      <span />
    </span>
  );
}
function Dialog({
  title,
  children,
  close,
  locked = false,
}: {
  title: string;
  children: ReactNode;
  close: () => void;
  locked?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  return (
    <dialog
      ref={ref}
      className="dialog purchase-dialog"
      aria-labelledby="dialog-title"
      onCancel={(event) => {
        if (locked) event.preventDefault();
      }}
      onClose={close}
      onPointerDown={(event) => {
        if (locked || event.target !== event.currentTarget) return;
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
        <h2 id="dialog-title">{title}</h2>
        <button
          className="icon-button"
          aria-label="Закрыть окно"
          onClick={close}
          disabled={locked}
        >
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}

export default function App() {
  const commerce = useCommerce();
  const [section, setSection] = useState<Section>(readSection);
  const [catalogFocus, setCatalogFocus] = useState(0);
  const [help, setHelp] = useState(false);
  const [confirmationId, setConfirmationId] = useState<string | null>(null);
  const [barHidden, setBarHidden] = useState<string | null>(null);
  const compact = useCompactScreen();
  const { proposal, pending } = usePendingProposal(
    commerce.latest,
    commerce.warehouseId,
  );
  const warehouse = commerce.warehouses.find(
    (value) => value.id === commerce.warehouseId,
  );
  const cartWarehouse = commerce.warehouses.find(
    (value) => value.id === commerce.cart?.warehouse_id,
  );
  const canConfirm = commerce.ready && !commerce.busy && pending;
  const hasRemoval = proposal ? isRemoval(proposal, commerce.cart) : false;
  const step: 1 | 2 | 3 = pending
    ? 3
    : commerce.latest || commerce.document
      ? 2
      : 1;
  const navigate = (next: Section) => {
    setSection(next);
    history.pushState(
      {},
      "",
      next === "cart" ? "/cart" : next === "workspace" ? "/" : `/?view=${next}`,
    );
    if (next === "cart" && commerce.ready && !commerce.busy)
      void commerce.refresh();
  };
  const openSearch = () => {
    navigate("catalog");
    setCatalogFocus((value) => value + 1);
  };
  useEffect(() => {
    const pop = () => setSection(readSection());
    const key = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSection("catalog");
        history.pushState({}, "", "/?view=catalog");
        setCatalogFocus((value) => value + 1);
      }
    };
    window.addEventListener("popstate", pop);
    window.addEventListener("keydown", key);
    return () => {
      window.removeEventListener("popstate", pop);
      window.removeEventListener("keydown", key);
    };
  }, []);
  useEffect(() => {
    if (confirmationId && proposal?.id !== confirmationId)
      setConfirmationId(null);
  }, [proposal?.id, confirmationId]);

  function openConfirmation() {
    if (proposal?.status === "pending") setConfirmationId(proposal.id);
  }
  async function sendFromCart(message: string) {
    if (
      commerce.cart?.warehouse_id &&
      commerce.cart.warehouse_id !== commerce.warehouseId
    )
      commerce.setWarehouseId(commerce.cart.warehouse_id);
    navigate("workspace");
    await commerce.send(message);
  }
  async function confirm() {
    if (
      !canConfirm ||
      proposal?.id !== confirmationId ||
      Date.parse(proposal.expires_at) <= Date.now()
    )
      return;
    await commerce.confirm();
    setConfirmationId(null);
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="/"
          onClick={(event) => {
            event.preventDefault();
            navigate("workspace");
          }}
          aria-label="Контур — подбор"
        >
          <BrandMark />
          <span>
            контур<span className="brand-dot">.</span>
          </span>
        </a>
        <div className="workspace-label">
          <span className="workspace-icon">
            <Zap size={15} />
          </span>
          <div>
            <strong>Электрокомплект</strong>
            <small>Пространство закупки</small>
          </div>
          <span className="workspace-status" title="Локальная сессия" />
        </div>
        <button
          className="sidebar-search"
          aria-label="Найти товар"
          onClick={openSearch}
        >
          <Search size={17} />
          <span>Найти товар</span>
          <kbd>⌘ K</kbd>
        </button>
        <div className="nav-label">РАБОЧЕЕ ПРОСТРАНСТВО</div>
        <nav aria-label="Основная навигация">
          <button
            className={clsx("nav-item", section === "workspace" && "active")}
            aria-label="Подбор с ассистентом"
            aria-current={section === "workspace" ? "page" : undefined}
            onClick={() => navigate("workspace")}
          >
            <MessageSquare size={18} />
            <span>{compact ? "Подбор" : "Подбор с ассистентом"}</span>
            <span className="active-dot" />
          </button>
          <button
            className={clsx("nav-item", section === "catalog" && "active")}
            aria-label="Каталог товаров"
            aria-current={section === "catalog" ? "page" : undefined}
            onClick={() => navigate("catalog")}
          >
            <LayoutGrid size={18} />
            <span>{compact ? "Каталог" : "Каталог товаров"}</span>
          </button>
          <button
            className={clsx("nav-item", section === "upload" && "active")}
            aria-label="Спецификация из файла"
            aria-current={section === "upload" ? "page" : undefined}
            onClick={() => navigate("upload")}
          >
            <FileUp size={18} />
            <span>{compact ? "Файл" : "Спецификация"}</span>
          </button>
          <button
            className={clsx("nav-item", section === "cart" && "active")}
            aria-label="Моя корзина"
            aria-current={section === "cart" ? "page" : undefined}
            onClick={() => navigate("cart")}
          >
            <ShoppingBag size={18} />
            <span>{compact ? "Корзина" : "Моя корзина"}</span>
            {!!commerce.cart?.items.length && (
              <span className="nav-count">{commerce.cart.items.length}</span>
            )}
          </button>
        </nav>
        <div className="sidebar-divider" />
        <div className="nav-label">ТЕКУЩАЯ СЕССИЯ</div>
        <button
          className="selection-item"
          onClick={() => navigate("workspace")}
        >
          <span className="selection-line" />
          <span>
            Ваш подбор
            <small>
              {commerce.messages.length
                ? `${commerce.messages.filter((message) => message.role === "user").length} ${plural(
                    commerce.messages.filter(
                      (message) => message.role === "user",
                    ).length,
                    "запрос",
                    "запроса",
                    "запросов",
                  )}`
                : "Начните с артикула или задачи"}
            </small>
          </span>
        </button>
        <div className="sidebar-bottom">
          <div className="trust-note">
            <ShieldCheck size={23} />
            <h3>
              Сначала проверим.
              <br />
              Потом добавим.
            </h3>
            <p>
              Каждая рекомендация —<br />с понятным основанием.
            </p>
            <span className="trust-line" />
          </div>
          <button className="help-link" onClick={() => setHelp(true)}>
            <CircleHelp size={17} />
            Как работает Контур
            <ArrowRight size={15} />
          </button>
          <div className="profile">
            <span className="avatar">М</span>
            <div>
              <strong>Мой рабочий стол</strong>
              <small>Анонимная сессия</small>
            </div>
            <span className="profile-dot" />
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Рабочая область</span>
            <ChevronRight size={14} />
            <strong>
              {section === "workspace"
                ? "Подбор"
                : section === "catalog"
                  ? "Каталог"
                  : section === "upload"
                    ? "Спецификация"
                    : "Корзина"}
            </strong>
          </div>
          <div className="topbar-actions">
            <span className="concept-label">
              <span />
              Снимок каталога
            </span>
            {section !== "catalog" && (
              <label className="live-warehouse">
                <MapPin size={15} />
                <select
                  aria-label="Склад подбора"
                  value={commerce.warehouseId}
                  disabled={!commerce.ready || commerce.busy}
                  onChange={(event) =>
                    commerce.setWarehouseId(event.target.value)
                  }
                >
                  {!commerce.warehouses.length && (
                    <option value="">Подключение…</option>
                  )}
                  {commerce.warehouses.map((value) => (
                    <option key={value.id} value={value.id}>
                      {value.city}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                <span />
                {section === "workspace"
                  ? "ВАША ЗАДАЧА. НАШЕ ВНИМАНИЕ К ДЕТАЛЯМ."
                  : section === "catalog"
                    ? "НАЙТИ. СРАВНИТЬ. ПРОВЕРИТЬ."
                    : section === "upload"
                      ? "ИЗ ДОКУМЕНТА — В ПРОВЕРЕННЫЙ КОМПЛЕКТ."
                      : "ТОЛЬКО ТО, ЧТО ВЫ ПОДТВЕРДИЛИ."}
              </div>
              <h1>
                {section === "workspace" ? (
                  <>
                    Точный подбор.<span> Спокойная закупка.</span>
                  </>
                ) : section === "catalog" ? (
                  <>
                    Каталог<span> с проверяемыми данными.</span>
                  </>
                ) : section === "upload" ? (
                  <>
                    Ваша спецификация.<span> Каждая строка на виду.</span>
                  </>
                ) : (
                  <>
                    Ваш комплект.<span> Решение за вами.</span>
                  </>
                )}
              </h1>
              <p>
                {section === "workspace"
                  ? "От списка требований — к комплекту, в котором всё сходится."
                  : section === "catalog"
                    ? "Товары из локального снимка. Поиск, характеристики и остаток выбранного склада."
                    : section === "upload"
                      ? "Загрузите файл, уточните позиции и проверьте их по каталогу выбранного склада."
                      : "Подтверждённые позиции вашей сессии. Заказ и резервирование в ekt.kz не выполняются."}
              </p>
            </div>
            <div className="heading-actions">
              {section === "workspace" && (
                <button
                  className="new-selection"
                  aria-label="Загрузить спецификацию"
                  onClick={() => navigate("upload")}
                >
                  <FileUp size={16} />
                  <span>Из файла</span>
                </button>
              )}
              <button
                className="new-selection"
                aria-label={
                  section === "cart"
                    ? "Вернуться к подбору"
                    : "Перейти в корзину"
                }
                onClick={() =>
                  navigate(section === "cart" ? "workspace" : "cart")
                }
              >
                {section === "cart" ? (
                  <ArrowLeft size={16} />
                ) : (
                  <ShoppingBag size={16} />
                )}
                <span>{section === "cart" ? "К подбору" : "Корзина"}</span>
              </button>
            </div>
          </div>
          {commerce.error && (
            <div className="commerce-error" role="alert">
              <div>
                <strong>Не удалось завершить действие</strong>
                <p>{commerce.error}</p>
              </div>
              <button
                className="secondary-button"
                onClick={() => void commerce.retry()}
                disabled={commerce.busy}
              >
                <RefreshCw size={15} />
                {commerce.retryLabel}
              </button>
              <button
                className="icon-button"
                onClick={commerce.dismissError}
                aria-label="Закрыть сообщение об ошибке"
              >
                <X size={17} />
              </button>
            </div>
          )}
          {commerce.booting && (
            <div className="commerce-connecting" role="status">
              <LoaderCircle size={16} />
              Подключаем вашу сессию…
            </div>
          )}
          {(section === "workspace" || section === "upload") && (
            <StepRail current={step} />
          )}
          {section === "workspace" && (
            <>
              {commerce.document && (
                <div className="document-return">
                  <FileCheck2 size={20} />
                  <div>
                    <strong>{commerce.document.fileName}</strong>
                    <span>
                      Строки спецификации можно уточнить и проверить повторно.
                    </span>
                  </div>
                  <button
                    className="secondary-button"
                    onClick={() => navigate("upload")}
                  >
                    Исправить строки
                    <ArrowRight size={15} />
                  </button>
                </div>
              )}
              <ChatPanel
                messages={commerce.messages}
                latest={commerce.latest}
                cart={commerce.cart}
                warehouseId={commerce.warehouseId}
                warehouses={commerce.warehouses}
                busy={commerce.busy}
                ready={commerce.ready}
                onSend={commerce.send}
                onConfirm={openConfirmation}
                onOpenUpload={() => navigate("upload")}
                onOpenCatalog={openSearch}
                onOpenCart={() => navigate("cart")}
              />
            </>
          )}
          {section === "upload" && (
            <UploadPanel
              document={commerce.document}
              result={commerce.documentResultId ? commerce.latest : null}
              cart={commerce.cart}
              warehouses={commerce.warehouses}
              warehouseId={commerce.warehouseId}
              ready={commerce.ready}
              busy={commerce.busy}
              warehouseName={warehouse?.city || warehouse?.name || ""}
              onConfirm={openConfirmation}
              onUpload={commerce.uploadFile}
              onChangeLine={commerce.updateDocumentLine}
              onPropose={commerce.proposeDocument}
              onReset={commerce.resetDocument}
              onOpenChat={() => navigate("workspace")}
            />
          )}
          {section === "catalog" && (
            <CatalogPanel
              focusRequest={catalogFocus}
              selectedWarehouseId={commerce.warehouseId}
              disabledWarehouse={commerce.busy || !commerce.ready}
              onWarehouseChange={commerce.setWarehouseId}
              onDiscuss={
                commerce.ready && !commerce.busy
                  ? (product) => {
                      navigate("workspace");
                      void commerce.send(`Покажи ${product.sku}`);
                    }
                  : undefined
              }
            />
          )}
          {section === "cart" && (
            <CartPanel
              cart={commerce.cart}
              ready={commerce.ready}
              busy={commerce.busy}
              warehouseName={
                cartWarehouse?.city || commerce.cart?.warehouse_id || ""
              }
              onSend={sendFromCart}
              onBrowse={() => navigate("catalog")}
              onRefresh={commerce.refresh}
            />
          )}
          {compact && pending && proposal && barHidden !== proposal.id && (
            <DecisionBar
              proposal={proposal}
              removal={hasRemoval}
              busy={commerce.busy || !commerce.ready}
              onConfirm={openConfirmation}
              onDismiss={() => setBarHidden(proposal.id)}
            />
          )}
          <footer className="page-footer">
            <span>
              КОНТУР <span className="footer-separator">/</span> ВНИМАНИЕ К
              КАЖДОЙ ПОЗИЦИИ
            </span>
            <span>HackAlem AI · 2026</span>
          </footer>
        </main>
      </div>
      {confirmationId && proposal?.id === confirmationId && (
        <Dialog
          title={
            hasRemoval
              ? "Подтвердить изменение корзины"
              : "Подтвердить состав комплекта"
          }
          close={() => setConfirmationId(null)}
          locked={commerce.busy}
        >
          <p className="dialog-lead">
            Проверьте итоговое количество каждой позиции. Неуказанные позиции
            останутся в корзине. Склад:{" "}
            {warehouse?.city || proposal.warehouse_id}.
          </p>
          <div className="purchase-items">
            {proposal.items.map((item) => {
              const product = commerce.latest?.products.find(
                (value) => value.id === item.product_id,
              );
              const existing = commerce.cart?.items.find(
                (value) => value.product_id === item.product_id,
              );
              return (
                <div key={item.product_id}>
                  <Package size={22} />
                  <div>
                    <strong>
                      {product?.name ||
                        existing?.name ||
                        `Товар № ${item.product_id}`}
                    </strong>
                    <small>
                      {product?.sku || existing?.sku} ·{" "}
                      {item.target_quantity === 0
                        ? "Удаление из корзины"
                        : `Итоговое количество: ${item.target_quantity} ${product?.unit || existing?.unit || ""}`}
                    </small>
                  </div>
                  <span>
                    {money(item.unit_price_kzt)} /{" "}
                    {product?.unit || existing?.unit || "ед."}
                  </span>
                </div>
              );
            })}
          </div>
          <div className="purchase-total">
            <span>Итог всей корзины</span>
            <strong>{money(proposal.result_total_kzt)}</strong>
          </div>
          <div className="source-explanation">
            <ShieldCheck size={18} />
            <p>
              Сервер повторно проверит цену, остаток и состав. Подтверждение
              изменит локальную корзину; заказ в ekt.kz не создаётся.
            </p>
          </div>
          {!canConfirm && !commerce.busy && (
            <p role="status" className="quantity-warning">
              Предложение больше недоступно. Отправьте запрос заново, чтобы
              проверить актуальные данные.
            </p>
          )}
          <div className="dialog-actions">
            <button
              className="secondary-button"
              onClick={() => setConfirmationId(null)}
              disabled={commerce.busy}
            >
              Вернуться
            </button>
            <button
              className="primary-button"
              disabled={!canConfirm}
              onClick={() => void confirm()}
            >
              {commerce.busy ? <LoaderCircle size={16} /> : <Check size={16} />}
              {commerce.busy
                ? "Подтверждаем…"
                : hasRemoval
                  ? "Подтверждаю изменение"
                  : "Подтверждаю добавление"}
            </button>
          </div>
        </Dialog>
      )}
      {help && (
        <Dialog
          title="От запроса — к ясному решению"
          close={() => setHelp(false)}
        >
          <div className="help-steps">
            <div>
              <span>1</span>
              <section>
                <h3>Опишите задачу или загрузите спецификацию</h3>
                <p>
                  Контур проверит данные загруженного каталога и выбранного
                  склада. Строки файла сначала покажем для проверки и
                  исправления.
                </p>
              </section>
            </div>
            <div>
              <span>2</span>
              <section>
                <h3>Посмотрите основания</h3>
                <p>
                  Описание, характеристики и остатки показаны раздельно.
                  Расхождения блокируют предложение покупки.
                </p>
              </section>
            </div>
            <div>
              <span>3</span>
              <section>
                <h3>Подтвердите изменение</h3>
                <p>
                  Только после вашего подтверждения сервер изменит корзину
                  текущей сессии. Повторный клик не удваивает количество.
                </p>
              </section>
            </div>
          </div>
          <p className="dialog-caption">
            Цены и остатки относятся к сохранённому снимку. Учебные позиции явно
            обозначены; реальная оплата и резервирование не выполняются. Корзина
            хранится на сервере, история диалога в этой версии — только в
            открытой вкладке. Редактируемые строки файла также сохраняются
            только до перезагрузки страницы.
          </p>
          <button className="primary-button" onClick={() => setHelp(false)}>
            Понятно
            <FileCheck2 size={16} />
          </button>
        </Dialog>
      )}
    </div>
  );
}
