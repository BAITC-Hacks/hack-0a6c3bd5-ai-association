import { useEffect, useRef, useState } from "react";
import {
  ApiError,
  apiErrorMessage,
  confirmProposal,
  createSession,
  getCart,
  getWarehouses,
  sendChat,
  uploadDocument,
  proposeUpload,
  type Cart,
  type ChatResponse,
  type Warehouse,
  type ReviewedUploadLine,
} from "./api";

export interface ChatEntry {
  id: string;
  role: "user" | "assistant";
  text: string;
  response?: ChatResponse;
}

export interface DocumentLineDraft {
  line_id: string;
  query: string;
  quantity: string;
  unit: "" | "шт" | "м";
  included: boolean;
}

export interface ReviewedDocument {
  upload_id: string;
  fileName: string;
  warnings: string[];
  lines: DocumentLineDraft[];
}

type Operation =
  | { kind: "chat"; requestId: string; message: string; warehouseId: string }
  | { kind: "upload"; requestId: string; file: File; warehouseId: string }
  | {
      kind: "upload_proposal";
      requestId: string;
      uploadId: string;
      fileName: string;
      lines: ReviewedUploadLine[];
      warehouseId: string;
    }
  | {
      kind: "confirm";
      requestId: string;
      proposalId: string;
      warehouseId: string;
    };

const confirmationPhrases = new Set([
  "да добавь",
  "да добавляй",
  "подтверждаю добавление",
  "подтверждаю удаление",
  "да удали",
  "подтверждаю",
]);

