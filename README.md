# Sakila — Advanced Title Search

> **Финальный проект курса Python** — TUI-приложение для поиска фильмов  
> по базе данных Sakila с аналитикой поисковых запросов.

---

## Содержание

- [Цель проекта](#цель-проекта)
- [Быстрый старт](#быстрый-старт)
- [Конфигурация](#конфигурация)
- [Технологии](#технологии)
- [Структура проекта](#структура-проекта)
- [Дерево виджетов](#дерево-виджетов)
- [Работа с базами данных](#работа-с-базами-данных)
- [Примеры работы](#примеры-работы)

---

## Цель проекта

Приложение демонстрирует практическое применение Python для разработки терминального интерфейса с подключением к реальным базам данных. В проекте реализованы:

- полнотекстовый поиск через MySQL FULLTEXT индекс
- фильтрация по жанрам и годам выпуска с пагинацией результатов
- сохранение истории поиска в MongoDB
- аналитика поисковых запросов (топ запросов, жанров, годов)
- многовкладочный интерфейс с живой статистикой

---

## Быстрый старт

### Вариант 1 — через uv (рекомендуется)

```bash
# 1. Клонируем репозиторий
git clone https://github.com/VadymSlyvkanych/sakila.git
cd sakila

# 2. Устанавливаем зависимости из pyproject.toml (uv создаёт виртуальное окружение автоматически)
uv sync

# 3. Запускаем приложение
uv run sakila.py
```

### Вариант 2 — через pip

```bash
# 1. Клонируем репозиторий
git clone https://github.com/VadymSlyvkanych/sakila.git
cd sakila

# 2. Создаём и активируем виртуальное окружение
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# 3. Устанавливаем зависимости
pip install textual pymysql pymongo

# 4. Запускаем приложение
python sakila.py
```

### Требования

| Компонент | Версия |
|-----------|--------|
| Python    | 3.10+  |
| Textual   | 8.x    |
| pymysql   | любая  |
| pymongo   | любая  |

---

## Конфигурация

Все настройки подключений находятся в файле **`config.py`**.  
Перед запуском замените значения на свои:

```python
# config.py

# --- MySQL ---
sakila_db = MySQLDB(
    host="your-mysql-host",       # адрес сервера MySQL
    user="your-user",             # имя пользователя
    password="your-password",     # пароль
    database="sakila",            # имя базы данных
)

# --- MongoDB ---
MONGO_URI = (
    "mongodb://your-user:your-password@your-mongo-host/"
    "?authSource=your-auth-db"
)
MONGO_COLLECTION = "your-collection-name"
```

### Полнотекстовый индекс MySQL

Приложение использует FULLTEXT поиск по полю `title` таблицы `film`.  
Индекс нужно создать один раз:

```sql
ALTER TABLE film ADD FULLTEXT INDEX fulltext_title (title);
```

Проверить что индекс создан:

```sql
SHOW INDEX FROM film WHERE Key_name = 'fulltext_title';
```

---

## Технологии

| Технология | Роль в проекте |
|------------|----------------|
| [Textual](https://textual.textualize.io/) | TUI-фреймворк: виджеты, экраны, CSS-стили, реактивность |
| MySQL + pymysql | Основная база данных Sakila: фильмы, жанры, годы |
| MongoDB + pymongo | Хранение и аналитика поисковых запросов |
| Python dataclasses | Иммутабельная модель данных `Filters` (frozen=True) |
| Python threading | Фоновые запросы к БД через `@work(thread=True)` |

### Паттерны и решения

**Singleton для подключения к БД** — класс `Database` в `db.py` реализует паттерн Singleton: повторный вызов `MySQLDB(**config)` с теми же параметрами возвращает уже существующий объект, а не создаёт новое соединение.

**Иммутабельные фильтры** — `Filters` объявлен как `@dataclass(frozen=True)`. При изменении фильтров создаётся новый объект через `dc_replace()`. Это делает безопасной передачу фильтров в фоновый поток: поток держит ссылку на старый объект который никто не может изменить.

**Retry при потере соединения** — если MySQL-соединение разрывается по таймауту, `db.py` обнуляет `self.conn = None`. При следующем запросе соединение восстанавливается автоматически. Дополнительно в `_do_search` реализованы 2 попытки с паузой 0.5с между ними на случай гонки воркеров.

---

## Структура проекта

```
sakila/
│
├── sakila.py      # Точка входа. Класс SakilaApp — главный экран приложения
├── config.py      # Подключения к MySQL и MongoDB, константы (PAGE_SIZE и др.)
├── models.py      # Класс Filters и функция highlight_terms
├── mongo.py       # Работа с MongoDB: save_search(), get_stats(), clear_all()
├── widgets.py     # Виджеты: FilterTag, FilmCard, LoadMoreButton
├── modals.py      # Модальные экраны: GenresModal, YearsModal
├── styles.tcss    # CSS-стили приложения (Textual CSS)
├── db.py          # Универсальный модуль БД (MySQL, SQLite, PostgreSQL)
└── README.md      # Этот файл
```

---

## Дерево виджетов

```
SakilaApp
├── Header
├── TabbedContent
│   ├── TabPane "Search"  (#tab__search)
│   │   └── Vertical (#main)
│   │       ├── Horizontal (#search__row)
│   │       │   ├── Input (#search__input)          — строка поиска
│   │       │   └── Button "Clear" (#clear__input)  — очистка строки
│   │       ├── Horizontal (#controls__row)
│   │       │   ├── Static "Search filters:"        — подпись
│   │       │   ├── Button "Genres" (#open__genres) — открывает GenresModal
│   │       │   ├── Button "Years" (#open__years)   — открывает YearsModal
│   │       │   ├── Static "Sort by:"               — подпись
│   │       │   └── Select (#sort__select)          — сортировка результатов
│   │       ├── Vertical (#active__filters)         — панель тегов фильтров
│   │       │   └── Horizontal (.tags__row)         — строка тегов (динамически)
│   │       │       └── FilterTag                   — тег жанра или года (×N)
│   │       ├── Static (#status)                    — "Found: X | Loaded: Y"
│   │       └── VerticalScroll (#search__results)   — список результатов
│   │           ├── FilmCard                        — карточка фильма (динамически)
│   │           └── LoadMoreButton                  — дозагрузка (если есть ещё)
│   │
│   ├── TabPane "Statistics"  (#tab__statistics)
│   │   └── VerticalScroll (#stats__container)
│   │       ├── Horizontal (#stats__buttons)
│   │       │   ├── Button "Refresh"               — обновить статистику
│   │       │   └── Button "Clear all"             — удалить всю статистику
│   │       ├── Static (#stats__total)             — общее кол-во запросов
│   │       ├── Vertical (.stats__section)         — Топ 5 запросов
│   │       ├── Vertical (.stats__section)         — Последние 5 запросов
│   │       ├── Vertical (.stats__section)         — Топ 5 жанров
│   │       └── Vertical (.stats__section)         — Топ 5 годов
│   │
│   └── TabPane "README"  (#tab__readme)
│       └── MarkdownViewer                         — отображение README.md
│
├── GenresModal  (ModalScreen, поверх основного экрана)
│   └── Vertical (#modal__container)
│       ├── Label "Select genres"
│       ├── SelectionList (#modal__list)
│       └── Vertical (.modal__footer)
│           └── Horizontal
│               ├── Button "Clear"
│               └── Button "Apply"
│
├── YearsModal  (ModalScreen, поверх основного экрана)
│   └── Vertical (#modal__container)
│       ├── Label "Select years"
│       ├── SelectionList (#modal__list)
│       └── Vertical (.modal__footer)
│           ├── Button "Fill gaps"
│           └── Horizontal
│               ├── Button "Clear"
│               └── Button "Apply"
│
└── Footer
```

### Ключевые компоненты

**`FilterTag`** — кликабельный тег активного фильтра. При клике постит сообщение `FilterTag.Removed` которое `SakilaApp` перехватывает и удаляет соответствующий фильтр.

**`FilmCard`** — карточка фильма. Создаётся динамически для каждого результата поиска. Подсвечивает вхождения поискового запроса в названии через Rich-разметку.

**`LoadMoreButton`** — появляется в конце списка результатов если загружено меньше чем найдено. После нажатия удаляется и появляется снова после загрузки следующей страницы.

**`GenresModal` / `YearsModal`** — модальные экраны поверх основного. Блокируют ввод пока открыты. Возвращают результат через `dismiss(value)` в callback переданный в `push_screen()`.

---

## Работа с базами данных

### MySQL — поиск фильмов

Таблицы Sakila задействованные в запросах:

| Таблица | Поля | Назначение |
|---------|------|-----------|
| `film` | `film_id, title, description, release_year, rating, length, rental_rate` | Основная таблица фильмов |
| `film_category` | `film_id, category_id` | Связь фильм ↔ жанр |
| `category` | `category_id, name` | Справочник жанров |

#### Запрос поиска

Приложение формирует динамический SQL в зависимости от заполненных фильтров:

```sql
-- Пример: поиск "batman" в жанре Action за 1990-е, сортировка по релевантности
SELECT
    f.film_id,
    f.title,
    f.description,
    f.release_year,
    f.rating,
    f.length,
    f.rental_rate,
    c.name AS category,
    MATCH(f.title) AGAINST ('batman*' IN BOOLEAN MODE) AS relevance
FROM film f
JOIN film_category fc ON f.film_id = fc.film_id
JOIN category      c  ON fc.category_id = c.category_id
WHERE
    MATCH(f.title) AGAINST ('batman*' IN BOOLEAN MODE)
    AND c.name IN ('Action')
    AND f.release_year IN (1990, 1991, 1992, ..., 1999)
ORDER BY relevance DESC, f.title
LIMIT 10 OFFSET 0;
```

#### Запрос подсчёта (для пагинации)

```sql
-- Выполняется перед основным запросом чтобы знать общее количество
SELECT COUNT(DISTINCT f.film_id) AS total
FROM film f
JOIN film_category fc ON f.film_id = fc.film_id
JOIN category      c  ON fc.category_id = c.category_id
WHERE
    MATCH(f.title) AGAINST ('batman*' IN BOOLEAN MODE)
    AND c.name IN ('Action');
```

#### Загрузка справочников

```sql
-- Жанры (при старте приложения)
SELECT name FROM category ORDER BY name;

-- Годы выпуска (при старте приложения)
SELECT DISTINCT release_year FROM film ORDER BY release_year;
```

#### FULLTEXT индекс

Поиск использует MySQL BOOLEAN MODE — каждое слово получает суффикс `*` для поиска по префиксу. Запрос `"dark knight"` превращается в `"dark* knight*"` что найдёт "Darkness", "Knights" и т.д.

```sql
-- Создание индекса (выполнить один раз)
ALTER TABLE film ADD FULLTEXT INDEX fulltext_title (title);

-- Проверка
SHOW INDEX FROM film WHERE Key_name = 'fulltext_title';
```

---

### MongoDB — статистика поиска

#### Структура документа

Каждый поисковый запрос сохраняется как документ:

```json
{
  "_id":        "ObjectId(...)",
  "query":      "batman",
  "genres":     ["Action", "Drama"],
  "years":      [1990, 1991, 1992],
  "created_at": "2026-03-20T14:30:00Z"
}
```

#### Aggregation pipelines

**Топ-5 текстовых запросов по частоте:**

```python
db.collection.aggregate([
  { $match:  { query: { $ne: "" } } },  // исключаем пустые
  { $group:  { _id: "$query", count: { $sum: 1 } } },
  { $sort:   { count: -1 } },
  { $limit:  5 }
])
```

**Топ-5 жанров** (`$unwind` разворачивает массив в отдельные документы):

```python
db.collection.aggregate([
  { $unwind: "$genres" },               // ["Action","Drama"] → 2 документа
  { $group:  { _id: "$genres", count: { $sum: 1 } } },
  { $sort:   { count: -1 } },
  { $limit:  5 }
])
```

**Топ-5 годов** (аналогично жанрам):

```python
db.collection.aggregate([
  { $unwind: "$years" },
  { $group:  { _id: "$years", count: { $sum: 1 } } },
  { $sort:   { count: -1 } },
  { $limit:  5 }
])
```

---

## Примеры работы

### Вкладка Search

![Вкладка Search](./images/Screenshot_01.png)

### Модальный экран выбора жанров

![Модальный экран выбора жанров](./images/Screenshot_02.png)

### Вкладка Statistics

![Вкладка Statistics](./images/Screenshot_03.png)

---

## Горячие клавиши

| Клавиша | Действие |
|---------|----------|
| `Ctrl+Q` | Выйти из приложения |

---

## Автор

**Vadym Slyvkanych** — финальный проект курса Python, группа 101025-ptm, апрель 2026.
