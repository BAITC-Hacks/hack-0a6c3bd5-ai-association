import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  ArrowRight,
  ArrowUp,
  Check,
  ChevronDown,
  Clock3,
  FileCheck2,
  FileText,
  Layers3,
  LoaderCircle,
  MapPin,
  MessageSquare,
  Package,
  ShieldCheck,
  ShoppingBag,
  SlidersHorizontal,
  Sparkles,
  TriangleAlert,
} from "lucide-react";
import {
  localAssetUrl,
  type Cart,
  type ChatResponse,
  type Check as ProductCheck,
  type Product,
  type Warehouse,
} from "./api";
import type { ChatEntry } from "./useCommerce";

interface ChatPanelProps {
  messages: ChatEntry[];
  latest: ChatResponse | null;
  cart: Cart | null;
  warehouseId: string;
  warehouses: Warehouse[];
  busy: boolean;
  ready: boolean;
  onSend: (message: string) => Promise<void>;
  onConfirm: () => void;
  onOpenCart: () => void;
}

const numbers = new Intl.NumberFormat("ru-RU");
const dateTime = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Asia/Almaty",
});
const money = (value: number | null) =>
  value === null ? "Цена не указана" : `${numbers.format(value)} ₸`;
const timeLabel = (value: string) =>
  Number.isNaN(Date.parse(value))
    ? "Время не указано"
    : dateTime.format(new Date(value));
const fieldNames: Record<string, string> = {
  current_a: "Номинальный ток, А",
  poles: "Количество полюсов",
  voltage_v: "Напряжение, В",
  breaking_capacity_ka: "Отключающая способность, кА",
  price_kzt: "Цена, ₸",
  min_order_quantity: "Минимальная партия",
  available_quantity: "Остаток на складе",
  name: "Название товара",
  description: "Описание товара",
};
const sourceLabels: Record<ChatResponse["answer_source"], string> = {
  fixture: "Офлайн-ответ",
  rules: "Проверка правилами",
  openai: "AI-ответ",
};
const prompts = [
  {
    title: "Проверить артикул",
    detail: "200300285_",
    message: "Проверь товар 200300285_",
  },
  {
    title: "Подобрать автомат",
    detail: "2 штуки · 160 А",
    message: "Подбери 2 штуки на 160 А",
  },
  {
    title: "Условия покупки",
    detail: "Оплата и доставка",
    message: "Какие условия покупки?",
  },
];

function KonturSymbol() {
  return (
    <span className="commerce-symbol" aria-hidden="true">
      <i />
      <i />
      <i />
    </span>
  );
}

function CheckState({ check }: { check: ProductCheck }) {
  if (check.status === "conflict")
    return (
      <span className="commerce-check-state conflict">
        <TriangleAlert size={13} />
        Расхождение
      </span>
    );
  if (check.status === "unknown")
    return <span className="commerce-check-state unknown">Нет данных</span>;
  return (
    <span className="commerce-check-state match">
      <Check size={13} />
      {check.expected === null ? "Есть данные" : "Совпадает"}
    </span>
  );
}

