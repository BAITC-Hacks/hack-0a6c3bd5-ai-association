import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  ClipboardList,
  CornerDownLeft,
  FileCheck2,
  FileText,
  LayoutGrid,
  MapPin,
  MessageSquare,
  Minus,
  Package,
  Plus,
  Search,
  ShieldCheck,
  ShoppingBag,
  SlidersHorizontal,
  Sparkles,
  X,
  Zap,
} from "lucide-react";
import {
  formatMoney,
  products,
  warehouseNames,
  type PreviewProduct,
  type Warehouse,
} from "./design-data";

type Section = "workspace" | "catalog" | "cart";
type Modal = "sources" | "confirm" | "search" | "help" | null;
type Cart = { productId: string; quantity: number; warehouse: Warehouse };
type Message = { role: "user" | "assistant"; text: string };
const storageKey = "kontur-design-cart-v1";

function readCart(): Cart | null {
  try {
    const value: unknown = JSON.parse(
      localStorage.getItem(storageKey) || "null",
    );
    if (
      value &&
      typeof value === "object" &&
      "productId" in value &&
      value.productId === products[1].id &&
      "quantity" in value &&
      Number.isInteger(value.quantity) &&
      Number(value.quantity) > 0 &&
      "warehouse" in value &&
      (value.warehouse === "astana" || value.warehouse === "almaty") &&
      Number(value.quantity) <= products[1].stocks[value.warehouse]
    )
      return value as Cart;
  } catch {
    /* Недоступное хранилище не мешает просмотру концепта. */
  }
  return null;
}

function BrandMark({ small = false }: { small?: boolean }) {
  return (
    <span className={`brand-mark ${small ? "small" : ""}`} aria-hidden="true">
      <span />
      <span />
      <span />
    </span>
  );
}

function Device({
  variant = "blue",
  large = false,
  label,
}: {
  variant?: "blue" | "dark";
  large?: boolean;
  label?: string;
}) {
  return (
    <div className={`device-stage ${large ? "large" : ""}`} aria-hidden="true">
      <div className={`device ${variant}`}>
        <div className="device-top">
          <i />
          <i />
          <i />
        </div>
        <div className="device-face">
          <span className="device-label">
            {label || (variant === "blue" ? "КМ / 160" : "DRX / 250")}
          </span>
          <div className="device-switches">
            <i />
            <i />
            <i />
          </div>
          <span className="device-spec">3P · 400V</span>
          <div className="device-lines">
            <i />
            <i />
            <i />
          </div>
        </div>
        <div className="device-bottom">
          <i />
          <i />
          <i />
        </div>
      </div>
    </div>
  );
}

