"""
sakila.py — точка входа приложения Sakila TUI.

Запуск:
    uv run sakila.py

Структура проекта:
    sakila.py   — точка входа, главный класс SakilaApp
    config.py   — конфигурация: подключения к БД, константы
    models.py   — модели данных (Filters, highlight_terms)
    mongo.py    — работа с MongoDB (сохранение и чтение статистики)
    widgets.py  — переиспользуемые виджеты (FilterTag, FilmCard, LoadMoreButton)
    modals.py   — модальные экраны (GenresModal, YearsModal)
    styles.tcss — CSS стили приложения
    db.py       — универсальный модуль для работы с БД (MySQL, SQLite, Postgres)
    README.md   — документация проекта
"""

import time
from dataclasses import replace as dc_replace
from pathlib import Path
from typing import Any

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    MarkdownViewer,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

# Модули проекта
from config   import sakila_db, searches_col, SORT_OPTIONS, PAGE_SIZE, TAG_WIDTH_EXTRA, README_PATH
from models   import Filters
from mongo    import save_search, get_stats, clear_all
from widgets  import FilterTag, FilmCard, LoadMoreButton
from modals   import GenresModal, YearsModal


class SakilaApp(App):
    """
    Главный класс приложения.

    Управляет:
    - состоянием фильтров (self.filters)
    - пагинацией результатов (self.offset, self.total_found)
    - справочниками жанров и годов (self.available_*)
    - координацией между UI и фоновыми воркерами
    """

    TITLE     = "Sakila"
    SUB_TITLE = "Advanced title search"
    BINDINGS  = [("ctrl+q", "quit", "Quit")]

    # Подключаем внешний CSS файл
    CSS_PATH = Path(__file__).parent / "styles.tcss"

    # -------------------------------------------------------------------------
    # Инициализация
    # -------------------------------------------------------------------------

    def __init__(self) -> None:
        super().__init__()
        # Текущее состояние фильтров (immutable — см. models.py)
        self.filters: Filters = Filters()

        # Пагинация результатов
        self.offset:      int = 0   # сколько уже загружено
        self.total_found: int = 0   # всего найдено в БД

        # Справочники из БД — заполняются при старте
        self.available_genres: list[str] = []
        self.available_years:  list[int] = []

    def on_mount(self) -> None:
        self.theme = "gruvbox"
        self.load_options()

    # -------------------------------------------------------------------------
    # Разметка (структура UI)
    # -------------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():

            # --- Вкладка 1: Поиск фильмов ---
            with TabPane("Search", id="tab__search"):
                with Vertical(id="main"):
                    with Horizontal(id="search__row"):
                        yield Input(id="search__input", placeholder="e.g. Godfather")
                        yield Button("Clear", id="clear__input", variant="warning")
                    with Horizontal(id="controls__row"):
                        yield Static("Search filters:", id="label__filters")
                        yield Button("Genres", id="open__genres")
                        yield Button("Years",  id="open__years")
                        yield Static("Sort by:", id="label__sort")
                        yield Select(
                            SORT_OPTIONS,
                            value="relevance",
                            id="sort__select",
                            allow_blank=False,
                        )
                    # Панель тегов активных фильтров (заполняется динамически)
                    yield Vertical(id="active__filters")
                    # Строка статуса: "Found: X | Loaded: Y"
                    yield Static("", id="status")
                    # Список карточек фильмов (заполняется динамически)
                    yield VerticalScroll(id="search__results")

            # --- Вкладка 2: Статистика поиска ---
            with TabPane("Statistics", id="tab__statistics"):
                with VerticalScroll(id="stats__container"):
                    with Horizontal(id="stats__buttons"):
                        yield Button("Refresh",   id="stats__refresh", variant="primary")
                        yield Button("Clear all", id="stats__clear",   variant="warning")
                    yield Static("", id="stats__total")
                    with Vertical(classes="stats__section"):
                        yield Static("Last 5 queries", classes="stats__title")
                        yield Static("", id="stats__recent")
                    with Vertical(classes="stats__section"):
                        yield Static("Top 5 keywords", classes="stats__title")
                        yield Static("", id="stats__top")
                    with Vertical(classes="stats__section"):
                        yield Static("Top 5 genres", classes="stats__title")
                        yield Static("", id="stats__genres")
                    with Vertical(classes="stats__section"):
                        yield Static("Top 5 years", classes="stats__title")
                        yield Static("", id="stats__years")

            # --- Вкладка 3: README ---
            with TabPane("README", id="tab__readme"):
                readme_text = README_PATH.read_text() if README_PATH.exists() else "README.md not found"
                yield MarkdownViewer(readme_text, show_table_of_contents=True)

        yield Footer()

    # -------------------------------------------------------------------------
    # Загрузка справочников из MySQL
    # -------------------------------------------------------------------------

    @work(thread=True)
    def load_options(self) -> None:
        """
        Загружает списки жанров и годов из MySQL в фоновом потоке.
        Вызывается один раз при старте приложения.
        """
        genres = sakila_db.query("SELECT name FROM category ORDER BY name")
        years  = sakila_db.query(
            "SELECT DISTINCT release_year FROM film ORDER BY release_year"
        )
        self.call_from_thread(
            self._set_options,
            [row["name"] for row in genres],
            [int(row["release_year"]) for row in years],
        )

    def _set_options(self, genres: list[str], years: list[int]) -> None:
        """Сохраняет справочники (вызывается в главном потоке)."""
        self.available_genres = genres
        self.available_years  = years

    # -------------------------------------------------------------------------
    # Обработчики модальных экранов
    # -------------------------------------------------------------------------

    @on(Button.Pressed, "#open__genres")
    def open_genres_modal(self) -> None:
        """Открывает модалку выбора жанров."""
        self.push_screen(
            GenresModal(self.available_genres, self.filters.genres),
            self._on_genres_selected,
        )

    @on(Button.Pressed, "#open__years")
    def open_years_modal(self) -> None:
        """Открывает модалку выбора годов."""
        self.push_screen(
            YearsModal(self.available_years, self.filters.years),
            self._on_years_selected,
        )

    def _on_genres_selected(self, selected: frozenset[str]) -> None:
        """Callback вызываемый после закрытия GenresModal."""
        self.filters = dc_replace(self.filters, genres=selected)
        self._refresh_filter_tags()
        self._reset_and_search()

    def _on_years_selected(self, selected: frozenset[int]) -> None:
        """Callback вызываемый после закрытия YearsModal."""
        self.filters = dc_replace(self.filters, years=selected)
        self._refresh_filter_tags()
        self._reset_and_search()

    # -------------------------------------------------------------------------
    # Обработчики UI — вкладка Search
    # -------------------------------------------------------------------------

    @on(Button.Pressed, "#clear__input")
    def on_clear_input(self) -> None:
        """Очищает строку поиска и возвращает на неё фокус."""
        inp = self.query_one("#search__input", Input)
        inp.value = ""
        self.filters = dc_replace(self.filters, search="")
        inp.focus()

    @on(Input.Changed, "#search__input")
    def on_search_changed(self, event: Input.Changed) -> None:
        """Обновляет фильтр поиска при каждом изменении строки (не запускает поиск)."""
        self.filters = dc_replace(self.filters, search=event.value.strip())

    @on(Input.Submitted, "#search__input")
    def on_search_submitted(self) -> None:
        """Запускает поиск по нажатию Enter."""
        self._reset_and_search()

    @on(Select.Changed, "#sort__select")
    def on_sort_changed(self, event: Select.Changed) -> None:
        """Меняет тип сортировки и перезапускает поиск."""
        self.filters = dc_replace(self.filters, sort=str(event.value))
        self._reset_and_search()

    @on(Button.Pressed, "LoadMoreButton")
    def on_load_more(self) -> None:
        """Дозагружает следующую страницу результатов."""
        for btn in self.query("LoadMoreButton"):
            btn.remove()
        self._do_search(replace=False)

    @on(FilterTag.Removed)
    def on_filter_tag_removed(self, event: FilterTag.Removed) -> None:
        """Удаляет фильтр по клику на тег и перезапускает поиск."""
        if event.kind == "genre":
            self.filters = dc_replace(
                self.filters, genres=self.filters.genres - {event.value}
            )
        elif event.kind == "year":
            self.filters = dc_replace(
                self.filters, years=self.filters.years - {event.value}
            )
        self._refresh_filter_tags()
        self._reset_and_search()

    # -------------------------------------------------------------------------
    # Обработчики UI — вкладка Statistics
    # -------------------------------------------------------------------------

    @on(Button.Pressed, "#stats__refresh")
    def on_stats_refresh(self) -> None:
        """Перезагружает статистику из MongoDB."""
        self.load_statistics()

    @on(Button.Pressed, "#stats__clear")
    def on_stats_clear(self) -> None:
        """Удаляет всю статистику из MongoDB."""
        self.clear_statistics()

    @work(thread=True)
    def clear_statistics(self) -> None:
        """Удаляет все документы из коллекции и обновляет UI."""
        try:
            clear_all()
        except Exception as e:
            self.call_from_thread(self._update_statistics_error, str(e))
            return
        # После удаления перезагружаем (покажет "No data yet")
        self.call_from_thread(self.load_statistics)

    # -------------------------------------------------------------------------
    # Обработчик переключения вкладок
    # -------------------------------------------------------------------------

    @on(TabbedContent.TabActivated)
    def on_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """
        Реагирует на переключение вкладок:
        - Search: фокусирует строку поиска
        - Statistics: обновляет статистику из MongoDB
        """
        if event.pane.id == "tab__search":
            # Небольшая задержка нужна — Textual ещё монтирует TabPane
            self.set_timer(0.1, lambda: self.query_one("#search__input", Input).focus())
        elif event.pane.id == "tab__statistics":
            self.load_statistics()

    def on_resize(self) -> None:
        """Пересчитывает строки тегов при изменении размера окна."""
        if self.filters.genres or self.filters.years:
            self._refresh_filter_tags()

    # -------------------------------------------------------------------------
    # Управление тегами активных фильтров
    # -------------------------------------------------------------------------

    def _refresh_filter_tags(self) -> None:
        """
        Пересобирает панель тегов фильтров под строкой поиска.

        Теги разбиваются на строки по ширине экрана:
        если следующий тег не помещается в текущую строку —
        начинается новая строка (Horizontal).
        """
        container = self.query_one("#active__filters", Vertical)
        container.remove_children()

        # Собираем все теги: сначала жанры, потом годы
        all_tags = (
            [FilterTag(g,      "genre", g) for g in sorted(self.filters.genres)] +
            [FilterTag(str(y), "year",  y) for y in sorted(self.filters.years)]
        )
        if not all_tags:
            return

        # Доступная ширина: ширина экрана минус margin контейнера (2+2) и запас (1)
        available_width = self.size.width - 5
        current_row:   list[FilterTag] = []
        current_width: int             = 0

        for tag in all_tags:
            tag_width = len(tag.label) + TAG_WIDTH_EXTRA
            if current_row and current_width + tag_width > available_width:
                # Текущая строка заполнена — монтируем её и начинаем новую
                self._mount_tag_row(container, current_row)
                current_row   = [tag]
                current_width = tag_width
            else:
                current_row.append(tag)
                current_width += tag_width

        # Монтируем последнюю (или единственную) строку
        if current_row:
            self._mount_tag_row(container, current_row)

    def _mount_tag_row(self, container: Vertical, tags: list[FilterTag]) -> None:
        """Монтирует одну горизонтальную строку тегов в контейнер."""
        row = Horizontal(classes="tags__row")
        container.mount(row)
        for tag in tags:
            row.mount(tag)

    # -------------------------------------------------------------------------
    # Поиск (MySQL)
    # -------------------------------------------------------------------------

    def _reset_and_search(self) -> None:
        """Сбрасывает пагинацию и запускает поиск с первой страницы."""
        self.offset      = 0
        self.total_found = 0
        self._do_search(replace=True)

    @work(thread=True)
    def _do_search(self, replace: bool) -> None:
        """
        Выполняет поиск в фоновом потоке.

        Аргументы:
            replace: True  — очистить список и показать первую страницу
                     False — дописать следующую страницу в конец

        Логика retry:
            После таймаута БД сбрасывает соединение (self.conn = None в db.py).
            Но если старый зависший воркер ещё не завершился, он может снова
            обнулить соединение уже после того как новый воркер подключился.
            Поэтому делаем 2 попытки с паузой 0.5с между ними.
        """
        # Снимаем иммутабельный снимок состояния для передачи в поток
        filters = self.filters
        offset  = self.offset

        if filters.is_empty:
            self.call_from_thread(self._update_results, [], replace, 0)
            return

        # Сохраняем запрос в MongoDB (не прерываем поиск при ошибке MongoDB)
        try:
            save_search(filters)
        except Exception:
            pass

        # Попытки выполнить SQL запрос (с одним retry при потере соединения)
        last_error: Exception | None = None
        for _ in range(2):
            try:
                results, total = self._fetch_results(filters, offset, PAGE_SIZE)
                last_error = None
                break
            except Exception as e:
                last_error = e
                time.sleep(0.5)  # пауза перед повторной попыткой

        if last_error is not None:
            self.call_from_thread(self._show_db_error, str(last_error))
            return

        self.call_from_thread(self._update_results, results, replace, total)

    def _fetch_results(
        self,
        filters: Filters,
        offset:  int,
        limit:   int,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Строит SQL запрос на основе фильтров и выполняет его.

        Возвращает:
            (список фильмов, общее количество совпадений в БД)

        Запрос включает:
            - поиск по f.title
            - фильтр по жанрам (JOIN с category)
            - фильтр по годам выпуска
            - сортировку по релевантности / названию / году

        Важно: при сортировке по релевантности MATCH() вызывается дважды —
        один раз в WHERE для фильтрации, второй в SELECT для получения значения.
        Это особенность MySQL FULLTEXT.
        """
        conditions: list[str] = []
        params:     list[Any] = []

        # Поиск по f.title
        words = [f"%{word}%" for word in filters.search.split()]

        if words:
            conditions.append(f"({" OR ".join(["(f.title LIKE %s)"] * len(words))})")
            params.extend(words)

        # Фильтр по жанрам через JOIN с таблицей category
        if filters.genres:
            placeholders = ", ".join(["%s"] * len(filters.genres))
            conditions.append(f"c.name IN ({placeholders})")
            params.extend(sorted(filters.genres))

        # Фильтр по годам выпуска
        if filters.years:
            placeholders = ", ".join(["%s"] * len(filters.years))
            conditions.append(f"f.release_year IN ({placeholders})")
            params.extend(sorted(filters.years))

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        # Определяем сортировку
        if filters.sort == "relevance" and words:
            relevance = f", ({" + ".join(["(f.title LIKE %s)"] * len(words))}) AS relevance"
            order = "ORDER BY relevance DESC, f.title"
            extra = words
        elif filters.sort == "year":
            relevance, order, extra = "", "ORDER BY f.release_year ASC, f.title", []
        else:  # "title" или relevance без текстового запроса
            relevance, order, extra = "", "ORDER BY f.title", []

        sql_count = f"""
            SELECT COUNT(DISTINCT f.film_id) AS total
            FROM film f
            JOIN film_category fc ON f.film_id = fc.film_id
            JOIN category c ON fc.category_id = c.category_id
            {where}
        """

        sql_data = f"""
            SELECT
                f.film_id,
                f.title,
                f.description,
                f.release_year,
                f.rating,
                f.length,
                f.rental_rate,
                c.name AS category
                {relevance}
            FROM film f
            JOIN film_category fc ON f.film_id = fc.film_id
            JOIN category c ON fc.category_id = c.category_id
            {where}
            {order}
            LIMIT %s OFFSET %s
        """

        total = (sakila_db.query(sql_count, params) or [{"total": 0}])[0]["total"]
        films = sakila_db.query(sql_data, extra + params + [limit, offset])
        return films, total

    def _update_results(
        self,
        results: list[dict[str, Any]],
        replace: bool,
        total:   int,
    ) -> None:
        """
        Обновляет список результатов (вызывается в главном потоке через call_from_thread).

        Аргументы:
            results: список фильмов для отображения
            replace: True — очистить список, False — дописать в конец
            total:   общее количество найденных фильмов
        """
        container = self.query_one("#search__results", VerticalScroll)
        status    = self.query_one("#status", Static)

        if replace:
            container.remove_children()
            self.total_found = total

        start = self.offset + 1
        for i, film in enumerate(results):
            container.mount(FilmCard(start + i, film, search=self.filters.search))

        self.offset += len(results)
        
        status.update(
            f"Found: {self.total_found} | Loaded: {self.offset}"
            if self.total_found else "" if self.filters.is_empty else "Oops! We couldn’t find anything."
        )

        # Кнопка "Load more" появляется если загружено меньше чем найдено
        if self.offset < self.total_found:
            container.mount(LoadMoreButton())

    def _show_db_error(self, message: str) -> None:
        """Показывает сообщение об ошибке БД в строке статуса."""
        short = message[:80] + "..." if len(message) > 80 else message
        self.query_one("#status", Static).update(f"[red]DB Error: {short}[/]")

    # -------------------------------------------------------------------------
    # Статистика (MongoDB)
    # -------------------------------------------------------------------------

    @work(thread=True)
    def load_statistics(self) -> None:
        """Загружает статистику из MongoDB в фоновом потоке."""
        try:
            stats = get_stats()
        except Exception as e:
            self.call_from_thread(self._update_statistics_error, str(e))
            return
        self.call_from_thread(self._update_statistics, stats)

    def _update_statistics(self, stats: dict) -> None:
        """
        Отрисовывает статистику в UI (вызывается в главном потоке).

        Использует две вспомогательные функции для форматирования:
        - fmt_list:   для топ-списков (запросы, жанры, годы)
        - fmt_recent: для последних запросов (с деталями фильтров)
        """

        def fmt_list(rows: list[dict], key: str) -> str:
            """Форматирует список вида: 1. Значение  ×N"""
            if not rows:
                return "[dim]No data yet[/dim]"
            return "\n".join(
                f"[dim]{i+1}.[/dim] [bold]{row[key]}[/bold]  [dim]×{row['count']}[/dim]"
                for i, row in enumerate(rows)
            )

        def fmt_recent(rows: list[dict]) -> str:
            """Форматирует последние запросы с деталями жанров и годов."""
            if not rows:
                return "[dim]No data yet[/dim]"
            lines = []
            for i, row in enumerate(rows):
                parts = []
                if row.get("query"):
                    parts.append(f"[bold]{row['query']}[/bold]")
                if row.get("genres"):
                    parts.append(f"[dim]genres: {', '.join(row['genres'])}[/dim]")
                if row.get("years"):
                    parts.append(f"[dim]years: {', '.join(str(y) for y in row['years'])}[/dim]")
                line = f"[dim]{i+1}.[/dim] " + ("  ".join(parts) if parts else "[dim](no filters)[/dim]")
                lines.append(line)
            return "\n".join(lines)

        self.query_one("#stats__total",  Static).update(
            f"Total searches: [bold]{stats.get('total', 0)}[/bold]"
        )
        self.query_one("#stats__top",    Static).update(fmt_list(stats["top_queries"], "_id"))
        self.query_one("#stats__recent", Static).update(fmt_recent(stats["recent"]))
        self.query_one("#stats__genres", Static).update(fmt_list(stats["top_genres"], "_id"))
        self.query_one("#stats__years",  Static).update(fmt_list(stats["top_years"],  "_id"))

    def _update_statistics_error(self, message: str) -> None:
        """Показывает ошибку MongoDB во всех секциях статистики."""
        short = message[:80] + "..." if len(message) > 80 else message
        for wid in ["#stats__top", "#stats__recent", "#stats__genres", "#stats__years"]:
            self.query_one(wid, Static).update(f"[red]MongoDB Error: {short}[/]")
        self.query_one("#stats__total", Static).update("")


# =============================================================================

if __name__ == "__main__":
    SakilaApp().run()
