import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import NumberFlow from "@number-flow/react";
import { ArrowRight, Check } from "lucide-react";
import clsx from "clsx";
import { money } from "./format";
import type { Proposal } from "./api";

export function useCompactScreen() {
  const [compact, setCompact] = useState(
    () =>
      typeof window !== "undefined" &&
      window.matchMedia("(max-width: 820px)").matches,
  );
  useEffect(() => {
    const query = window.matchMedia("(max-width: 820px)");
    const update = () => setCompact(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return compact;
}

const steps = [
  { title: "Запрос или файл", hint: "Опишите или загрузите" },
  { title: "Проверка", hint: "Данные каталога и склад" },
  { title: "Подтверждение", hint: "Решение за вами" },
];

// Один указатель пути на всех рабочих экранах: где пользователь сейчас.
export function StepRail({ current }: { current: 1 | 2 | 3 }) {
  return (
    <ol className="step-rail" aria-label="Путь закупки">
      {steps.map((step, index) => {
        const number = index + 1;
        const done = number < current;
        return (
          <li
            key={step.title}
            className={clsx(done && "done", number === current && "active")}
            aria-current={number === current ? "step" : undefined}
          >
            <b>{done ? <Check size={13} /> : number}</b>
            <span>
              {step.title}
              <small>{step.hint}</small>
            </span>
          </li>
        );
      })}
    </ol>
  );
}

// На узком экране главное действие не должно уезжать под ленту ответа.
export function DecisionBar({
  proposal,
  removal,
  busy,
  onConfirm,
  onDismiss,
}: {
  proposal: Proposal;
  removal: boolean;
  busy: boolean;
  onConfirm: () => void;
  onDismiss: () => void;
}) {
  const reduced = useReducedMotion();
  return (
    <AnimatePresence>
      <motion.div
        className="decision-bar"
        role="region"
        aria-label="Предложение ожидает вашего решения"
        initial={reduced ? false : { opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        exit={reduced ? undefined : { opacity: 0, y: 16 }}
        transition={{ duration: 0.24, ease: [0.22, 0.68, 0, 1] }}
      >
        <div className="decision-bar-text">
          <span>Предложение · ещё не в корзине</span>
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
        <button
          type="button"
          className="decision-bar-later"
          onClick={onDismiss}
        >
          Позже
        </button>
        <button
          type="button"
          className="primary-button"
          disabled={busy}
          onClick={onConfirm}
        >
          {removal ? "Проверить изменение" : "Проверить и подтвердить"}
          <ArrowRight size={16} />
        </button>
      </motion.div>
    </AnimatePresence>
  );
}
