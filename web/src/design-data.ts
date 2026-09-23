// Только данные интерактивного дизайн-прототипа. Это не live-каталог ekt.kz.
export type Warehouse = "astana" | "almaty";
export type PreviewProduct = {
  id: string;
  name: string;
  subtitle: string;
  price: number;
  stocks: Record<Warehouse, number>;
  current: string;
  poles: string;
  voltage: string;
  conflict: boolean;
};

export const products: PreviewProduct[] = [
  {
    id: "200300285_",
    name: "DRX250 MT",
    subtitle: "Автоматический выключатель",
    price: 64920,
    stocks: { astana: 8, almaty: 5 },
    current: "160 / 250 А",
    poles: "3P",
    voltage: "400 В",
    conflict: true,
  },
  {
    id: "DEMO-160-3P",
    name: "КМ 160 / 3P",
    subtitle: "Аналог из учебного каталога",
    price: 61500,
    stocks: { astana: 16, almaty: 12 },
    current: "160 А",
    poles: "3P",
    voltage: "400 В",
    conflict: false,
  },
  {
    id: "DEMO-100-3P",
    name: "КМ 100 / 3P",
    subtitle: "Учебная позиция · другой номинал",
    price: 48700,
    stocks: { astana: 24, almaty: 18 },
    current: "100 А",
    poles: "3P",
    voltage: "400 В",
    conflict: false,
  },
];

export const warehouseNames: Record<Warehouse, string> = {
  astana: "Астана",
  almaty: "Алматы",
};
export const formatMoney = (value: number) =>
  `${new Intl.NumberFormat("ru-RU").format(value)} ₸`;
