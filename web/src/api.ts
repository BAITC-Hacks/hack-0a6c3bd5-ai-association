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
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(
    message: string,
    status: number,
    code = "HTTP_ERROR",
    details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function requestJson<T>(
  path: string,
  method: "GET" | "POST",
  signal?: AbortSignal,
  body?: unknown,
): Promise<T> {
  const timeout = AbortSignal.timeout(method === "POST" ? 40000 : 10000);
  const multipart = body instanceof FormData;
  let response: Response;
  try {
    response = await fetch(path, {
      signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
      credentials: "same-origin",
      method,
      headers: {
        Accept: "application/json",
        ...(method === "POST" && !multipart
          ? { "Content-Type": "application/json" }
          : {}),
      },
      ...(method === "POST"
        ? { body: multipart ? body : JSON.stringify(body) }
        : {}),
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError(
      timeout.aborted
        ? "Сервис не ответил вовремя. Повторите попытку."
        : "Нет связи с сервисом. Повторите попытку.",
      0,
      timeout.aborted ? "TIMEOUT" : "NETWORK_ERROR",
    );
  }
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    let message = "Не удалось получить данные. Попробуйте ещё раз.";
    let code = "HTTP_ERROR";
    let details: Record<string, unknown> = {};
    if (payload && typeof payload === "object" && "error" in payload) {
      const error = payload.error;
      if (
        error &&
        typeof error === "object" &&
        "message" in error &&
        typeof error.message === "string"
      ) {
        message = error.message;
        if ("code" in error && typeof error.code === "string")
          code = error.code;
        if (
          "details" in error &&
          error.details &&
          typeof error.details === "object" &&
          !Array.isArray(error.details)
        )
          details = error.details as Record<string, unknown>;
      }
    }
    throw new ApiError(message, response.status, code, details);
  }
  if (payload === null)
    throw new ApiError(
      "Сервис вернул неполные данные. Попробуйте ещё раз.",
      502,
      "INVALID_RESPONSE",
    );
  return payload as T;
}

function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  return requestJson(path, "GET", signal);
}

export function postJson<T>(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<T> {
  return requestJson(path, "POST", signal, body);
}

export interface CartItem {
  product_id: number;
  sku: string;
  name: string;
  unit: "шт" | "м";
  quantity: number;
  unit_price_kzt: number;
  line_total_kzt: number;
}

export interface Cart {
  id: string;
  version: number;
  warehouse_id: string | null;
  items: CartItem[];
  total_kzt: number;
  cart_url: "/cart";
  scope: "local_demo";
}

export interface Check {
  product_id: number;
  field: string;
  expected: string | null;
  actual: string | null;
  status: "match" | "conflict" | "unknown";
  sources: { field: string; value: string }[];
}

export interface Proposal {
  id: string;
  status: "pending" | "confirmed" | "expired" | "superseded";
  warehouse_id: string;
  cart_version: number;
  items: {
    product_id: number;
    target_quantity: number;
    unit_price_kzt: number;
  }[];
  result_total_kzt: number;
  expires_at: string;
}

export interface ChatResponse {
  message: string;
  products: Product[];
  checks: Check[];
  proposal: Proposal | null;
  cart: Cart;
  answer_source: "fixture" | "rules" | "openai";
  confirmation_required: boolean;
}

export interface ConfirmResponse {
  proposal_id: string;
  status: "confirmed";
  cart: Cart;
}

export interface ExtractedUploadLine {
  line_id: string;
  query: string;
  quantity: number | null;
  unit: "шт" | "м" | null;
}

export interface UploadResponse {
  upload_id: string;
  warnings: string[];
  lines: ExtractedUploadLine[];
}

export interface ReviewedUploadLine {
  line_id: string;
  query: string;
  quantity: number;
  unit: "шт" | "м";
}

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

const string = (value: unknown) => typeof value === "string";
const integer = (value: unknown, minimum = 0) =>
  typeof value === "number" && Number.isSafeInteger(value) && value >= minimum;
const nullableInteger = (value: unknown, minimum = 0) =>
  value === null || integer(value, minimum);
const strings = (value: Record<string, unknown>, fields: string[]) =>
  fields.every((field) => string(value[field]));
const array = (value: unknown, valid: (item: unknown) => boolean) =>
  Array.isArray(value) && value.every(valid);
const unit = (value: unknown) => value === "шт" || value === "м";
const date = (value: unknown) =>
  typeof value === "string" && Number.isFinite(Date.parse(value));

function validCart(value: unknown): boolean {
  return (
    record(value) &&
    string(value.id) &&
    integer(value.version) &&
    (value.warehouse_id === null || string(value.warehouse_id)) &&
    integer(value.total_kzt) &&
    value.cart_url === "/cart" &&
    value.scope === "local_demo" &&
    array(
      value.items,
      (item) =>
        record(item) &&
        integer(item.product_id, 1) &&
        strings(item, ["sku", "name"]) &&
        unit(item.unit) &&
        integer(item.quantity, 1) &&
        integer(item.unit_price_kzt) &&
        integer(item.line_total_kzt),
    )
  );
}

function validProduct(value: unknown): boolean {
  if (
    !record(value) ||
    !integer(value.id, 1) ||
    !strings(value, ["sku", "name", "description", "warehouse_id"]) ||
    !unit(value.unit) ||
    !nullableInteger(value.price_kzt) ||
    !nullableInteger(value.min_order_quantity, 1) ||
    !nullableInteger(value.available_quantity) ||
    !nullableInteger(value.total_quantity) ||
    !(value.image_url === null || string(value.image_url))
  )
    return false;
  return (
    array(
      value.properties,
      (item) =>
        record(item) && strings(item, ["name", "value", "source_field"]),
    ) &&
    array(
      value.documents,
      (item) =>
        record(item) &&
        strings(item, ["title", "url"]) &&
        (item.kind === "certificate" || item.kind === "datasheet"),
    ) &&
    record(value.snapshot) &&
    (value.snapshot.source === "ekt_catalog" ||
      value.snapshot.source === "demo_fixture") &&
    date(value.snapshot.captured_at) &&
    (value.snapshot.source_url === null || string(value.snapshot.source_url))
  );
}

function validProposal(value: unknown): boolean {
  return (
    record(value) &&
    strings(value, ["id", "warehouse_id", "status"]) &&
    ["pending", "confirmed", "expired", "superseded"].includes(
      String(value.status),
    ) &&
    integer(value.cart_version) &&
    integer(value.result_total_kzt) &&
    date(value.expires_at) &&
    array(
      value.items,
      (item) =>
        record(item) &&
        integer(item.product_id, 1) &&
        integer(item.target_quantity) &&
        integer(item.unit_price_kzt),
    )
  );
}

function validChat(value: unknown): boolean {
  return (
    record(value) &&
    strings(value, ["message", "answer_source"]) &&
    typeof value.confirmation_required === "boolean" &&
    ["fixture", "rules", "openai"].includes(String(value.answer_source)) &&
    validCart(value.cart) &&
    (value.proposal === null || validProposal(value.proposal)) &&
    array(value.products, validProduct) &&
    array(
      value.checks,
      (check) =>
        record(check) &&
        integer(check.product_id, 1) &&
        strings(check, ["field", "status"]) &&
        (check.expected === null || string(check.expected)) &&
        (check.actual === null || string(check.actual)) &&
        ["match", "conflict", "unknown"].includes(String(check.status)) &&
        array(
          check.sources,
          (source) => record(source) && strings(source, ["field", "value"]),
        ),
    )
  );
}

function validUpload(value: unknown): boolean {
  if (
    !record(value) ||
    typeof value.upload_id !== "string" ||
    !value.upload_id.trim() ||
    !array(value.warnings, string) ||
    !Array.isArray(value.lines) ||
    value.lines.length < 1 ||
    value.lines.length > 50
  )
    return false;
  const ids = new Set<string>();
  return value.lines.every((line: unknown) => {
    if (
      !record(line) ||
      typeof line.line_id !== "string" ||
      !line.line_id.trim() ||
      line.line_id.length > 64 ||
      ids.has(line.line_id) ||
      typeof line.query !== "string" ||
      !line.query.trim() ||
      line.query.length > 2000 ||
      !nullableInteger(line.quantity, 1) ||
      !(line.unit === null || unit(line.unit))
    )
      return false;
    ids.add(line.line_id);
    return true;
  });
}

function checked<T>(value: unknown, valid: (input: unknown) => boolean): T {
  if (!valid(value))
    throw new ApiError(
      "Сервис вернул неполный или неверный ответ. Повторите проверку; предыдущее действие не будет выполнено дважды.",
      502,
      "INVALID_RESPONSE",
    );
  return value as T;
}

export async function createSession(
  signal?: AbortSignal,
): Promise<{ ready: boolean }> {
  return checked(
    await postJson("/api/session", {}, signal),
    (value) => record(value) && value.ready === true,
  );
}

export async function getCart(signal?: AbortSignal): Promise<Cart> {
  return checked(await getJson("/api/cart", signal), validCart);
}

export async function sendChat(
  body: { message: string; request_id: string; warehouse_id: string },
  signal?: AbortSignal,
): Promise<ChatResponse> {
  return checked(await postJson("/api/chat", body, signal), validChat);
}

export async function uploadDocument(
  file: File,
  requestId: string,
  warehouseId: string,
  signal?: AbortSignal,
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file, file.name);
  form.append("request_id", requestId);
  form.append("warehouse_id", warehouseId);
  return checked(
    await requestJson("/api/uploads", "POST", signal, form),
    validUpload,
  );
}

export async function proposeUpload(
  uploadId: string,
  body: {
    request_id: string;
    warehouse_id: string;
    lines: ReviewedUploadLine[];
  },
  signal?: AbortSignal,
): Promise<ChatResponse> {
  return checked(
    await postJson(
      `/api/uploads/${encodeURIComponent(uploadId)}/proposal`,
      body,
      signal,
    ),
    validChat,
  );
}

export async function confirmProposal(
  proposalId: string,
  requestId: string,
  signal?: AbortSignal,
): Promise<ConfirmResponse> {
  return checked(
    await postJson(
      `/api/proposals/${encodeURIComponent(proposalId)}/confirm`,
      { request_id: requestId },
      signal,
    ),
    (value) =>
      record(value) &&
      value.proposal_id === proposalId &&
      value.status === "confirmed" &&
      validCart(value.cart),
  );
}

export async function getWarehouses(
  signal: AbortSignal,
): Promise<WarehousesResponse> {
  return checked(
    await getJson("/api/warehouses", signal),
    (value) =>
      record(value) &&
      string(value.default_warehouse_id) &&
      array(
        value.items,
        (item) => record(item) && strings(item, ["id", "name", "city"]),
      ),
  );
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