export function useCommerce() {
  const [ready, setReady] = useState(false);
  const [booting, setBooting] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cart, setCart] = useState<Cart | null>(null);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [warehouseId, setWarehouse] = useState("");
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [latest, setLatest] = useState<ChatResponse | null>(null);
  const [document, setDocument] = useState<ReviewedDocument | null>(null);
  const [documentResultId, setDocumentResultId] = useState<string | null>(null);
  const mounted = useRef(false);
  const lock = useRef(false);
  const readyRef = useRef(false);
  const warehouseRef = useRef("");
  const warehouseListRef = useRef<Warehouse[]>([]);
  const latestRef = useRef<ChatResponse | null>(null);
  const documentRef = useRef<ReviewedDocument | null>(null);
  const pending = useRef<Operation | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const generation = useRef(0);

  function updateDocument(value: ReviewedDocument | null) {
    documentRef.current = value;
    setDocument(value);
  }

  function clearDocument() {
    updateDocument(null);
    setDocumentResultId(null);
  }

  function updateLatest(value: ChatResponse | null) {
    latestRef.current = value;
    setLatest(value);
  }

  function dropProposal() {
    if (latestRef.current)
      updateLatest({
        ...latestRef.current,
        proposal: null,
        confirmation_required: false,
      });
  }

  function applyCart(value: Cart) {
    setCart(value);
    const current = latestRef.current;
    if (!current) return;
    const stale =
      current.proposal?.status === "pending" &&
      current.proposal.cart_version !== value.version;
    updateLatest({
      ...current,
      cart: value,
      ...(stale ? { proposal: null, confirmation_required: false } : {}),
    });
  }

  function isActive(token: number) {
    return mounted.current && generation.current === token;
  }

  async function fail(caught: unknown, token: number, signal: AbortSignal) {
    if (!isActive(token) || signal.aborted) return;
    const message =
      apiErrorMessage(caught) +
      (caught instanceof ApiError && caught.status === 409
        ? pending.current?.kind === "upload" ||
          pending.current?.kind === "upload_proposal"
          ? " Вернитесь к спецификации и запустите проверку заново."
          : " Отправьте запрос в чат заново."
        : "");
    setError(message);
    if (caught instanceof ApiError && caught.status === 401) {
      readyRef.current = false;
      setReady(false);
      pending.current = null;
      dropProposal();
      clearDocument();
      return;
    }
    if (
      caught instanceof ApiError &&
      caught.status >= 400 &&
      caught.status < 500
    ) {
      pending.current = null;
      dropProposal();
      if (caught.status === 409) {
        try {
          const currentCart = await getCart(signal);
          if (isActive(token)) applyCart(currentCart);
        } catch (refreshError) {
          if (
            isActive(token) &&
            refreshError instanceof ApiError &&
            refreshError.status === 401
          ) {
            readyRef.current = false;
            setReady(false);
            clearDocument();
          }
          if (isActive(token) && !signal.aborted)
            setError(
              `${message} Не удалось обновить корзину; повторите проверку.`,
            );
        }
      }
    }
    // При неизвестном результате запроса сохраняем UUID и тело для явного повтора.
  }

  async function bootstrap() {
    if (lock.current || !mounted.current) return;
    lock.current = true;
    const token = ++generation.current;
    const controller = new AbortController();
    controllerRef.current = controller;
    readyRef.current = false;
    setReady(false);
    setBooting(true);
    setError(null);
    clearDocument();
    try {
      await createSession(controller.signal);
      const [currentCart, warehouseData] = await Promise.all([
        getCart(controller.signal),
        getWarehouses(controller.signal),
      ]);
      if (!isActive(token)) return;
      if (!warehouseData.items.length)
        throw new ApiError(
          "В каталоге нет доступных складов.",
          503,
          "WAREHOUSES_UNAVAILABLE",
        );
      const selected =
        currentCart.warehouse_id || warehouseData.default_warehouse_id;
      const id = warehouseData.items.some((item) => item.id === selected)
        ? selected
        : warehouseData.items[0].id;
      warehouseListRef.current = warehouseData.items;
      warehouseRef.current = id;
      setWarehouses(warehouseData.items);
      setWarehouse(id);
      setCart(currentCart);
      updateLatest(null);
      pending.current = null;
      readyRef.current = true;
      setReady(true);
    } catch (caught) {
      await fail(caught, token, controller.signal);
    } finally {
      if (isActive(token)) {
        lock.current = false;
        controllerRef.current = null;
        setBooting(false);
      }
    }
  }

  useEffect(() => {
    mounted.current = true;
    void bootstrap();
    return () => {
      mounted.current = false;
      generation.current += 1;
      controllerRef.current?.abort();
      controllerRef.current = null;
      lock.current = false;
    };
  }, []);

  async function execute(operation: Operation) {
    if (lock.current || !readyRef.current || !mounted.current) return;
    lock.current = true;
    const token = ++generation.current;
    const controller = new AbortController();
    controllerRef.current = controller;
    pending.current = operation;
    setBusy(true);
    setError(null);
    try {
      if (operation.kind === "upload") {
        const response = await uploadDocument(
          operation.file,
          operation.requestId,
          operation.warehouseId,
          controller.signal,
        );
        if (!isActive(token)) return;
        updateDocument({
          upload_id: response.upload_id,
          fileName: operation.file.name,
          warnings: response.warnings,
          lines: response.lines.map((line) => ({
            line_id: line.line_id,
            query: line.query,
            quantity: line.quantity === null ? "" : String(line.quantity),
            unit: line.unit ?? "",
            included: true,
          })),
        });
      } else if (
        operation.kind === "chat" ||
        operation.kind === "upload_proposal"
      ) {
        const response =
          operation.kind === "chat"
            ? await sendChat(
                {
                  message: operation.message,
                  request_id: operation.requestId,
                  warehouse_id: operation.warehouseId,
                },
                controller.signal,
              )
            : await proposeUpload(
                operation.uploadId,
                {
                  request_id: operation.requestId,
                  warehouse_id: operation.warehouseId,
                  lines: operation.lines,
                },
                controller.signal,
              );
        if (!isActive(token)) return;
        setCart(response.cart);
        updateLatest(response);
        if (operation.kind === "upload_proposal")
          setDocumentResultId(operation.requestId);
        const entry: ChatEntry = {
          id: `${operation.requestId}:assistant`,
          role: "assistant",
          text: response.message,
          response,
        };
        setMessages((previous) =>
          previous.some((message) => message.id === entry.id)
            ? previous
            : [...previous, entry],
        );
      } else {
        const response = await confirmProposal(
          operation.proposalId,
          operation.requestId,
          controller.signal,
        );
        if (!isActive(token)) return;
        setCart(response.cart);
        const current = latestRef.current;
        if (current?.proposal?.id === operation.proposalId)
          updateLatest({
            ...current,
            proposal: { ...current.proposal, status: "confirmed" },
            cart: response.cart,
            confirmation_required: false,
          });
        const entry: ChatEntry = {
          id: `${operation.requestId}:confirmed`,
          role: "assistant",
          text: "Состав корзины обновлён после вашего подтверждения. Товар не заказан и не зарезервирован.",
        };
        setMessages((previous) =>
          previous.some((message) => message.id === entry.id)
            ? previous
            : [...previous, entry],
        );
      }
      pending.current = null;
    } catch (caught) {
      await fail(caught, token, controller.signal);
    } finally {
      if (isActive(token)) {
        lock.current = false;
        controllerRef.current = null;
        setBusy(false);
      }
    }
  }

  async function send(message: string) {
    if (lock.current) return;
    if (!readyRef.current) {
      setError("Сессия ещё не готова. Повторите подключение.");
      return;
    }
    const text = message.trim();
    if (!text || text.length > 4000) {
      setError("Введите сообщение от 1 до 4000 символов.");
      return;
    }
    const phrase = text
      .toLocaleLowerCase("ru-RU")
      .replace(/[.,!?;:]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    const currentProposal = latestRef.current?.proposal;
    if (
      confirmationPhrases.has(phrase) &&
      (!currentProposal ||
        currentProposal.status !== "pending" ||
        currentProposal.warehouse_id !== warehouseRef.current)
    ) {
      setError(
        "Сначала получите и проверьте новое предложение. Предыдущий подбор нельзя подтвердить из другого контекста.",
      );
      return;
    }
    if (confirmationPhrases.has(phrase) && currentProposal) {
      const currentCart = latestRef.current?.cart;
      const deltas = currentProposal.items.map(
        (item) =>
          item.target_quantity -
          (currentCart?.items.find((row) => row.product_id === item.product_id)
            ?.quantity ?? 0),
      );
      const saysAdd = [
        "да добавь",
        "да добавляй",
        "подтверждаю добавление",
      ].includes(phrase);
      const saysRemove = ["да удали", "подтверждаю удаление"].includes(phrase);
      if (
        (saysAdd && deltas.some((delta) => delta < 0)) ||
        (saysRemove && deltas.some((delta) => delta > 0))
      ) {
        setError(
          "Подтверждение не соответствует изменению. Проверьте состав и используйте кнопку подтверждения.",
        );
        return;
      }
      // Подтверждаем показанный ID: другая вкладка могла создать новое предложение.
      await confirm();
      return;
    }
    const operation: Operation = {
      kind: "chat",
      requestId: crypto.randomUUID(),
      message: text,
      warehouseId: warehouseRef.current,
    };
    dropProposal();
    setDocumentResultId(null);
    pending.current = operation;
    setMessages((previous) => [
      ...previous,
      { id: `${operation.requestId}:user`, role: "user", text },
    ]);
    await execute(operation);
  }

  async function confirm() {
    if (lock.current) return;
    if (!readyRef.current) {
      setError("Подключитесь заново, затем запросите новое предложение.");
      return;
    }
    const proposal = latestRef.current?.proposal;
    if (
      !proposal ||
      proposal.status !== "pending" ||
      proposal.warehouse_id !== warehouseRef.current
    ) {
      setError(
        "Нет актуального предложения для подтверждения. Уточните запрос в чате.",
      );
      return;
    }
    const operation: Operation =
      pending.current?.kind === "confirm" &&
      pending.current.proposalId === proposal.id
        ? pending.current
        : {
            kind: "confirm",
            requestId: crypto.randomUUID(),
            proposalId: proposal.id,
            warehouseId: proposal.warehouse_id,
          };
    await execute(operation);
  }

  function setWarehouseId(id: string) {
    if (id === warehouseRef.current) return;
    if (lock.current) {
      setError("Дождитесь завершения текущего запроса, затем смените склад.");
      return;
    }
    if (!warehouseListRef.current.some((warehouse) => warehouse.id === id)) {
      setError("Выберите склад из списка.");
      return;
    }
    warehouseRef.current = id;
    setWarehouse(id);
    pending.current = null;
    dropProposal();
    setDocumentResultId(null);
    setError(null);
  }

  async function uploadFile(file: File) {
    if (lock.current) return;
    dropProposal();
    pending.current = null;
    clearDocument();
    setError(null);
    if (!readyRef.current) {
      setError("Сессия ещё не готова. Повторите подключение.");
      return;
    }
    if (!file.name.trim() || file.name.length > 255) {
      setError("Имя файла должно содержать от 1 до 255 символов.");
      return;
    }
    if (!/\.(xlsx|docx|pdf|jpe?g)$/i.test(file.name)) {
      setError("Выберите файл XLSX, DOCX, PDF, JPG или JPEG.");
      return;
    }
    if (file.size === 0 || file.size > 10 * 1024 * 1024) {
      setError("Файл должен быть непустым и не превышать 10 MiB.");
      return;
    }
    await execute({
      kind: "upload",
      requestId: crypto.randomUUID(),
      file,
      warehouseId: warehouseRef.current,
    });
  }

  function updateDocumentLine(
    id: string,
    patch: Partial<Omit<DocumentLineDraft, "line_id">>,
  ) {
    if (lock.current) return;
    const current = documentRef.current;
    if (!current || !current.lines.some((line) => line.line_id === id)) return;
    updateDocument({
      ...current,
      lines: current.lines.map((line) =>
        line.line_id === id
          ? { ...line, ...patch, line_id: line.line_id }
          : line,
      ),
    });
    dropProposal();
    pending.current = null;
    setDocumentResultId(null);
    setError(null);
  }

  function resetDocument() {
    if (lock.current) return;
    clearDocument();
    dropProposal();
    pending.current = null;
    setError(null);
  }

  async function proposeDocument() {
    if (lock.current) return;
    dropProposal();
    pending.current = null;
    setDocumentResultId(null);
    setError(null);
    if (!readyRef.current) {
      setError("Сессия ещё не готова. Повторите подключение.");
      return;
    }
    const current = documentRef.current;
    if (!current) {
      setError("Сначала загрузите документ и проверьте строки.");
      return;
    }
    const included = current.lines.filter((line) => line.included);
    if (included.length < 1 || included.length > 50) {
      setError("Оставьте в спецификации от 1 до 50 строк.");
      return;
    }
    const lines: ReviewedUploadLine[] = [];
    for (const line of included) {
      const query = line.query.trim();
      const quantity = Number(line.quantity.trim());
      if (!query || query.length > 2000) {
        setError(
          `Строка ${line.line_id}: укажите название или артикул длиной до 2000 символов.`,
        );
        return;
      }
      if (
        !/^\d+$/.test(line.quantity.trim()) ||
        !Number.isSafeInteger(quantity) ||
        quantity <= 0
      ) {
        setError(
          `Строка ${line.line_id}: укажите положительное целое количество.`,
        );
        return;
      }
      if (line.unit !== "шт" && line.unit !== "м") {
        setError(`Строка ${line.line_id}: выберите единицу «шт» или «м».`);
        return;
      }
      lines.push({ line_id: line.line_id, query, quantity, unit: line.unit });
    }
    const operation: Operation = {
      kind: "upload_proposal",
      requestId: crypto.randomUUID(),
      uploadId: current.upload_id,
      fileName: current.fileName,
      lines,
      warehouseId: warehouseRef.current,
    };
    pending.current = operation;
    setMessages((previous) => [
      ...previous,
      {
        id: `${operation.requestId}:user`,
        role: "user",
        text: `Проверить спецификацию «${current.fileName}» (${lines.length} строк)`,
      },
    ]);
    await execute(operation);
  }

  async function refresh() {
    if (lock.current) return;
    if (!readyRef.current) {
      await bootstrap();
      return;
    }
    lock.current = true;
    const token = ++generation.current;
    const controller = new AbortController();
    controllerRef.current = controller;
    setBusy(true);
    setError(null);
    try {
      const currentCart = await getCart(controller.signal);
      if (isActive(token)) applyCart(currentCart);
    } catch (caught) {
      await fail(caught, token, controller.signal);
    } finally {
      if (isActive(token)) {
        lock.current = false;
        controllerRef.current = null;
        setBusy(false);
      }
    }
  }

  async function retry() {
    if (lock.current) return;
    if (!readyRef.current) {
      await bootstrap();
      return;
    }
    if (pending.current) {
      await execute(pending.current);
      return;
    }
    await refresh();
  }

  return {
    ready,
    booting,
    busy,
    error,
    cart,
    warehouses,
    warehouseId,
    setWarehouseId,
    messages,
    latest,
    document,
    documentResultId,
    uploadFile,
    updateDocumentLine,
    proposeDocument,
    resetDocument,
    send,
    confirm,
    retry,
    retryLabel: !ready
      ? "Подключиться"
      : pending.current
        ? "Повторить"
        : "Обновить корзину",
    refresh,
    dismissError: () => setError(null),
  };
}

export default useCommerce;