function Dialog({
  title,
  children,
  close,
  wide = false,
}: {
  title: string;
  children: ReactNode;
  close: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  return (
    <dialog
      ref={ref}
      className={`dialog ${wide ? "wide" : ""}`}
      aria-labelledby="dialog-title"
      onClose={close}
      onPointerDown={(event) => {
        if (event.target !== event.currentTarget) return;
        const bounds = event.currentTarget.getBoundingClientRect();
        if (
          event.clientX < bounds.left || event.clientX > bounds.right ||
          event.clientY < bounds.top || event.clientY > bounds.bottom
        ) close();
      }}
    >
      <div className="dialog-head">
        <h2 id="dialog-title">{title}</h2>
        <button
          className="icon-button"
          aria-label="Закрыть окно"
          onClick={close}
        >
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}

export default function App() {
  const [section, setSection] = useState<Section>(
    location.pathname === "/cart"
      ? "cart"
      : new URLSearchParams(location.search).get("view") === "catalog"
        ? "catalog"
        : "workspace",
  );
  const [warehouse, setWarehouse] = useState<Warehouse>("astana");
  const [warehouseOpen, setWarehouseOpen] = useState(false);
  const [modal, setModal] = useState<Modal>(null);
  const [quantity, setQuantity] = useState(10);
  const [alternative, setAlternative] = useState(false);
  const [selected, setSelected] = useState(false);
  const [cart, setCart] = useState<Cart | null>(readCart);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [query, setQuery] = useState("");
  const [availableOnly, setAvailableOnly] = useState(false);
  const [notice, setNotice] = useState("");
  const [sourceTab, setSourceTab] = useState<"check" | "source">("check");
  const chatEnd = useRef<HTMLDivElement>(null);
  const currentProduct = selected ? products[1] : products[0];
  const stock = currentProduct.stocks[warehouse];
  const canConfirm = selected && quantity > 0 && quantity <= stock;
  const proposalConfirmed =
    selected && cart?.quantity === quantity && cart.warehouse === warehouse;
  const originalShortage = quantity > products[0].stocks[warehouse];
  const alternativeShortage = quantity > products[1].stocks[warehouse];
  const filteredProducts = products.filter(
    (product) =>
      `${product.name} ${product.id} ${product.current}`
        .toLowerCase()
        .includes(query.toLowerCase()) &&
      (modal === "search" ||
        !availableOnly ||
        product.stocks[warehouse] >= quantity),
  );

  const navigate = (next: Section) => {
    setSection(next);
    history.pushState({}, "", next === "workspace" ? "/" : next === "catalog" ? "/?view=catalog" : "/cart");
    setQuery("");
  };
  useEffect(() => {
    const pop = () =>
      setSection(
        location.pathname === "/cart"
          ? "cart"
          : new URLSearchParams(location.search).get("view") === "catalog"
            ? "catalog"
            : "workspace",
      );
    const key = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "k") {
        event.preventDefault();
        setModal("search");
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
    try {
      localStorage.setItem(storageKey, JSON.stringify(cart));
    } catch {
      /* Корзина остаётся доступна в текущей вкладке. */
    }
  }, [cart]);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 4500);
    return () => clearTimeout(timer);
  }, [notice]);
  useEffect(() => {
    if (messages.length)
      chatEnd.current?.scrollIntoView({
        block: "nearest",
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "instant"
          : "smooth",
      });
  }, [messages]);

  function showAlternative() {
    setAlternative(true);
    setNotice("Найден аналог в учебном каталоге");
  }
  function chooseAlternative() {
    setAlternative(true);
    setSelected(true);
    setNotice("Предложение обновлено. Корзина ещё не изменена.");
  }
  function reset() {
    setQuantity(10);
    setAlternative(false);
    setSelected(false);
    setMessages([]);
    setInput("");
    setSourceTab("check");
    navigate("workspace");
    setNotice("Начат новый подбор. Корзина сохранена.");
  }
  function changeWarehouse(value: Warehouse) {
    setWarehouse(value);
    setWarehouseOpen(false);
    setNotice(
      `Выбран склад: ${warehouseNames[value]}. Предложение пересчитано.`,
    );
  }
  function sendMessage(event?: FormEvent, text = input) {
    event?.preventDefault();
    const clean = text.trim();
    if (!clean) return;
    const amount = clean.match(/(\d+)\s*(?:шт|штук|автомат)/i);
    const qty = amount
      ? Math.min(999, Math.max(1, Number(amount[1])))
      : quantity;
    if (amount) setQuantity(qty);
    const effectiveWarehouse: Warehouse = /алмат/i.test(clean)
      ? "almaty"
      : /астан/i.test(clean)
        ? "astana"
        : warehouse;
    if (effectiveWarehouse !== warehouse) setWarehouse(effectiveWarehouse);
    let answer =
      "В этом концепте можно проверить демонстрационный артикул, сравнить аналог и собрать комплект. Попробуйте «Покажи аналог» или «Какие условия покупки?».";
    if (/аналог|замен/i.test(clean)) {
      setAlternative(true);
      answer = `В учебном каталоге есть КМ 160 / 3P: 160 А, три полюса, 400 В. На складе «${warehouseNames[effectiveWarehouse]}» — ${products[1].stocks[effectiveWarehouse]} шт. Проверьте остаток и выберите позицию в карточке аналога.`;
    } else if (/достав|оплат|услов|партия/i.test(clean))
      answer =
        "В демонстрационном сценарии минимальное количество — 1 шт. Реальные условия оплаты и доставки здесь не подключены: их нужно получить из подтверждённого источника ekt.kz. Этот прототип не оформляет заказ.";
    else if (/добав|подтверж/i.test(clean))
      answer = selected
        ? "Проверьте состав и количество в правой панели. Кнопка подтверждения покажет итог, после вашего согласия изменится только демонстрационная корзина."
        : "Сначала нужно решить расхождение характеристик и выбрать подходящую позицию. Исходный товар нельзя добавить как проверенный.";
    else if (/160|200300285|515291|провер|автомат/i.test(clean)) {
      setSelected(false);
      answer = `У исходной позиции расходится номинальный ток: 160 А в описании и 250 А в характеристиках. На выбранном складе — ${products[0].stocks[effectiveWarehouse]} шт., запрошено ${qty}. Показываю это в проверке ниже.`;
    }
    setMessages((previous) => [
      ...previous,
      { role: "user", text: clean },
      { role: "assistant", text: answer },
    ]);
    setInput("");
  }
  function confirm() {
    if (!canConfirm) {
      setModal(null);
      setNotice("Проверьте количество и выбранный товар.");
      return;
    }
    setCart({ productId: products[1].id, quantity, warehouse });
    setModal(null);
    setNotice("Комплект добавлен в демонстрационную корзину");
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
          aria-label="Контур — рабочая область"
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
          <span className="workspace-status" title="Дизайн-прототип" />
        </div>
        <button
          className="sidebar-search"
          aria-label="Найти товар"
          onClick={() => {
            setQuery("");
            setModal("search");
          }}
        >
          <Search size={17} />
          <span>Найти товар</span>
          <kbd>⌘ K</kbd>
        </button>
        <div className="nav-label">РАБОЧЕЕ ПРОСТРАНСТВО</div>
        <nav aria-label="Основная навигация">
          <button
            className={`nav-item ${section === "workspace" ? "active" : ""}`}
            aria-label="Подбор с ассистентом"
            aria-current={section === "workspace" ? "page" : undefined}
            onClick={() => navigate("workspace")}
          >
            <MessageSquare size={18} />
            <span>Подбор с ассистентом</span>
            <span className="active-dot" />
          </button>
          <button
            className={`nav-item ${section === "catalog" ? "active" : ""}`}
            aria-label="Каталог товаров"
            aria-current={section === "catalog" ? "page" : undefined}
            onClick={() => navigate("catalog")}
          >
            <LayoutGrid size={18} />
            <span>Каталог товаров</span>
          </button>
          <button
            className={`nav-item ${section === "cart" ? "active" : ""}`}
            aria-label="Моя корзина"
            aria-current={section === "cart" ? "page" : undefined}
            onClick={() => navigate("cart")}
          >
            <ShoppingBag size={18} />
            <span>Моя корзина</span>
            {cart && <span className="nav-count">1</span>}
          </button>
        </nav>
        <div className="sidebar-divider" />
        <div className="nav-label">
          ТЕКУЩИЙ ПОДБОР <span>01</span>
        </div>
        <button
          className="selection-item"
          onClick={() => navigate("workspace")}
        >
          <span className="selection-line" />
          <span>
            Автоматы для объекта<small>Сегодня · {quantity} шт.</small>
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
          <button className="help-link" onClick={() => setModal("help")}>
            <CircleHelp size={17} />
            Как работает Контур
            <ArrowRight size={15} />
          </button>
          <div className="profile">
            <span className="avatar">М</span>
            <div>
              <strong>Мой рабочий стол</strong>
              <small>Локальная демосессия</small>
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
                ? "Новый подбор"
                : section === "catalog"
                  ? "Каталог"
                  : "Корзина"}
            </strong>
          </div>
          <div className="topbar-actions">
            <span className="concept-label">
              <span />
              Дизайн-прототип
            </span>
            <div className="warehouse-control">
              <button
                className="warehouse-button"
                aria-expanded={warehouseOpen}
                onClick={() => setWarehouseOpen(!warehouseOpen)}
              >
                <MapPin size={15} />
                <span>{warehouseNames[warehouse]}</span>
                <ChevronDown size={14} />
              </button>
              {warehouseOpen && (
                <div className="warehouse-menu">
                  {(["astana", "almaty"] as Warehouse[]).map((value) => (
                    <button key={value} onClick={() => changeWarehouse(value)}>
                      {warehouseNames[value]}
                      {warehouse === value && <Check size={15} />}
                    </button>
                  ))}
                </div>
              )}
            </div>
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
                    : "ТОЛЬКО ТО, ЧТО ВЫ ПОДТВЕРДИЛИ."}
              </div>
              <h1>
                {section === "workspace" ? (
                  <>
                    Точный подбор.<span> Спокойная закупка.</span>
                  </>
                ) : section === "catalog" ? (
                  <>
                    Каталог<span> для вашего объекта.</span>
                  </>
                ) : (
                  <>
                    Ваш комплект<span> готов к проверке.</span>
                  </>
                )}
              </h1>
              <p>
                {section === "workspace"
                  ? "От списка требований — к комплекту, в котором всё сходится."
                  : section === "catalog"
                    ? "Демонстрационные позиции. Все цены и остатки — для проверки интерфейса."
                    : "Демонстрационная корзина. Заказ и резервирование в ekt.kz не выполняются."}
              </p>
            </div>
            <button
              className="new-selection"
              onClick={reset}
              aria-label="Новый подбор"
            >
              <Plus size={16} />
              <span>Новый подбор</span>
            </button>
          </div>

          {section === "workspace" && (
            <div className="workspace-grid">
              <section
                className="conversation"
                aria-label="Подбор с ассистентом"
              >
                <div className="conversation-bar">
                  <div>
                    <span className="session-dot" />
                    <strong>Автоматы для объекта</strong>
                    <span className="small-tag">ПОДБОР 001</span>
                  </div>
                  <button
                    className="icon-button"
                    onClick={() => setModal("help")}
                    aria-label="Информация о сценарии"
                  >
                    <CircleHelp size={17} />
                  </button>
                </div>
                <div className="conversation-content">
                  <div className="day-label">
                    <span />
                    Сегодня
                    <span />
                  </div>
                  <div className="user-message">
                    <div>
                      <p>
                        Нужны {quantity} автоматов на 160 А, 3 полюса.
                        <br />
                        Проверь DRX250 MT. Забрать в{" "}
                        {warehouse === "astana" ? "Астане" : "Алматы"}.
                      </p>
                      <span>
                        Вы <CheckCheck size={13} />
                      </span>
                    </div>
                    <span className="avatar compact">М</span>
                  </div>
                  <div className="assistant-message">
                    <BrandMark small />
                    <div className="assistant-content">
                      <div className="assistant-label">
                        Контур <span>ПРОВЕРКА КАТАЛОГА</span>
                      </div>
                      <h2>
                        Нашёл позицию.
                        <br className="mobile-break" />{" "}
                        {originalShortage
                          ? "Но есть два нюанса."
                          : "Но есть расхождение."}
                      </h2>
                      <p className="assistant-intro">
                        В описании и характеристиках — разный номинальный ток. А
                        на выбранном складе {products[0].stocks[warehouse]} шт.
                        из {quantity} запрошенных.
                      </p>

                      <div className="verification-card">
                        <div className="verification-header">
                          <span className="verification-icon">
                            <SlidersHorizontal size={17} />
                          </span>
                          <strong>Паспорт подбора</strong>
                          <span className="warning-badge">
                            <span />
                            Требует внимания
                          </span>
                        </div>
                        <div
                          className="verification-tabs"
                          role="tablist"
                          aria-label="Паспорт подбора"
                        >
                          <button
                            role="tab"
                            aria-selected={sourceTab === "check"}
                            className={sourceTab === "check" ? "active" : ""}
                            onClick={() => setSourceTab("check")}
                          >
                            Сверка требований
                          </button>
                          <button
                            role="tab"
                            aria-selected={sourceTab === "source"}
                            className={sourceTab === "source" ? "active" : ""}
                            onClick={() => setSourceTab("source")}
                          >
                            Данные источника<span>2</span>
                          </button>
                        </div>
                        {sourceTab === "check" ? (
                          <div className="comparison-table">
                            <div className="comparison-row table-head">
                              <span>Параметр</span>
                              <span>В запросе</span>
                              <span>В каталоге</span>
                              <span />
                            </div>
                            <div className="comparison-row conflict-row">
                              <span>Номинальный ток</span>
                              <strong>160 А</strong>
                              <span>
                                <strong className="conflicting-value">
                                  250 А
                                </strong>
                                <small>в описании — 160 А</small>
                              </span>
                              <span className="state-indicator warn">!</span>
                            </div>
                            <div className="comparison-row">
                              <span>Количество полюсов</span>
                              <strong>3</strong>
                              <strong>3</strong>
                              <Check size={15} className="green" />
                            </div>
                            <div className="comparison-row">
                              <span>
                                На складе · {warehouseNames[warehouse]}
                              </span>
                              <strong>{quantity} шт.</strong>
                              <strong
                                className={
                                  quantity > products[0].stocks[warehouse]
                                    ? "amber"
                                    : ""
                                }
                              >
                                {products[0].stocks[warehouse]} шт.
                              </strong>
                              {quantity > products[0].stocks[warehouse] ? (
                                <span className="state-indicator warn">!</span>
                              ) : (
                                <Check size={15} className="green" />
                              )}
                            </div>
                          </div>
                        ) : (
                          <div className="source-summary">
                            <div>
                              <FileText size={18} />
                              <span>
                                <strong>Название и описание</strong>
                                <small>«DRX250 MT, 3 полюса, 160 А»</small>
                              </span>
                              <b>160 А</b>
                            </div>
                            <div>
                              <ClipboardList size={18} />
                              <span>
                                <strong>Поле «Номинальный ток»</strong>
                                <small>Значение из карточки товара</small>
                              </span>
                              <b className="amber">250 А</b>
                            </div>
                            <p>
                              Значения показаны раздельно. Ассистент не выбирает
                              одно из них наугад.
                            </p>
                          </div>
                        )}
                        <div className="verification-footer">
                          <ShieldCheck size={15} />
                          <span>
                            Противоречие нельзя считать подтверждённой
                            характеристикой.
                          </span>
                          <button
                            onClick={() => setModal("sources")}
                            aria-label="Открыть источники проверки"
                          >
                            <ArrowUp size={15} />
                          </button>
                        </div>
                      </div>

                      <div className="assistant-recommendation">
                        <span className="recommendation-line" />
                        <p>
                          {alternativeShortage
                            ? "Характеристики аналога совпадают, но его остатка также недостаточно. Уменьшите количество или проверьте другой склад."
                            : "Предлагаю посмотреть аналог с согласованными характеристиками и нужным остатком."}
                        </p>
                      </div>
                      {!alternative ? (
                        <button
                          className="alternative-button"
                          onClick={showAlternative}
                        >
                          <Sparkles size={16} />
                          Показать подходящий аналог
                          <ArrowRight size={17} />
                        </button>
                      ) : (
                        <div
                          className={`alternative-card ${selected ? "chosen" : ""}`}
                        >
                          <Device />
                          <div className="alternative-info">
                            <span className="eyebrow blue">
                              УЧЕБНЫЙ КАТАЛОГ
                            </span>
                            <h3>КМ 160 / 3P</h3>
                            <p>
                              160 А <span>·</span> 3 полюса <span>·</span> 400 В
                            </p>
                            <span className="availability">
                              <span />
                              {products[1].stocks[warehouse]} шт. ·{" "}
                              {warehouseNames[warehouse]}
                            </span>
                          </div>
                          <div className="alternative-action">
                            <strong>{formatMoney(products[1].price)}</strong>
                            <button
                              className={
                                selected
                                  ? "selected-button"
                                  : "primary-button compact-button"
                              }
                              onClick={chooseAlternative}
                            >
                              {selected ? (
                                <>
                                  <Check size={15} />
                                  Выбран
                                </>
                              ) : (
                                <>
                                  Выбрать
                                  <ArrowRight size={14} />
                                </>
                              )}
                            </button>
                          </div>
                        </div>
                      )}
                      <div className="assistant-footnote">
                        <FileCheck2 size={13} />
                        Характеристики и остатки проверяются отдельно
                      </div>
                    </div>
                  </div>
                  {messages.map((message, index) => (
                    <div
                      key={index}
                      className={`extra-message ${message.role}`}
                    >
                      {message.role === "assistant" && <BrandMark small />}
                      <p>{message.text}</p>
                    </div>
                  ))}
                  <div ref={chatEnd} />
                </div>
                <div className="composer-area">
                  <div className="quick-prompts">
                    <button
                      onClick={() =>
                        sendMessage(undefined, "Какие условия покупки?")
                      }
                    >
                      Условия покупки
                      <ArrowUp size={11} />
                    </button>
                    <button onClick={() => setModal("sources")}>
                      Почему возникло расхождение?
                      <ArrowUp size={11} />
                    </button>
                  </div>
                  <form className="composer" onSubmit={sendMessage}>
                    <label className="sr-only" htmlFor="chat-input">
                      Сообщение ассистенту
                    </label>
                    <input
                      id="chat-input"
                      value={input}
                      maxLength={4000}
                      onChange={(event) => setInput(event.target.value)}
                      placeholder="Уточните задачу или укажите артикул…"
                      autoComplete="off"
                    />
                    <button
                      className="send-button"
                      disabled={!input.trim()}
                      aria-label="Отправить сообщение"
                    >
                      <ArrowUp size={19} />
                    </button>
                  </form>
                  <div className="composer-caption">
                    <span>
                      Решение остаётся за вами. Добавление — только после
                      подтверждения.
                    </span>
                    <span>
                      <CornerDownLeft size={11} />
                      Отправить
                    </span>
                  </div>
                </div>
              </section>

              <aside className="order-column">
                <div className="order-card">
                  <div className="order-heading">
                    <div>
                      <span className="eyebrow">СОБИРАЕМ ВМЕСТЕ</span>
                      <h2>
                        Ваш комплект<span>01</span>
                      </h2>
                    </div>
                    <ShoppingBag size={21} />
                  </div>
                  <div className="order-progress">
                    <span className="complete" />
                    <span className={selected ? "complete" : "current"} />
                    <span className={proposalConfirmed ? "complete" : ""} />
                  </div>
                  <div className="order-progress-label">
                    <span>
                      {proposalConfirmed
                        ? "Комплект подтверждён"
                        : selected
                          ? canConfirm
                            ? "Готов к подтверждению"
                            : "Недостаточно на складе"
                          : "Проверяем соответствие"}
                    </span>
                    <span>
                      {proposalConfirmed ? "3" : selected ? "2" : "1"} / 3
                    </span>
                  </div>
                  <div className="order-product">
                    <div className="order-product-visual">
                      <Device variant={selected ? "blue" : "dark"} large />
                      <span className="product-corner">
                        {currentProduct.poles}
                      </span>
                    </div>
                    <div className="order-product-meta">
                      <span className="product-category">
                        АВТОМАТИЧЕСКИЙ ВЫКЛЮЧАТЕЛЬ
                      </span>
                      <h3>{currentProduct.name}</h3>
                      <span className="product-sku">
                        АРТ. {currentProduct.id}
                      </span>
                    </div>
                    <div
                      className={`product-status ${canConfirm ? "verified" : ""}`}
                    >
                      {selected ? <Check size={13} /> : <span>!</span>}
                      {selected
                        ? "Характеристики совпадают в демосценарии"
                        : "Характеристики требуют уточнения"}
                    </div>
                  </div>
                  <div className="order-quantity">
                    <div>
                      <span>Количество</span>
                      <small>{stock} шт. на складе</small>
                    </div>
                    <div className="stepper">
                      <button
                        onClick={() =>
                          setQuantity((value) => Math.max(1, value - 1))
                        }
                        disabled={quantity <= 1}
                        aria-label="Уменьшить количество"
                      >
                        <Minus size={13} />
                      </button>
                      <label className="sr-only" htmlFor="quantity">
                        Количество товаров
                      </label>
                      <input
                        id="quantity"
                        inputMode="numeric"
                        value={quantity}
                        onChange={(event) => {
                          const value = Number(event.target.value);
                          if (
                            Number.isInteger(value) &&
                            value >= 1 &&
                            value <= 999
                          )
                            setQuantity(value);
                        }}
                      />
                      <button
                        onClick={() =>
                          setQuantity((value) => Math.min(999, value + 1))
                        }
                        disabled={quantity >= 999}
                        aria-label="Увеличить количество"
                      >
                        <Plus size={13} />
                      </button>
                    </div>
                  </div>
                  <div className="order-price">
                    <span>Цена за единицу</span>
                    <strong>{formatMoney(currentProduct.price)}</strong>
                  </div>
                  <div className="order-total">
                    <span>
                      {selected
                        ? "Итого за комплект"
                        : "Предварительная стоимость"}
                    </span>
                    <strong>
                      {formatMoney(quantity * currentProduct.price)}
                    </strong>
                    <small>
                      {quantity} шт. <span>×</span>{" "}
                      {formatMoney(currentProduct.price)}
                    </small>
                  </div>
                  {quantity > stock && (
                    <p className="quantity-warning">
                      На этом складе недостаточно товара для {quantity} шт.
                    </p>
                  )}
                  {selected ? (
                    <button
                      className="primary-button order-cta"
                      onClick={() => setModal("confirm")}
                      disabled={!canConfirm}
                    >
                      Подтвердить комплект
                      <ArrowRight size={17} />
                    </button>
                  ) : (
                    <button
                      className="primary-button order-cta"
                      onClick={showAlternative}
                    >
                      Рассмотреть аналог
                      <ArrowRight size={17} />
                    </button>
                  )}
                  <p className="cart-promise">
                    <ShieldCheck size={13} />
                    {cart
                      ? "В корзине есть подтверждённый комплект"
                      : "В корзину пока ничего не добавлено"}
                  </p>
                  {cart && (
                    <button
                      className="text-link cart-open"
                      onClick={() => navigate("cart")}
                    >
                      Открыть корзину
                      <ArrowRight size={14} />
                    </button>
                  )}
                </div>
                <div className="context-note">
                  <span className="context-note-icon">
                    <FileCheck2 size={18} />
                  </span>
                  <div>
                    <strong>Покупайте с ясностью</strong>
                    <p>
                      Показываем, что совпало,
                      <br />а что стоит уточнить.
                    </p>
                  </div>
                </div>
                <p className="preview-disclaimer">
                  Интерактивный концепт.
                  <br />
                  Данные и расчёты демонстрационные.
                </p>
              </aside>
            </div>
          )}

          {section === "catalog" && (
            <section className="catalog-view">
              <div className="catalog-toolbar">
                <label className="catalog-search">
                  <Search size={18} />
                  <input
                    placeholder="Название, артикул или номинал"
                    aria-label="Поиск по каталогу"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                  />
                </label>
                <button
                  className={`filter-button ${availableOnly ? "on" : ""}`}
                  aria-pressed={availableOnly}
                  onClick={() => setAvailableOnly(!availableOnly)}
                >
                  <SlidersHorizontal size={16} />
                  Хватит на {quantity} шт.
                </button>
              </div>
              <div className="catalog-grid">
                {filteredProducts.map((product) => (
                  <article className="catalog-card" key={product.id}>
                    <Device
                      variant={product.conflict ? "dark" : "blue"}
                      label={
                        product.id === "DEMO-100-3P" ? "КМ / 100" : undefined
                      }
                      large
                    />
                    <span className="product-category">УЧЕБНЫЙ КАТАЛОГ</span>
                    <h2>{product.name}</h2>
                    <p>{product.subtitle}</p>
                    <div className="catalog-facts">
                      <span>{product.current}</span>
                      <span>{product.poles}</span>
                      <span>{product.voltage}</span>
                    </div>
                    <div className="catalog-price">
                      <strong>{formatMoney(product.price)}</strong>
                      <span>{product.stocks[warehouse]} шт.</span>
                    </div>
                    <button
                      className="catalog-select"
                      onClick={() => {
                        if (product.id === products[1].id) {
                          chooseAlternative();
                          navigate("workspace");
                        } else if (product.conflict) {
                          setSelected(false);
                          navigate("workspace");
                        } else
                          setNotice(
                            "Номинал 100 А не соответствует запросу 160 А. Выберите другой товар.",
                          );
                      }}
                    >
                      Проверить соответствие
                      <ArrowRight size={16} />
                    </button>
                  </article>
                ))}
              </div>
              {!filteredProducts.length && (
                <div className="empty-state">
                  <Search size={34} />
                  <h2>Нет совпадений</h2>
                  <p>Попробуйте «160» или отключите фильтр наличия.</p>
                  <button
                    className="text-link"
                    onClick={() => {
                      setQuery("");
                      setAvailableOnly(false);
                    }}
                  >
                    Сбросить поиск
                  </button>
                </div>
              )}
            </section>
          )}

          {section === "cart" && (
            <section className="cart-view">
              {cart ? (
                <>
                  <div className="cart-success">
                    <span>
                      <Check size={22} />
                    </span>
                    <div>
                      <h2>Состав подтверждён вами</h2>
                      <p>
                        Склад: {warehouseNames[cart.warehouse]} · Локальная
                        демонстрационная корзина
                      </p>
                    </div>
                    <span className="small-tag">1 ПОЗИЦИЯ</span>
                  </div>
                  <div className="cart-line">
                    <Device />
                    <div>
                      <span className="product-category">УЧЕБНЫЙ КАТАЛОГ</span>
                      <h3>{products[1].name}</h3>
                      <p>160 А · 3 полюса · 400 В</p>
                      <span className="product-sku">{products[1].id}</span>
                    </div>
                    <div className="cart-line-quantity">
                      {cart.quantity} шт.
                      <small>{formatMoney(products[1].price)} / шт.</small>
                    </div>
                    <strong>
                      {formatMoney(cart.quantity * products[1].price)}
                    </strong>
                  </div>
                  <div className="cart-summary">
                    <p>
                      <ShieldCheck size={16} />
                      Ничего не заказано и не зарезервировано в ekt.kz.
                    </p>
                    <div>
                      <span>Итого</span>
                      <strong>
                        {formatMoney(cart.quantity * products[1].price)}
                      </strong>
                    </div>
                  </div>
                  <button
                    className="primary-button"
                    onClick={() => {
                      setQuantity(cart.quantity);
                      setWarehouse(cart.warehouse);
                      setSelected(true);
                      setAlternative(true);
                      navigate("workspace");
                    }}
                  >
                    <ArrowLeft size={16} />
                    Вернуться к подбору
                  </button>
                </>
              ) : (
                <div className="empty-state">
                  <ShoppingBag size={40} />
                  <h2>Каждая позиция — с вашего согласия</h2>
                  <p>
                    Выберите товар в подборе и подтвердите комплект.
                    <br />
                    Только после этого он появится здесь.
                  </p>
                  <button
                    className="primary-button"
                    onClick={() => navigate("workspace")}
                  >
                    Перейти к подбору
                    <ArrowRight size={16} />
                  </button>
                </div>
              )}
            </section>
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

      {notice && (
        <div className="toast" role="status">
          <Check size={17} />
          {notice}
          <button
            onClick={() => setNotice("")}
            aria-label="Закрыть уведомление"
          >
            <X size={15} />
          </button>
        </div>
      )}
      {modal === "sources" && (
        <Dialog
          title="Откуда взялись два значения"
          close={() => setModal(null)}
          wide
        >
          <p className="dialog-lead">
            В исходной карточке встретились разные значения одной
            характеристики. В концепте показываем их рядом, сохраняя источник
            каждого.
          </p>
          <div className="source-evidence">
            <span className="source-number">01</span>
            <div>
              <small>НАЗВАНИЕ И ОПИСАНИЕ</small>
              <h3>Номинальный ток — 160 А</h3>
              <p>«027228 АВ DRX250 MT 3ф 160А 18ka Legrand»</p>
            </div>
          </div>
          <div className="source-evidence warning">
            <span className="source-number">02</span>
            <div>
              <small>СТРУКТУРИРОВАННЫЕ ХАРАКТЕРИСТИКИ</small>
              <h3>Номинальный ток — 250 А</h3>
              <p>Поле NOMINALNYY_TOK содержит «250 А».</p>
            </div>
          </div>
          <div className="source-explanation">
            <ShieldCheck size={20} />
            <p>
              <strong>Расхождение требует уточнения.</strong> Мы не делаем
              вывод, какое значение верно. До проверки позиция не считается
              подтверждённым аналогом.
            </p>
          </div>
          <p className="dialog-caption">
            Основано на наблюдении при подготовке проекта 23.09.2026. Остальные
            позиции и расчёты прототипа — учебные, не актуальная оферта
            магазина.
          </p>
          <button
            className="primary-button"
            onClick={() => {
              setModal(null);
              showAlternative();
            }}
          >
            Посмотреть учебный аналог
            <ArrowRight size={16} />
          </button>
        </Dialog>
      )}
      {modal === "confirm" && (
        <Dialog
          title="Подтвердить состав комплекта"
          close={() => setModal(null)}
        >
          <p className="dialog-lead">
            В демонстрационной корзине будет следующая позиция. Существующее
            количество этой позиции заменится указанным.
          </p>
          <div className="confirm-product">
            <Device />
            <div>
              <h3>{products[1].name}</h3>
              <p>
                {quantity} шт. · {warehouseNames[warehouse]}
              </p>
              <strong>{formatMoney(quantity * products[1].price)}</strong>
            </div>
          </div>
          <div className="source-explanation">
            <ShieldCheck size={18} />
            <p>
              Это действие изменяет только локальный прототип. Заказ в ekt.kz не
              создаётся.
            </p>
          </div>
          <div className="dialog-actions">
            <button className="secondary-button" onClick={() => setModal(null)}>
              Вернуться
            </button>
            <button
              className="primary-button"
              onClick={confirm}
              disabled={!canConfirm}
            >
              <Check size={16} />
              Подтверждаю добавление
            </button>
          </div>
        </Dialog>
      )}
      {modal === "search" && (
        <Dialog
          title="Найти товар"
          close={() => {
            setModal(null);
            setQuery("");
          }}
        >
          <label className="catalog-search modal-search">
            <Search size={18} />
            <input
              autoFocus
              placeholder="Например, 160 или DRX"
              aria-label="Поиск товара"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <div className="search-results">
            {filteredProducts.map((product: PreviewProduct) => (
              <button
                key={product.id}
                onClick={() => {
                  setModal(null);
                  navigate("catalog");
                  setQuery(product.id);
                }}
              >
                <Package size={21} />
                <span>
                  <strong>{product.name}</strong>
                  <small>{product.id}</small>
                </span>
                <ArrowRight size={17} />
              </button>
            ))}
            {!filteredProducts.length && (
              <p>В учебном каталоге нет такого товара. Попробуйте «160».</p>
            )}
          </div>
          <p className="dialog-caption">
            Поиск работает по трём позициям дизайн-прототипа.
          </p>
        </Dialog>
      )}
      {modal === "help" && (
        <Dialog
          title="От запроса — к ясному решению"
          close={() => setModal(null)}
        >
          <div className="help-steps">
            <div>
              <span>1</span>
              <section>
                <h3>Опишите, что нужно</h3>
                <p>Количество, характеристики и склад — в одном запросе.</p>
              </section>
            </div>
            <div>
              <span>2</span>
              <section>
                <h3>Проверьте основания</h3>
                <p>
                  Контур показывает совпадения, противоречия и доступный аналог.
                </p>
              </section>
            </div>
            <div>
              <span>3</span>
              <section>
                <h3>Подтвердите комплект</h3>
                <p>
                  Позиции появляются в корзине только после вашего согласия.
                </p>
              </section>
            </div>
          </div>
          <p className="dialog-caption">
            Сейчас открыт интерактивный дизайн-концепт: три учебные позиции,
            ограниченный диалог, без подключения backend, оплаты и реальных
            заказов.
          </p>
          <button className="primary-button" onClick={() => setModal(null)}>
            Понятно
            <Check size={16} />
          </button>
        </Dialog>
      )}
    </div>
  );
}
