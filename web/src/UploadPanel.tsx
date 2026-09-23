import { useEffect, useRef, useState, type DragEvent } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  FileCheck2,
  FileSpreadsheet,
  FileText,
  Image,
  ListChecks,
  LoaderCircle,
  MapPin,
  MessageSquare,
  ShieldCheck,
  TriangleAlert,
  UploadCloud,
  X,
} from "lucide-react";
import type { Cart, ChatResponse, Warehouse } from "./api";
import UploadResult from "./UploadResult";
import type { DocumentLineDraft, ReviewedDocument } from "./useCommerce";

interface UploadPanelProps {
  document: ReviewedDocument | null;
  result: ChatResponse | null;
  cart: Cart | null;
  warehouses: Warehouse[];
  warehouseId: string;
  ready: boolean;
  busy: boolean;
  warehouseName: string;
  onConfirm: () => void;
  onUpload: (file: File) => Promise<void>;
  onChangeLine: (
    id: string,
    patch: Partial<Omit<DocumentLineDraft, "line_id">>,
  ) => void;
  onPropose: () => Promise<void>;
  onReset: () => void;
  onOpenChat: () => void;
  onOpenCart: () => void;
}

const maxFileSize = 10 * 1024 * 1024;
const acceptedFiles =
  ".xlsx,.docx,.pdf,.jpg,.jpeg,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/pdf,image/jpeg";
const examples = [
  { extension: "xlsx", label: "Таблица Excel", Icon: FileSpreadsheet },
  { extension: "docx", label: "Документ Word", Icon: FileText },
  { extension: "pdf", label: "Текстовый PDF", Icon: FileText },
  { extension: "jpg", label: "Фото JPEG", Icon: Image },
];

function validateLine(line: DocumentLineDraft) {
  const quantity = Number(line.quantity);
  return {
    query: !line.query.trim()
      ? "Укажите товар или артикул."
      : line.query.trim().length > 2000
        ? "Не больше 2000 символов."
        : "",
    quantity:
      !/^\d+$/.test(line.quantity.trim()) ||
      !Number.isSafeInteger(quantity) ||
      quantity < 1
        ? "Нужно целое количество от 1."
        : "",
    unit: line.unit !== "шт" && line.unit !== "м" ? "Выберите единицу." : "",
  };
}

