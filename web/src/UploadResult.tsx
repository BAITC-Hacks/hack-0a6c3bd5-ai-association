import { motion, useReducedMotion } from "motion/react";
import {
  ArrowRight,
  Check,
  MessageSquare,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import type { Cart, ChatResponse, Warehouse } from "./api";
import { fieldLabel, money } from "./format";
import {
  ProposalComposition,
  isRemoval,
  usePendingProposal,
} from "./proposal";

interface Props {
  latest: ChatResponse;
  cart: Cart | null;
  warehouses: Warehouse[];
  warehouseId: string;
  busy: boolean;
  ready: boolean;
  onConfirm: () => void;
  onOpenChat: () => void;
  onOpenCart: () => void;
}

// Результат сопоставления показывается рядом со строками спецификации:
// исправлять строки можно здесь же, без перехода в чат и обратно.
export default function UploadResult({
  latest,
  cart,
  warehouses,
  warehouseId,
  busy,
  ready,
  onConfirm,
  onOpenChat,
  onOpenCart,
}: Props) {
  const reduced = useReducedMotion();
  const { proposal, pending, expired } = usePendingProposal(
    latest,
    warehouseId,
  );
  const conflicts = latest.checks.filter(
    (check) => check.status === "conflict",
  );
  const removal = proposal ? isRemoval(proposal, cart) : false;
  const state = pending ? "ready" : conflicts.length ? "conflict" : "info";

  if (proposal?.status === "confirmed") return (
    <section className="upload-result state-ready" aria-label="Результат проверки по каталогу">
      <header className="upload-result-head"><span className="step-badge">Готово</span><span className="verdict verdict-ready"><Check size={14} />Корзина обновлена</span></header>
      <p className="upload-result-message" role="status">Предложение подтверждено.{cart ? ` Итог корзины: ${money(cart.total_kzt)}.` : ""}</p>
      <button type="button" className="primary-button upload-result-confirm" onClick={onOpenCart}>Открыть корзину<ArrowRight size={16} /></button>
    </section>
  );

  return (
    <motion.section
      className={`upload-result state-${state}`}
      aria-label="Результат проверки по каталогу"
      initial={reduced ? false : { opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: [0.22, 0.68, 0, 1] }}
    >
      <header className="upload-result-head">
        <span className="step-badge">Шаг 3</span>
        <span className={`verdict verdict-${state}`}>
          {state === "ready" ? (
            <>
              <Check size={14} />
              Проверено — можно подтвердить
            </>
          ) : state === "conflict" ? (
            <>
              <TriangleAlert size={14} />
              Нужно уточнение — предложения нет
            </>
          ) : (
            <>
              <ShieldCheck size={14} />
              Ответ по каталогу
            </>
          )}
        </span>
      </header>
      <p className="upload-result-message">{latest.message}</p>

      {conflicts.length > 0 && (
        <div className="upload-result-conflicts" role="status">
          <h3>
            <TriangleAlert size={15} />
            Расхождения в данных каталога
          </h3>
          <ul>
            {conflicts.map((check, index) => {
              const product = latest.products.find(
                (item) => item.id === check.product_id,
              );
              return (
                <li key={`${check.product_id}-${check.field}-${index}`}>
                  <span className="tag-mono">
                    {product?.sku || `ID ${check.product_id}`}
                  </span>
                  <strong>{fieldLabel(check.field)}</strong>
                  <span className="conflict-values">
                    в запросе {check.expected ?? "не задано"} · в источнике{" "}
                    {check.actual ?? "нет данных"}
                  </span>
                </li>
              );
            })}
          </ul>
          <p>
            Пока расхождение не снято, предложение по всему списку не
            создаётся. Исправьте или исключите строку ниже и запустите проверку
            снова.
          </p>
        </div>
      )}

      {pending && proposal ? (
        <>
          <ProposalComposition
            proposal={proposal}
            latest={latest}
            cart={cart}
            warehouses={warehouses}
          />
          <button
            type="button"
            className="primary-button upload-result-confirm"
            disabled={busy || !ready}
            onClick={onConfirm}
          >
            {removal ? "Проверить и подтвердить изменение" : "Проверить и подтвердить"}
            <ArrowRight size={16} />
          </button>
        </>
      ) : (
        <p className="upload-result-next">
          {expired
            ? "Срок предложения истёк. Запустите проверку по каталогу заново."
            : "Корзина не изменилась. Поправьте строки ниже и повторите проверку."}
        </p>
      )}

      <button type="button" className="quiet-link" onClick={onOpenChat}>
        <MessageSquare size={15} />
        Открыть подробный ответ и паспорт проверок
        <ArrowRight size={14} />
      </button>
    </motion.section>
  );
}
