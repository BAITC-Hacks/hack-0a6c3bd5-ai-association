import { useEffect, useState } from "react";
import NumberFlow from "@number-flow/react";
import { Clock3, ShieldCheck } from "lucide-react";
import type { Cart, ChatResponse, Proposal, Warehouse } from "./api";
import { money, numbers, timeLabel } from "./format";

// Единая проверка «предложение можно подтвердить»: статус, склад, срок.
// Все места интерфейса опираются на неё, чтобы CTA не разошлись между экранами.
export function usePendingProposal(
  latest: ChatResponse | null,
  warehouseId: string,
) {
  const proposal = latest?.proposal ?? null;
  const [now, setNow] = useState(() => Date.now());
  const live = proposal?.status === "pending";
  useEffect(() => {
    if (!live) return;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [live, proposal?.id]);
  const expired = proposal ? Date.parse(proposal.expires_at) <= now : false;
  const pending = Boolean(
    proposal &&
      proposal.status === "pending" &&
      latest?.confirmation_required &&
      proposal.warehouse_id === warehouseId &&
      !expired,
  );
  return { proposal, pending, expired, now };
}

export function isRemoval(proposal: Proposal, cart: Cart | null) {
  return proposal.items.some(
    (item) =>
      item.target_quantity <
      (cart?.items.find((row) => row.product_id === item.product_id)
        ?.quantity ?? 0),
  );
}

// Состав предложения: итоговые количества строк и итог всей корзины с сервера.
export function ProposalComposition({
  proposal,
  latest,
  cart,
  warehouses,
}: {
  proposal: Proposal;
  latest: ChatResponse | null;
  cart: Cart | null;
  warehouses: Warehouse[];
}) {
  const place = warehouses.find((item) => item.id === proposal.warehouse_id);
  return (
    <div className="decision-body">
      <div className="decision-place">
        <span className="tag-mono">Склад</span>
        {place?.city || place?.name || proposal.warehouse_id}
      </div>
      <div className="decision-items">
        {proposal.items.map((item) => {
          const product = latest?.products.find(
            (value) => value.id === item.product_id,
          );
          const existing = cart?.items.find(
            (value) => value.product_id === item.product_id,
          );
          const unit = product?.unit || existing?.unit || "";
          const current = existing?.quantity ?? 0;
          const removal = item.target_quantity === 0;
          return (
            <article className="decision-item" key={item.product_id}>
              <span className="tag-mono">
                {product?.sku || existing?.sku || `ID ${item.product_id}`}
              </span>
              <h4>
                {product?.name ||
                  existing?.name ||
                  `Товар ${item.product_id}`}
              </h4>
              <div className="decision-quantity">
                <span>{removal ? "Удалить из корзины" : "Итог по позиции"}</span>
                <strong>
                  {removal ? "0" : numbers.format(item.target_quantity)} {unit}
                </strong>
              </div>
              <p className="decision-current">
                Сейчас в корзине: {numbers.format(current)} {unit}
                {!removal && (
                  <>
                    {" · "}
                    {money(item.unit_price_kzt)} / {unit || "ед."}
                  </>
                )}
              </p>
            </article>
          );
        })}
      </div>
      <div className="decision-total">
        <span>Корзина станет</span>
        <strong>
          <NumberFlow
            value={proposal.result_total_kzt}
            locales="ru-RU"
            format={{ maximumFractionDigits: 0 }}
            aria-label={money(proposal.result_total_kzt)}
          />
          <i>₸</i>
        </strong>
      </div>
      <p className="decision-expiry">
        <Clock3 size={13} />
        Проверено до {timeLabel(proposal.expires_at)} · время Астаны
      </p>
      <p className="decision-untouched">
        <ShieldCheck size={13} />
        Это предложение. Корзина ещё не изменилась.
      </p>
    </div>
  );
}
