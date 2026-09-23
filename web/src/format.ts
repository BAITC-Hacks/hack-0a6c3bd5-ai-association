// Общее форматирование: деньги, даты и подписи полей проверки.
// Значения приходят с сервера; здесь только представление.
export const numbers = new Intl.NumberFormat("ru-RU");

const dateTime = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Asia/Almaty",
});

export const money = (value: number | null) =>
  value === null ? "Цена не указана" : `${numbers.format(value)} ₸`;

export const timeLabel = (value: string) =>
  Number.isNaN(Date.parse(value))
    ? "Время не указано"
    : dateTime.format(new Date(value));

export const fieldNames: Record<string, string> = {
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

export const fieldLabel = (field: string) => fieldNames[field] || field;

// Русское склонение: 1 позиция, 2 позиции, 5 позиций.
export const plural = (count: number, one: string, few: string, many: string) => {
  const mod100 = Math.abs(count) % 100;
  const mod10 = mod100 % 10;
  if (mod100 >= 11 && mod100 <= 14) return many;
  if (mod10 === 1) return one;
  if (mod10 >= 2 && mod10 <= 4) return few;
  return many;
};
