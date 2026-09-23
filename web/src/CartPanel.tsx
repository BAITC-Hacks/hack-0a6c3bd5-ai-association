import { useState } from "react";
import {
  ArrowRight,
  LoaderCircle,
  Package,
  RefreshCw,
  ShieldCheck,
  ShoppingBag,
  Trash2,
} from "lucide-react";
import type { Cart, CartItem } from "./api";
const money = (value: number) =>
  `${new Intl.NumberFormat("ru-RU").format(value)} ₸`;
interface Props {
  cart: Cart | null;
  ready: boolean;
  busy: boolean;
  warehouseName: string;
  onSend: (message: string) => Promise<void>;
  onBrowse: () => void;
  onRefresh: () => Promise<void>;
}
function CartRow({
  item,
  disabled,
  send,
}: {
  item: CartItem;
  disabled: boolean;
  send: Props["onSend"];
}) {
  const [value, setValue] = useState(String(item.quantity));
  const quantity = Number(value);
  const valid =
    value.trim() !== "" && Number.isSafeInteger(quantity) && quantity >= 0;
  return (
    <article className="server-cart-row">
      <div className="server-cart-product">
        <span className="server-cart-icon">
          <Package size={24} />
        </span>
        <div>
          <span className="product-sku">АРТ. {item.sku}</span>
          <h3>{item.name}</h3>
          <p>
            {money(item.unit_price_kzt)} / {item.unit} · Подтверждено{" "}
            {item.quantity} {item.unit}
          </p>
        </div>
      </div>
      <strong className="server-cart-line-total">
        {money(item.line_total_kzt)}
      </strong>
      <form
        className="server-cart-edit"
        onSubmit={(event) => {
          event.preventDefault();
          if (!valid || disabled) return;
          void send(
            quantity === 0
              ? `Удали ${item.sku}`
              : `Установи ${quantity} ${item.unit} ${item.sku}`,
          );
        }}
      >
        <label>
          Новое количество
          <input
            type="number"
            min="0"
            step="1"
            value={value}
            onChange={(event) => setValue(event.target.value)}
            aria-label={`Количество ${item.sku}`}
            disabled={disabled}
          />
        </label>
        <button
          className="secondary-button"
          disabled={disabled || !valid || quantity === item.quantity}
        >
          Предложить изменение
          <ArrowRight size={14} />
        </button>
        <button
          type="button"
          className="cart-remove"
          aria-label={`Удалить ${item.sku}`}
          disabled={disabled}
          onClick={() => void send(`Удали ${item.sku}`)}
        >
          <Trash2 size={17} />
          Удалить
        </button>
      </form>
    </article>
  );
}
export default function CartPanel({
  cart,
  ready,
  busy,
  warehouseName,
  onSend,
  onBrowse,
  onRefresh,
}: Props) {
  if (!cart)
    return (
      <section className="empty-state">
        <ShoppingBag size={36} />
        <h2>{ready ? "Получаем корзину" : "Корзина вашей сессии"}</h2>
        <p>Для просмотра нужно соединение с локальным сервером.</p>
        {busy && <LoaderCircle size={20} />}
        <button
          className="secondary-button"
          disabled={busy}
          onClick={() => void onRefresh()}
        >
          <RefreshCw size={16} />
          Обновить
        </button>
      </section>
    );
  return (
    <section className="server-cart" aria-label="Корзина текущей сессии">
      <div className="server-cart-heading">
        <div>
          <span className="eyebrow">ПОДТВЕРЖДЕНО ВАМИ</span>
          <h2>
            {cart.items.length
              ? `${cart.items.length} позиций в комплекте`
              : "Корзина пока пуста"}
          </h2>
          <p>
            {cart.items.length
              ? `Склад: ${warehouseName}. Состав хранится на сервере.`
              : "Товары появятся здесь после вашего подтверждения."}
          </p>
        </div>
        <button
          className="secondary-button"
          disabled={!ready || busy}
          onClick={() => void onRefresh()}
        >
          <RefreshCw size={16} />
          Обновить
        </button>
      </div>
      {cart.items.length ? (
        <>
          <div>
            {cart.items.map((item) => (
              <CartRow
                key={`${item.product_id}-${cart.version}`}
                item={item}
                disabled={!ready || busy}
                send={onSend}
              />
            ))}
          </div>
          <div className="server-cart-summary">
            <p>
              <ShieldCheck size={18} />
              Изменение количества и удаление сначала создают предложение. До
              подтверждения состав сохранится.
            </p>
            <div>
              <span>Итого</span>
              <strong>{money(cart.total_kzt)}</strong>
            </div>
          </div>
          <button
            className="cart-remove"
            disabled={!ready || busy}
            onClick={() => void onSend("Очисти корзину")}
          >
            <Trash2 size={16} />
            Предложить очистку корзины
          </button>
        </>
      ) : (
        <div className="server-cart-empty">
          <ShoppingBag size={44} />
          <h3>Каждая позиция — с вашего согласия</h3>
          <p>Найдите товар в каталоге или задайте вопрос консультанту.</p>
          <button className="primary-button" onClick={onBrowse}>
            Открыть каталог
            <ArrowRight size={16} />
          </button>
        </div>
      )}
      <p className="server-cart-disclaimer">
        Корзина прототипа: заказ, оплата и резервирование в ekt.kz не
        выполняются. Данные относятся к снимку каталога.
      </p>
    </section>
  );
}
