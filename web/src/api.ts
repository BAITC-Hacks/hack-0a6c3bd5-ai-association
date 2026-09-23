export interface Warehouse {
  id: string;
  name: string;
  city: string;
}

export interface WarehousesResponse {
  items: Warehouse[];
  default_warehouse_id: string;
}

export interface ProductProperty {
  name: string;
  value: string;
  source_field: string;
}

export interface ProductDocument {
  title: string;
  url: string;
  kind: "certificate" | "datasheet";
}

export interface ProductSnapshot {
  source: "ekt_catalog" | "demo_fixture";
  captured_at: string;
  source_url: string | null;
}

export interface Product {
  id: number;
  sku: string;
  name: string;
  description: string;
  price_kzt: number | null;
  unit: "шт" | "м";
  min_order_quantity: number | null;
  warehouse_id: string;
  available_quantity: number | null;
  total_quantity: number | null;
  properties: ProductProperty[];
  image_url: string | null;
  documents: ProductDocument[];
  snapshot: ProductSnapshot;
}

export interface ProductListResponse {
  items: Product[];
  total: number;
  limit: number;
  offset: number;
  warehouse_id: string;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function getJson<T>(path: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    signal: AbortSignal.any([signal, AbortSignal.timeout(10000)]),
    credentials: "same-origin",
    headers: { Accept: "application/json" },
  });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    let message = "Не удалось получить данные. Попробуйте ещё раз.";
    if (payload && typeof payload === "object" && "error" in payload) {
      const error = payload.error;
      if (
        error &&
        typeof error === "object" &&
        "message" in error &&
        typeof error.message === "string"
      ) {
        message = error.message;
      }
    }
    throw new ApiError(message, response.status);
  }
  if (payload === null)
    throw new ApiError(
      "Сервис вернул неполные данные. Попробуйте ещё раз.",
      response.status,
    );
  return payload as T;
}

export function getWarehouses(
  signal: AbortSignal,
): Promise<WarehousesResponse> {
  return getJson("/api/warehouses", signal);
}

export function getProducts(
  options: {
    warehouseId: string;
    query: string;
    limit: number;
    offset: number;
  },
  signal: AbortSignal,
): Promise<ProductListResponse> {
  const parameters = new URLSearchParams({
    warehouse_id: options.warehouseId,
    q: options.query,
    limit: String(options.limit),
    offset: String(options.offset),
  });
  return getJson(`/api/products?${parameters}`, signal);
}

export function getProduct(
  id: number,
  warehouseId: string,
  signal: AbortSignal,
): Promise<Product> {
  const parameters = new URLSearchParams({ warehouse_id: warehouseId });
  return getJson(`/api/products/${id}?${parameters}`, signal);
}

export function apiErrorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "Нет связи с каталогом. Проверьте подключение и повторите попытку.";
}

export function localAssetUrl(value: string | null): string | null {
  if (!value?.startsWith("/assets/")) return null;
  try {
    const decoded = decodeURIComponent(value);
    if (
      decoded.includes("\\") ||
      decoded.split(/[/?#]/).some((part) => part === ".." || part === ".")
    )
      return null;
    const url = new URL(value, window.location.origin);
    return url.origin === window.location.origin &&
      url.pathname.startsWith("/assets/")
      ? value
      : null;
  } catch {
    return null;
  }
}
