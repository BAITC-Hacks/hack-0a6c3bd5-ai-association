# Сторонние компоненты

Раскрытие использованных сторонних материалов по п. 5.4.4 Положения.
Состояние проверено 23.09.2026. Версии зависимостей взяты из [uv.lock](uv.lock) и [web/package-lock.json](web/package-lock.json), лицензии и ссылки на проекты — из локальных `METADATA`, `package.json` и файлов `LICENSE` установленных пакетов. Это перечень фактически подключённых компонентов текущего прототипа.

## Библиотеки

| Компонент | Версия | Лицензия | Где используется |
|---|---|---|---|
| [FastAPI](https://github.com/fastapi/fastapi) | 0.141.1 | MIT | HTTP API, раздача готового интерфейса |
| [Uvicorn](https://github.com/Kludex/uvicorn) | 0.53.0 | BSD-3-Clause | ASGI-сервер |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | 1.2.3 | BSD-3-Clause | Чтение локальной конфигурации |
| [Pydantic](https://github.com/pydantic/pydantic) | 2.13.5 | MIT | Контракты API и структурированные ответы |
| [OpenAI Python SDK](https://github.com/openai/openai-python) | 2.54.0 | Apache-2.0 | Необязательные live-вызовы через `app/llm.py` |
| [python-multipart](https://github.com/Kludex/python-multipart) | 0.0.32 | Apache-2.0 | Приём загружаемых документов |
| [openpyxl](https://foss.heptapod.net/openpyxl/openpyxl) | 3.1.5 | MIT | Чтение XLSX |
| [python-docx](https://github.com/python-openxml/python-docx) | 1.2.0 | MIT | Чтение DOCX |
| [pypdf](https://github.com/py-pdf/pypdf) | 6.19.0 | BSD-3-Clause | Извлечение текстового слоя PDF |
| [Pillow](https://github.com/python-pillow/Pillow) | 12.3.0 | MIT-CMU | Проверка и декодирование JPEG |
| [defusedxml](https://github.com/tiran/defusedxml) | 0.7.1 | PSF-2.0; в метаданных `PSFL` | Ограниченный разбор XML внутри DOCX/XLSX |
| [React / React DOM](https://react.dev/) | 19.3.0 / 19.3.0 | MIT | Интерфейс и его рендеринг |
| [Lucide React](https://lucide.dev/) | 1.47.0 | ISC; производные иконки Feather — MIT | Иконки интерфейса |
| [Onest, вариативный пакет Fontsource](https://fontsource.org/fonts/onest) | 5.3.1 | SIL OFL-1.1 | Основной шрифт интерфейса |
| [Unbounded, вариативный пакет Fontsource](https://fontsource.org/fonts/unbounded) | 5.3.0 | SIL OFL-1.1 | Акцентная типографика интерфейса |
| [IBM Plex Mono, пакет Fontsource](https://fontsource.org/fonts/ibm-plex-mono) | 5.3.0 | SIL OFL-1.1 | Артикулы и служебные подписи, начертания 400 и 500 |
| [Motion](https://github.com/motiondivision/motion) | 13.4.1 | MIT | Анимации компонентов и переходов |
| [NumberFlow React](https://github.com/barvian/number-flow) | 0.6.2 | MIT | Анимация числовых значений и суммы предложения |
| [clsx](https://github.com/lukeed/clsx) | 2.1.1 | MIT | Условное объединение CSS-классов |
| [Vite](https://vite.dev/) | 8.3.0 | MIT | Сборка интерфейса |
| [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react) | 6.1.1 | MIT | Поддержка React в Vite |
| [Tailwind CSS / @tailwindcss/vite](https://tailwindcss.com/) | 4.3.3 / 4.3.3 | MIT | Стили и обработка CSS при сборке |
| [TypeScript](https://www.typescriptlang.org/) | 5.9.3 | Apache-2.0 | Проверка типов frontend |
| [@types/node](https://github.com/DefinitelyTyped/DefinitelyTyped/tree/master/types/node) | 22.20.4 | MIT | Типы Node.js при сборке |
| [@types/react](https://github.com/DefinitelyTyped/DefinitelyTyped/tree/master/types/react) | 19.3.0 | MIT | Типы React |
| [@types/react-dom](https://github.com/DefinitelyTyped/DefinitelyTyped/tree/master/types/react-dom) | 19.3.0 | MIT | Типы React DOM |
| [HTTPX](https://github.com/encode/httpx) | 0.28.1 | BSD-3-Clause | Проверки API; также зависимость OpenAI SDK |
| [pytest](https://github.com/pytest-dev/pytest) | 9.1.1 | MIT | Автоматические проверки backend |
| [Hatchling](https://github.com/pypa/hatch/tree/master/backend) | 1.32.4 в локальном кэше сборки | MIT | Сборка Python-пакета; в `pyproject.toml` задан диапазон `>=1.27,<2`, точная версия не входит в `uv.lock` |

Версии Fontsource относятся к пакетам шрифтов. Правообладатели: Onest Project Authors, 2021; Unbounded Project Authors, 2022; IBM Corp., 2017. В [лицензии Lucide](web/public/licenses/lucide.txt) сохранено отдельное уведомление Cole Bemis / Feather для производных иконок. Полные тексты лицензий [Onest](web/public/licenses/onest.txt), [Unbounded](web/public/licenses/unbounded.txt), [IBM Plex Mono](web/public/licenses/ibm-plex-mono.txt), [React](web/public/licenses/react.txt), [React DOM](web/public/licenses/react-dom.txt), [Motion](web/public/licenses/motion.txt), [NumberFlow](web/public/licenses/number-flow.txt) и [clsx](web/public/licenses/clsx.txt) включены в `web/public/licenses` и копируются в сборку. Шрифты и иконки поставляются локально, без CDN.

Транзитивные зависимости перечислены в lock-файлах; их собственные лицензии и уведомления поставляются с пакетами (`*.dist-info`, `LICENSE`, `NOTICE`, `ThirdPartyNoticeText.txt`). В частности, файл лицензии Pillow содержит уведомления о включённых сторонних библиотеках. Lock-файл фиксирует состав и версии, но не заменяет эти тексты. Recharts в текущие зависимости и сборку не включён: экранов с графиками пока нет.

## Модели и сервисы

| Сервис | Назначение | Условия |
|---|---|---|
| OpenAI API через [официальный Python SDK](https://github.com/openai/openai-python) | Разбор информационного запроса, структурированное вступление ответа и OCR нового JPEG | Необязательный live-режим с локальными `OPENAI_API_KEY` и `OPENAI_MODEL`. Реальные вызовы 23.09.2026 проверены на `gpt-4.1-mini` (ответ провайдера: `gpt-4.1-mini-2025-04-14`). Модель по умолчанию не задана. Доступ определяется учётной записью и условиями провайдера; лицензия SDK не является лицензией модели. |
| Автономный режим приложения | Записанные формулировки, локальные правила, известный JPEG по хэшу | `DEMO_MODE=1` по умолчанию; внешние модельные вызовы, ключи и личные аккаунты не требуются. Содержимое `fixtures/` описано ниже. |
| API ekt.kz | Получение исходного снимка каталога явной командой `hack snapshot` | Доступ по инструкции организаторов; права на данные не подменяются лицензиями библиотек. `seed`, `serve` и обычный демосценарий сеть для каталога не используют. |

Реальные вызовы приложения проверены отдельно от автономных тестов: ответ, разбор запроса и OCR нового JPEG прошли с пустым кэшем; повторное OCR использовало локальный кэш. Использование конкретных промокредитов не устанавливалось. Разработка с Codex учитывается отдельно как инструмент разработки. Протокол проверки — [FINAL-QA.md](docs/FINAL-QA.md); результат одного запуска не гарантирует будущую доступность провайдера.

## Данные

| Источник | Тип | Лицензия |
|---|---|---|
| [API ekt.kz](https://ekt.kz/api/products), исходный [снимок](data/ekt-snapshot.json) и [описание преобразований](data/provenance.json) | 10 карточек, полученных 23.09.2026 по инструкции организаторов; описания, характеристики, цены и остатки. URL и время получения сохранены для каждой карточки. | Открытая лицензия на партнёрский каталог в полученных данных не указана. Авторские права на описания, товарные знаки и материалы сохраняются у соответствующих правообладателей; проект не объявляет их MIT, CC0 или собственными материалами. |
| [products.csv](data/products.csv), [stock.csv](data/stock.csv), [warehouses.csv](data/warehouses.csv) | Нормализованный снимок для SQLite: 10 исходных карточек и 3 синтетические; склады Астаны, Алматы и Шымкента. Демонстрационная единица учёта указана через `demo.unit_override`; неизвестные значения сохранены как неизвестные. | Для исходных данных действуют те же неуточнённые условия источника. Преобразования команды не меняют права на исходный каталог. |
| Команда «Контур»: `000-DEMO-UNKNOWN`, `DEMO-160-AVAILABLE`, `DEMO-160-EMPTY` | Три синтетические карточки с учебными характеристиками, ценами и остатками, `source_url=null`; не реальные предложения ekt.kz | Материалы команды для демонстрации; отдельная лицензия проекта в репозитории не задана. |
| [fixtures/consultant.json](fixtures/consultant.json) | Подготовленные командой формулировки демосценариев. Факты, проверки и суммы вычисляются по SQLite. | Материалы команды; fixture сам по себе не подтверждает вызов модели. |
| [purchase_terms.json](data/purchase_terms.json), [официальные условия](https://ekt.kz/checkout-delivery/) и [FAQ ekt.kz](https://ekt.kz/about/faq/) | Краткий пересказ публичных сведений об оплате и доставке, проверенных 23.09.2026, с датой и ссылками. Условия локальной корзины описаны отдельно. | Открытая лицензия текстов продавца не установлена; сохранены ссылки на первоисточники. Расхождение порогов доставки отмечено, тарифы не рассчитываются. |
| [fixtures/uploads](fixtures/uploads) и точные копии в [web/public/examples](web/public/examples) | Созданные командой `sample.xlsx`, `sample.docx`, `sample.pdf`, `sample.jpg`: две учебные строки; не документы реального покупателя. [jpeg.json](fixtures/uploads/jpeg.json) содержит вручную записанное извлечение и SHA-256 известного JPEG. | Материалы команды с использованными сторонними средствами подготовки; сведения о PDF и его шрифте приведены ниже. Сам по себе fixture не удостоверяет вызов OCR-провайдера. |
| Интерфейс, знак «Контур», favicon и скриншоты в `docs/assets` | Собственные компоненты и оформление; знак выполнен CSS/SVG, скриншоты показывают версии интерфейса проекта | Работа команды с помощью Claude и Codex: редизайн Claude интегрирован, Codex проверяет интеграцию. Встроенные шрифты и иконки сохраняют лицензии, указанные выше. |

В исходном JSON каталога сохранены внешние URL изображений. Сами товарные фотографии и сертификаты не включены в нормализованный каталог и статическую сборку; права на них проекту не приписываются.

В `sample.pdf`, обновлённом в `d48910c`, встроен только поднабор **DejaVu Sans**; ArialMT и ссылка на Helvetica удалены. Источник шрифта — поставляемый Poppler runtime; upstream — [DejaVu Fonts](https://dejavu-fonts.github.io/). [Полный текст лицензии](fixtures/uploads/licenses/dejavu-fonts.txt) включает уведомления Bitstream Vera и Arev; изменения DejaVu указаны как public domain. Этот текст также вложен в PDF как `dejavu-fonts-license.txt`. Генератор — **ReportLab 4.4.9**. [Файл происхождения](fixtures/uploads/sample-pdf-provenance.json) фиксирует источники, хэши и две учебные строки. Три копии PDF в `fixtures/uploads`, `web/public/examples` и `web/dist/examples` идентичны: SHA-256 `0472c4e85e36d6cdd1b841187edbcd6b1f0fb98de4e6d2ed580c4d349ba7b87e`.

## Инструменты разработки

- Claude (Anthropic) — подготовка интегрированного редизайна интерфейса. Конкретная версия модели в репозитории не зафиксирована; Claude не вызывается приложением при запуске.
- OpenAI Codex — помощь в реализации, дизайне, проверках и документации; журнал задач находится в [docs/codex-log.md](docs/codex-log.md). На машине проверки доступен `codex-cli 0.154.0-alpha.6.1`. Версия CLI не определяет модель агента и не является зависимостью приложения.
- Python 3.12; macOS проверялся на CPython 3.12.13 со SQLite 3.53.1 из стандартного модуля `sqlite3`, чистый клон Windows 11 — на Python 3.12.3. Для установки и запуска используется `uv` (локально 0.11.21); fallback — `pip` и [requirements.txt](requirements.txt).
- Node.js и npm нужны для разработки и пересборки UI: локально 26.3.1 и 11.16.0 соответственно. При запуске готового `web/dist` Node.js не нужен. Git используется для совместной работы; Docker Compose проверен на Docker 29.5.2 с Linux-образом `python:3.12-slim` как альтернативный автономный запуск (`988434a`).
- [Playwright](https://github.com/Microsoft/playwright-python) и Playwright MCP — браузерные проверки и скриншоты. Локальный пакет Playwright 1.63.0 указывает Apache-2.0; он относится к окружению проверок, а не к зависимостям запуска приложения. Результаты проверок описаны в [docs/FINAL-QA.md](docs/FINAL-QA.md).
- [ReportLab](https://www.reportlab.com/) **4.4.9** — генератор обновлённого учебного PDF; версия зафиксирована в [происхождении образца](fixtures/uploads/sample-pdf-provenance.json). Лицензия — BSD; локальные `METADATA` и `LICENSE` использованного пакета проверены при подготовке. В зависимости запуска приложения ReportLab не входит.
- FFmpeg 8.1.1 — локальная перекодировка экранной записи Playwright в MP4 и добавление субтитров H5. Использованная сборка с libx264 сообщает GPL-3.0-or-later через `ffmpeg -L`; исполняемый файл FFmpeg не включён в приложение или репозиторий. Видеозапись показывает собственный интерфейс проекта и поставляемые учебные данные.

Версии инструментов в этом разделе описывают локальную среду проверки, а не обещают одинаковую среду у второго участника или проверяющего. Ключи API, пароли и личные данные в это раскрытие не включаются.