function Evidence({
  response,
  expanded,
}: {
  response: ChatResponse;
  expanded: boolean;
}) {
  if (!response.checks.length) return null;
  const productIds = [
    ...new Set(response.checks.map((check) => check.product_id)),
  ];
  const conflicts = response.checks.filter(
    (check) => check.status === "conflict",
  ).length;
  return (
    <details className="commerce-evidence" open={expanded}>
      <summary>
        <span className="commerce-evidence-icon">
          <SlidersHorizontal size={17} />
        </span>
        <span>
          <strong>Паспорт подбора</strong>
          <small>
            {conflicts
              ? `Расхождений: ${conflicts}`
              : "Основания ответа по данным каталога"}
          </small>
        </span>
        <ChevronDown size={16} className="commerce-disclosure" />
      </summary>
      <div className="commerce-evidence-content">
        {productIds.map((productId) => {
          const product = response.products.find(
            (item) => item.id === productId,
          );
          return (
            <section className="commerce-check-group" key={productId}>
              <h4>{product ? product.sku : `Товар ${productId}`}</h4>
              <div className="commerce-check-heading" aria-hidden="true">
                <span>Параметр</span>
                <span>Ожидается</span>
                <span>В источнике</span>
              </div>
              {response.checks
                .filter((check) => check.product_id === productId)
                .map((check, index) => (
                  <div
                    className={`commerce-check-row ${check.status}`}
                    key={`${check.field}-${index}`}
                  >
                    <div className="commerce-check-values">
                      <span>{fieldNames[check.field] || check.field}</span>
                      <strong>{check.expected ?? "Не задано"}</strong>
                      <strong>{check.actual ?? "Нет данных"}</strong>
                    </div>
                    <div className="commerce-check-bottom">
                      <CheckState check={check} />
                      {check.sources.length > 0 && (
                        <details className="commerce-origins">
                          <summary>
                            Источники <span>{check.sources.length}</span>
                          </summary>
                          <dl>
                            {check.sources.map((source, sourceIndex) => (
                              <div key={`${source.field}-${sourceIndex}`}>
                                <dt>
                                  {fieldNames[source.field] || source.field}
                                </dt>
                                <dd>{source.value}</dd>
                              </div>
                            ))}
                          </dl>
                        </details>
                      )}
                    </div>
                  </div>
                ))}
            </section>
          );
        })}
        <p className="commerce-evidence-note">
          <ShieldCheck size={14} />
          Исходные значения сохранены. Расхождение требует уточнения.
        </p>
      </div>
    </details>
  );
}

function ResponseProduct({
  product,
  warehouse,
  busy,
  onDiscuss,
  onPrepare,
}: {
  product: Product;
  warehouse: string;
  busy: boolean;
  onDiscuss: () => void;
  onPrepare: () => void;
}) {
  const source =
    product.snapshot.source === "demo_fixture" && !product.snapshot.source_url
      ? "Учебная позиция"
      : "Снимок каталога";
  return (
    <article className="commerce-product">
      <div className="commerce-product-head">
        <span className="commerce-product-icon">
          <Package size={22} />
        </span>
        <div>
          <span className="commerce-product-sku">{product.sku}</span>
          <h3>{product.name}</h3>
        </div>
      </div>
      <dl className="commerce-product-facts">
        <div>
          <dt>Цена за {product.unit}</dt>
          <dd>{money(product.price_kzt)}</dd>
        </div>
        <div>
          <dt>На складе · {warehouse}</dt>
          <dd
            className={product.available_quantity === 0 ? "commerce-zero" : ""}
          >
            {product.available_quantity === null
              ? "Нет данных"
              : `${numbers.format(product.available_quantity)} ${product.unit}${product.available_quantity === 0 ? " · нет в наличии" : ""}`}
          </dd>
        </div>
      </dl>
      <p className="commerce-product-source">
        <Clock3 size={12} />
        {source} · {timeLabel(product.snapshot.captured_at)}
      </p>
      {product.documents.length > 0 && (
        <div className="commerce-product-docs">
          {product.documents.map((document, index) => {
            const url = localAssetUrl(document.url);
            return url ? (
              <a
                key={`${document.url}-${index}`}
                href={url}
                target="_blank"
                rel="noopener noreferrer"
              >
                <FileText size={14} />
                {document.title ||
                  (document.kind === "certificate"
                    ? "Сертификат"
                    : "Технический лист")}
              </a>
            ) : (
              <span key={`${document.url}-${index}`}>
                <FileText size={14} />
                {document.title || "Документ"}: локальная копия не предоставлена
              </span>
            );
          })}
        </div>
      )}
      <div className="commerce-product-actions">
        <button type="button" onClick={onDiscuss} disabled={busy}>
          Обсудить товар
          <ArrowRight size={14} />
        </button>
        <button type="button" onClick={onPrepare} disabled={busy}>
          Указать количество
        </button>
      </div>
    </article>
  );
}