export default function UploadPanel({
  document,
  result,
  cart,
  warehouses,
  warehouseId,
  ready,
  busy,
  warehouseName,
  onConfirm,
  onUpload,
  onChangeLine,
  onPropose,
  onReset,
  onOpenChat,
  onOpenCart,
}: UploadPanelProps) {
  const fileInput = useRef<HTMLInputElement>(null);
  const resultRef = useRef<HTMLDivElement>(null);
  const dragDepth = useRef(0);
  const [dragging, setDragging] = useState(false);
  const [localError, setLocalError] = useState("");
  const [activity, setActivity] = useState<"upload" | "propose" | null>(null);
  const [fileName, setFileName] = useState("");
  const disabled = busy || !ready || activity !== null;
  const selectedLines = document?.lines.filter((line) => line.included) ?? [];
  const invalidCount = selectedLines.filter((line) =>
    Object.values(validateLine(line)).some(Boolean),
  ).length;
  const tooManyLines = (document?.lines.length ?? 0) > 50;
  useEffect(() => {
    if (!result) return;
    resultRef.current?.scrollIntoView({
      block: "start",
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
    });
  }, [result]);
  const valid = Boolean(
    document && selectedLines.length > 0 && invalidCount === 0 && !tooManyLines,
  );

  async function uploadFiles(files: FileList | File[]) {
    if (disabled || files.length === 0) return;
    setLocalError("");
    onReset();
    if (files.length !== 1) {
      setLocalError(
        "Выберите один файл. Несколько документов нужно загружать по отдельности.",
      );
      return;
    }
    const file = files[0];
    if (!/\.(xlsx|docx|pdf|jpe?g)$/i.test(file.name)) {
      setLocalError(
        "Поддерживаются XLSX, DOCX, текстовый PDF и JPEG. Выберите файл одного из этих форматов.",
      );
      return;
    }
    if (file.size === 0) {
      setLocalError("Файл пустой. Выберите документ с перечнем товаров.");
      return;
    }
    if (file.size > maxFileSize) {
      setLocalError(
        "Файл больше 10 МБ. Сохраните короткую спецификацию отдельным документом.",
      );
      return;
    }
    setFileName(file.name);
    setActivity("upload");
    try {
      await onUpload(file);
    } catch (error) {
      setLocalError(
        error instanceof Error
          ? error.message
          : "Не удалось прочитать файл. Попробуйте ещё раз.",
      );
    } finally {
      setActivity(null);
    }
  }

  function drop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    dragDepth.current = 0;
    setDragging(false);
    if (!disabled) void uploadFiles(event.dataTransfer.files);
  }

  async function propose() {
    if (!valid || disabled) return;
    setLocalError("");
    setActivity("propose");
    try {
      await onPropose();
    } catch (error) {
      setLocalError(
        error instanceof Error
          ? error.message
          : "Не удалось проверить строки. Повторите попытку.",
      );
    } finally {
      setActivity(null);
    }
  }

  function reset() {
    if (disabled) return;
    setLocalError("");
    setFileName("");
    setDragging(false);
    onReset();
  }

  return (
    <section
      className="upload-panel"
      aria-label="Загрузка и проверка спецификации"
      aria-busy={busy || activity !== null}
    >
      {localError && (
        <div className="upload-local-error" role="alert">
          <TriangleAlert size={18} />
          <p>{localError}</p>
          <button
            type="button"
            aria-label="Закрыть сообщение загрузки"
            onClick={() => setLocalError("")}
          >
            <X size={16} />
          </button>
        </div>
      )}
      {(busy || activity !== null) && (
        <div className="upload-busy" role="status">
          <LoaderCircle size={17} />
          <span>
            {activity === "upload"
              ? `Читаем файл ${fileName}…`
              : activity === "propose"
                ? "Сопоставляем проверенные строки с каталогом…"
                : "Завершаем текущую операцию…"}
          </span>
        </div>
      )}

      {!document ? (
        <div className="upload-start-layout">
          <div className="upload-start-main">
            <div
              className={`upload-dropzone ${dragging ? "dragging" : ""} ${disabled ? "disabled" : ""}`}
              onDragEnter={(event) => {
                event.preventDefault();
                if (disabled) return;
                dragDepth.current += 1;
                setDragging(true);
              }}
              onDragOver={(event) => {
                event.preventDefault();
                event.dataTransfer.dropEffect = disabled ? "none" : "copy";
              }}
              onDragLeave={(event) => {
                event.preventDefault();
                dragDepth.current = Math.max(0, dragDepth.current - 1);
                if (!dragDepth.current) setDragging(false);
              }}
              onDrop={drop}
            >
              <div className="upload-sheet-symbol" aria-hidden="true">
                <span>
                  <FileText size={26} />
                  <i />
                </span>
                <span />
                <span />
              </div>
              <h2>
                {dragging ? "Отпустите файл здесь" : "Загрузите список"}
              </h2>
              <p>
                Строки можно проверить и исправить до сверки с каталогом.
                Корзина при загрузке не меняется.
              </p>
              <input
                ref={fileInput}
                id="specification-file"
                className="sr-only"
                type="file"
                accept={acceptedFiles}
                aria-label="Файл спецификации"
                disabled={disabled}
                onChange={(event) => {
                  if (event.target.files) void uploadFiles(event.target.files);
                  event.target.value = "";
                }}
              />
              <button
                type="button"
                className="primary-button upload-choose"
                disabled={disabled}
                onClick={() => fileInput.current?.click()}
              >
                <UploadCloud size={17} />
                Выбрать файл
                <ArrowRight size={16} />
              </button>
              <span className="upload-drop-hint">
                или перетащите один файл в эту область
              </span>
              <p className="upload-drop-limit">
                XLSX, DOCX, текстовый PDF, JPEG · до 10 МБ · до 50 строк · PDF
                до 10 страниц
              </p>
            </div>

            <details className="upload-fold">
              <summary>
                <FileCheck2 size={17} />
                Нет файла? Возьмите учебный образец
              </summary>
              <div className="upload-example-links">
                {examples.map(({ extension, label, Icon }) => (
                  <a
                    key={extension}
                    href={`/examples/sample.${extension}`}
                    download
                  >
                    <Icon size={18} />
                    <span>
                      <strong>{extension.toUpperCase()}</strong>
                      <small>{label}</small>
                    </span>
                    <ArrowDownToLine size={14} />
                  </a>
                ))}
              </div>
              <p className="upload-fold-note">
                Скачайте файл и загрузите его в поле выше — сценарий работает
                без сети.
              </p>
            </details>

            <details className="upload-fold">
              <summary>
                <ListChecks size={17} />
                Требования к документу
              </summary>
              <div className="upload-instruction-row">
                <span>01</span>
                <div>
                  <strong>Название или артикул</strong>
                  <p>
                    У каждой позиции должно быть понятное обозначение товара.
                  </p>
                </div>
              </div>
              <div className="upload-instruction-row">
                <span>02</span>
                <div>
                  <strong>Количество и единица</strong>
                  <p>
                    Используйте целые штуки или метры. Пропуски можно исправить
                    после загрузки.
                  </p>
                </div>
              </div>
              <div className="upload-instruction-row">
                <span>03</span>
                <div>
                  <strong>Читаемый документ</strong>
                  <p>
                    Для PDF нужен текстовый слой. Старые XLS, DOC и
                    сканированные PDF не поддерживаются.
                  </p>
                </div>
              </div>
              <div className="upload-photo-note">
                <Image size={18} />
                <p>
                  Без сети распознаётся учебный JPEG из образцов. Для других
                  фотографий нужно подключённое распознавание; если оно
                  недоступно, используйте текстовый документ.
                </p>
              </div>
            </details>

            <div className="upload-start-foot">
              <p className="upload-safe-note">
                <ShieldCheck size={17} />
                <span>Загрузка файла не добавляет товары в корзину.</span>
              </p>
              <button
                type="button"
                className="upload-chat-link"
                onClick={onOpenChat}
              >
                <MessageSquare size={16} />
                Описать задачу в чате
                <ArrowRight size={15} />
              </button>
            </div>
          </div>
        </div>
      ) : (
        <>
        {result && (
          <div ref={resultRef} className="upload-result-slot">
            <UploadResult
              latest={result}
              cart={cart}
              warehouses={warehouses}
              warehouseId={warehouseId}
              busy={busy || activity !== null}
              ready={ready}
              onConfirm={onConfirm}
              onOpenChat={onOpenChat}
              onOpenCart={onOpenCart}
            />
          </div>
        )}
        <div className="upload-review-layout">
          <div className="upload-review-main">
            <header className="upload-document-heading">
              <span className="upload-document-icon">
                <FileText size={24} />
              </span>
              <div>
                <span className="upload-eyebrow">Документ прочитан</span>
                <h2>{document.fileName}</h2>
                <p>Проверьте каждую строку перед сопоставлением.</p>
              </div>
              <button
                type="button"
                className="secondary-button"
                onClick={reset}
                disabled={disabled}
              >
                <UploadCloud size={15} />
                Другой файл
              </button>
            </header>
            {document.warnings.length > 0 && (
              <div className="upload-warnings" role="status">
                <TriangleAlert size={17} />
                <div>
                  <h3>Обратите внимание</h3>
                  <ul>
                    {document.warnings.map((warning, index) => (
                      <li key={`${index}-${warning}`}>{warning}</li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
            <div className="upload-review-intro">
              <span>
                <ListChecks size={16} />
                Строк в документе: {document.lines.length}
              </span>
              <p>Снимите отметку, чтобы исключить строку из проверки.</p>
            </div>
            <div className="upload-column-labels" aria-hidden="true">
              <span>Строка</span>
              <span>Товар или артикул</span>
              <span>Количество</span>
              <span>Единица</span>
            </div>
            <div className="upload-lines">
              {document.lines.map((line, index) => {
                const lineNumber = index + 1;
                const errors = validateLine(line);
                const prefix = `upload-line-${lineNumber}`;
                return (
                  <article
                    key={line.line_id}
                    className={`upload-line ${line.included ? "" : "excluded"}`}
                    aria-label={`Строка ${lineNumber}`}
                  >
                    <div className="upload-line-select">
                      <label>
                        <input
                          type="checkbox"
                          checked={line.included}
                          aria-label={`Включить строку ${lineNumber}`}
                          disabled={disabled}
                          onChange={(event) =>
                            onChangeLine(line.line_id, {
                              included: event.target.checked,
                            })
                          }
                        />
                        <span>{String(lineNumber).padStart(2, "0")}</span>
                      </label>
                      {!line.included && <small>Исключена</small>}
                    </div>
                    <div className="upload-query-field">
                      <label
                        className="upload-mobile-label"
                        htmlFor={`${prefix}-query`}
                      >
                        Товар или артикул
                      </label>
                      <textarea
                        id={`${prefix}-query`}
                        rows={2}
                        value={line.query}
                        maxLength={2000}
                        aria-label={`Товар, строка ${lineNumber}`}
                        aria-invalid={line.included && Boolean(errors.query)}
                        aria-describedby={
                          line.included && errors.query
                            ? `${prefix}-query-error`
                            : undefined
                        }
                        disabled={disabled || !line.included}
                        onChange={(event) =>
                          onChangeLine(line.line_id, {
                            query: event.target.value,
                          })
                        }
                      />
                      {line.included && errors.query && (
                        <p
                          id={`${prefix}-query-error`}
                          className="upload-field-error"
                        >
                          {errors.query}
                        </p>
                      )}
                    </div>
                    <div className="upload-quantity-field">
                      <label
                        className="upload-mobile-label"
                        htmlFor={`${prefix}-quantity`}
                      >
                        Количество
                      </label>
                      <input
                        id={`${prefix}-quantity`}
                        type="number"
                        inputMode="numeric"
                        min="1"
                        step="1"
                        value={line.quantity}
                        aria-label={`Количество, строка ${lineNumber}`}
                        aria-invalid={line.included && Boolean(errors.quantity)}
                        aria-describedby={
                          line.included && errors.quantity
                            ? `${prefix}-quantity-error`
                            : undefined
                        }
                        disabled={disabled || !line.included}
                        onChange={(event) =>
                          onChangeLine(line.line_id, {
                            quantity: event.target.value,
                          })
                        }
                      />
                      {line.included && errors.quantity && (
                        <p
                          id={`${prefix}-quantity-error`}
                          className="upload-field-error"
                        >
                          {errors.quantity}
                        </p>
                      )}
                    </div>
                    <div className="upload-unit-field">
                      <label
                        className="upload-mobile-label"
                        htmlFor={`${prefix}-unit`}
                      >
                        Единица
                      </label>
                      <select
                        id={`${prefix}-unit`}
                        value={line.unit}
                        aria-label={`Единица, строка ${lineNumber}`}
                        aria-invalid={line.included && Boolean(errors.unit)}
                        aria-describedby={
                          line.included && errors.unit
                            ? `${prefix}-unit-error`
                            : undefined
                        }
                        disabled={disabled || !line.included}
                        onChange={(event) =>
                          onChangeLine(line.line_id, {
                            unit: event.target
                              .value as DocumentLineDraft["unit"],
                          })
                        }
                      >
                        <option value="">Выберите</option>
                        <option value="шт">шт</option>
                        <option value="м">м</option>
                      </select>
                      {line.included && errors.unit && (
                        <p
                          id={`${prefix}-unit-error`}
                          className="upload-field-error"
                        >
                          {errors.unit}
                        </p>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
            {document.lines.length === 0 && (
              <div className="upload-no-lines">
                <FileText size={29} />
                <h3>В файле не найден список товаров</h3>
                <p>
                  Попробуйте документ с названиями, количеством и единицами по
                  строкам.
                </p>
                <button
                  type="button"
                  className="secondary-button"
                  disabled={disabled}
                  onClick={reset}
                >
                  Выбрать другой файл
                </button>
              </div>
            )}
          </div>
          <aside className="upload-review-summary">
            <div className="upload-summary-heading">
              <span className="upload-eyebrow">Следующий шаг</span>
              <h2>Сверим с каталогом</h2>
              <p>Найдём позиции и покажем, что требует уточнения.</p>
            </div>
            <div className="upload-review-warehouse">
              <MapPin size={16} />
              <div>
                <small>Выбранный склад</small>
                <strong>{warehouseName || "Склад не выбран"}</strong>
              </div>
            </div>
            <dl className="upload-line-counts">
              <div>
                <dt>К проверке</dt>
                <dd>
                  {selectedLines.length}
                  <span>стр.</span>
                </dd>
              </div>
              <div>
                <dt>Исключено</dt>
                <dd>
                  {document.lines.length - selectedLines.length}
                  <span>стр.</span>
                </dd>
              </div>
            </dl>
            {!valid && (
              <div className="upload-validation-summary" role="status">
                <TriangleAlert size={15} />
                <p>
                  {tooManyLines
                    ? "В документе больше 50 строк. Загрузите сокращённую спецификацию."
                    : selectedLines.length === 0
                      ? "Отметьте хотя бы одну строку для проверки."
                      : `Исправьте отмеченные поля. Строк с ошибками: ${invalidCount}.`}
                </p>
              </div>
            )}
            <button
              type="button"
              className="primary-button upload-propose"
              disabled={!valid || disabled}
              onClick={() => void propose()}
            >
              {activity === "propose" ? (
                <LoaderCircle size={16} />
              ) : (
                <FileCheck2 size={16} />
              )}
              {activity === "propose" ? "Проверяем…" : "Проверить по каталогу"}
              <ArrowRight size={16} />
            </button>
            <p className="upload-final-quantity">
              Количество в строке задаёт желаемый итог для этой позиции.
              Остальные позиции корзины сохранятся.
            </p>
            <p className="upload-safe-note">
              <ShieldCheck size={16} />
              <span>
                Корзина пока не изменится. Сначала вы увидите результат и
                отдельно подтвердите предложение.
              </span>
            </p>
            <button
              type="button"
              className="upload-chat-link"
              onClick={onOpenChat}
            >
              <MessageSquare size={16} />
              Открыть чат
              <ArrowRight size={15} />
            </button>
          </aside>
        </div>
        </>
      )}
    </section>
  );
}