export default function ChatPanel({
  messages,
  latest,
  cart,
  warehouseId,
  warehouses,
  busy,
  ready,
  onSend,
  onConfirm,
  onOpenCart,
}: ChatPanelProps) {
  const [input, setInput] = useState("");
  const [sendError, setSendError] = useState("");
  const [now, setNow] = useState(Date.now());
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const proposal = latest?.proposal ?? null;
  const proposalExpired = proposal
    ? Date.parse(proposal.expires_at) <= now
    : false;
  const pending = Boolean(
    proposal &&
      proposal.status === "pending" &&
      latest?.confirmation_required &&
      proposal.warehouse_id === warehouseId &&
      !proposalExpired,
  );
  const warehouse = warehouses.find((item) => item.id === warehouseId);
  const proposalWarehouse = warehouses.find(
    (item) => item.id === proposal?.warehouse_id,
  );
  const lastAssistantId = [...messages]
    .reverse()
    .find((message) => message.role === "assistant")?.id;

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 15000);
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => {
    if (!messages.length) return;
    const thread = bottomRef.current?.closest<HTMLElement>(".commerce-thread");
    thread?.scrollTo({
      top: thread.scrollHeight,
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
    });
  }, [messages.length, busy]);

  async function send(message: string) {
    const text = message.trim();
    if (!text || busy || !ready) return;
    setSendError("");
    try {
      await onSend(text);
      setInput("");
    } catch (error) {
      setSendError(
        error instanceof Error
          ? error.message
          : "Не удалось отправить сообщение. Повторите попытку.",
      );
    }
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    void send(input);
  }
  function prepare(product: Product) {
    setInput(`Добавь количество:  ${product.unit} ${product.sku}`);
    inputRef.current?.focus();
    window.requestAnimationFrame(() =>
      inputRef.current?.setSelectionRange(
        "Добавь количество: ".length,
        "Добавь количество: ".length,
      ),
    );
  }

  return (
    <div className="commerce-layout">
      <section
        className="commerce-conversation"
        aria-label="Консультация по товарам"
      >
        <header className="commerce-conversation-head">
          <div>
            <span className={`commerce-status-dot ${ready ? "ready" : ""}`} />
            <strong>Подбор с ассистентом</strong>
          </div>
          <span className="commerce-location">
            <MapPin size={13} />
            {warehouse?.city || warehouse?.name || "Выберите склад"}
          </span>
        </header>
        <div className="commerce-thread" aria-busy={busy}>
          {!messages.length && (
            <div className="commerce-welcome">
              <KonturSymbol />
              <span className="commerce-eyebrow">
                Внимание к каждой позиции
              </span>
              <h2>
                Что нужно
                <br />
                <span>для вашего объекта?</span>
              </h2>
              <p>
                Укажите артикул или опишите задачу. Проверим характеристики и
                наличие, а решение о корзине останется за вами.
              </p>
              <div className="commerce-process">
                <span>
                  <MessageSquare size={15} />
                  Запрос
                </span>
                <i />
                <span>
                  <SlidersHorizontal size={15} />
                  Сверка
                </span>
                <i />
                <span>
                  <Check size={15} />
                  Ваше решение
                </span>
              </div>
              <div className="commerce-start-prompts">
                {prompts.map((prompt) => (
                  <button
                    type="button"
                    key={prompt.message}
                    disabled={busy || !ready}
                    onClick={() => void send(prompt.message)}
                  >
                    <span>
                      <strong>{prompt.title}</strong>
                      <small>{prompt.detail}</small>
                    </span>
                    <ArrowRight size={17} />
                  </button>
                ))}
              </div>
            </div>
          )}
          <div
            className="commerce-messages"
            role="log"
            aria-label="История консультации"
            aria-live="polite"
            aria-relevant="additions"
          >
            {messages.map((message) =>
              message.role === "user" ? (
                <article className="commerce-message user" key={message.id}>
                  <span className="commerce-message-author">Вы</span>
                  <p>{message.text}</p>
                </article>
              ) : (
                <article
                  className="commerce-message assistant"
                  key={message.id}
                >
                  <div className="commerce-assistant-head">
                    <KonturSymbol />
                    <strong>Контур</strong>
                    {message.response && (
                      <span>
                        {sourceLabels[message.response.answer_source]}
                      </span>
                    )}
                  </div>
                  <p className="commerce-answer">{message.text}</p>
                  {message.response && (
                    <>
                      <Evidence
                        response={message.response}
                        expanded={message.id === lastAssistantId}
                      />
                      <div className="commerce-products">
                        {message.response.products.map((product) => (
                          <ResponseProduct
                            key={product.id}
                            product={product}
                            warehouse={
                              warehouses.find(
                                (item) => item.id === product.warehouse_id,
                              )?.city || product.warehouse_id
                            }
                            busy={busy || !ready}
                            onDiscuss={() =>
                              void send(`Расскажи о товаре ${product.sku}`)
                            }
                            onPrepare={() => prepare(product)}
                          />
                        ))}
                      </div>
                    </>
                  )}
                </article>
              ),
            )}
          </div>
          {busy && (
            <div className="commerce-thinking" role="status">
              <LoaderCircle size={16} />
              <span>Проверяем данные и готовим ответ…</span>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
        <div className="commerce-composer-wrap">
          {messages.length > 0 && (
            <div className="commerce-quick-prompts">
              {prompts.map((prompt) => (
                <button
                  type="button"
                  key={prompt.message}
                  onClick={() => void send(prompt.message)}
                  disabled={busy || !ready}
                >
                  {prompt.title}
                  <ArrowUp size={11} />
                </button>
              ))}
            </div>
          )}
          {sendError && (
            <p className="commerce-send-error" role="alert">
              {sendError}
            </p>
          )}
          <form className="commerce-composer" onSubmit={submit}>
            <label className="sr-only" htmlFor="commerce-message">
              Сообщение ассистенту
            </label>
            <textarea
              ref={inputRef}
              id="commerce-message"
              rows={2}
              maxLength={4000}
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (
                  event.key === "Enter" &&
                  !event.shiftKey &&
                  !event.nativeEvent.isComposing
                ) {
                  event.preventDefault();
                  void send(input);
                }
              }}
              placeholder={
                ready
                  ? "Артикул, количество или вопрос по товару…"
                  : "Подключаем вашу сессию…"
              }
              disabled={!ready || busy}
            />
            <button
              type="submit"
              aria-label="Отправить сообщение"
              disabled={!ready || busy || !input.trim()}
            >
              {busy ? <LoaderCircle size={19} /> : <ArrowUp size={21} />}
            </button>
          </form>
          <div className="commerce-composer-note">
            <span>
              <ShieldCheck size={12} />
              Добавление — с вашего согласия
            </span>
            <span>Enter — отправить · Shift+Enter — новая строка</span>
          </div>
        </div>
      </section>

      <aside className="commerce-sidebar" aria-label="Предложение и корзина">
        <section
          className={`commerce-proposal ${pending ? "has-proposal" : ""}`}
        >
          <div className="commerce-panel-title">
            <div>
              <span className="commerce-eyebrow">Ваше решение</span>
              <h2>Состав комплекта</h2>
            </div>
            <Layers3 size={21} />
          </div>
          {pending && proposal ? (
            <>
              <p className="commerce-proposal-intro">
                Предложение готово. Проверьте, каким станет состав корзины.
              </p>
              <div className="commerce-proposal-place">
                <MapPin size={14} />
                {proposalWarehouse?.city ||
                  proposalWarehouse?.name ||
                  proposal.warehouse_id}
              </div>
              <div className="commerce-proposal-items">
                {proposal.items.map((item) => {
                  const product = latest?.products.find(
                    (product) => product.id === item.product_id,
                  );
                  const existing = cart?.items.find(
                    (product) => product.product_id === item.product_id,
                  );
                  const unit = product?.unit || existing?.unit || "";
                  return (
                    <div
                      className="commerce-proposal-item"
                      key={item.product_id}
                    >
                      <span className="commerce-product-sku">
                        {product?.sku ||
                          existing?.sku ||
                          `ID ${item.product_id}`}
                      </span>
                      <h3>
                        {product?.name ||
                          existing?.name ||
                          `Товар ${item.product_id}`}
                      </h3>
                      <div className="commerce-target-quantity">
                        <span>
                          {item.target_quantity === 0
                            ? "Удалить из корзины"
                            : "Итоговое количество"}
                        </span>
                        <strong>
                          {numbers.format(item.target_quantity)} {unit}
                        </strong>
                      </div>
                      <p className="commerce-current-quantity">
                        Сейчас в корзине:{" "}
                        {numbers.format(existing?.quantity ?? 0)} {unit}
                      </p>
                      {item.target_quantity > 0 && (
                        <div className="commerce-unit-price">
                          <span>Цена за единицу</span>
                          <span>{money(item.unit_price_kzt)}</span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
              <div className="commerce-proposal-total">
                <span>Корзина после изменения</span>
                <strong>{money(proposal.result_total_kzt)}</strong>
              </div>
              <p className="commerce-proposal-expiry">
                <Clock3 size={12} />
                До {timeLabel(proposal.expires_at)} · время Астаны
              </p>
              <button
                type="button"
                className="primary-button commerce-confirm-button"
                onClick={onConfirm}
                disabled={busy || !ready}
              >
                Проверить и подтвердить
                <ArrowRight size={16} />
              </button>
              <p className="commerce-no-mutation">
                <ShieldCheck size={13} />
                Предложение ещё не изменило корзину
              </p>
            </>
          ) : (
            <div className="commerce-proposal-empty">
              <span>
                <FileCheck2 size={32} />
              </span>
              <h3>
                {proposalExpired
                  ? "Предложение устарело"
                  : "Сначала уточним детали"}
              </h3>
              <p>
                {proposalExpired
                  ? "Отправьте запрос ещё раз, чтобы проверить цену и наличие."
                  : "Выберите товар в диалоге и укажите количество. Здесь появится конкретное предложение для вашего подтверждения."}
              </p>
              <div className="commerce-request-example">
                <MessageSquare size={15} />
                <span>
                  Напишите «Добавь 2 шт»
                  <br />и точный артикул товара
                </span>
              </div>
            </div>
          )}
        </section>
        <section className="commerce-cart-summary">
          <div className="commerce-cart-heading">
            <ShoppingBag size={18} />
            <h3>Ваша корзина</h3>
            <span>{cart?.items.length ?? "—"}</span>
          </div>
          <div className="commerce-cart-total">
            <span>Подтверждённый состав</span>
            <strong>{cart ? money(cart.total_kzt) : "Загружаем…"}</strong>
          </div>
          <button type="button" onClick={onOpenCart} disabled={!ready}>
            Открыть корзину
            <ArrowRight size={15} />
          </button>
        </section>
        <p className="commerce-scope">
          <ShieldCheck size={15} />
          <span>
            Корзина прототипа. Заказ и резервирование в ekt.kz не выполняются.
          </span>
        </p>
        <div className="commerce-sidebar-note">
          <Sparkles size={16} />
          <p>
            Если в данных есть противоречие, покажем основания и попросим
            уточнение.
          </p>
        </div>
      </aside>
    </div>
  );
}
