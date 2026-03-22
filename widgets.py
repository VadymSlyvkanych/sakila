"""
widgets.py — переиспользуемые виджеты Textual.

Каждый виджет — самодостаточный компонент с собственной логикой
отображения и взаимодействия.
"""

from decimal import Decimal
from typing import Any

from textual.message import Message
from textual.widgets import Button, Static

from models import highlight_terms


class FilterTag(Static):
    """
    Кликабельный тег активного фильтра (жанр или год).

    Отображается под строкой поиска. При клике на тег постит
    сообщение Removed которое перехватывает SakilaApp и удаляет
    соответствующий фильтр из self.filters.

    Атрибуты:
        label: текст отображаемый в теге
        kind:  "genre" или "year" — тип фильтра
        value: значение фильтра (str для жанра, int для года)

    Пример использования:
        container.mount(FilterTag("Action", "genre", "Action"))
        container.mount(FilterTag("1990",   "year",  1990))
    """

    class Removed(Message):
        """
        Сообщение об удалении тега.
        Перехватывается через @on(FilterTag.Removed) в родительском виджете.
        """
        def __init__(self, kind: str, value: str | int) -> None:
            super().__init__()
            self.kind  = kind   # "genre" или "year"
            self.value = value  # значение фильтра для удаления

    def __init__(self, label: str, kind: str, value: str | int) -> None:
        # ✕ — символ удаления отображаемый справа от названия
        super().__init__(f"{label} ✕")
        self.label = label
        self.kind  = kind
        self.value = value

    def on_click(self) -> None:
        """Клик на тег → постим сообщение об удалении."""
        self.post_message(self.Removed(self.kind, self.value))


class FilmCard(Static):
    """
    Карточка одного фильма в списке результатов поиска.

    Отображает:
      - порядковый номер и название (с подсветкой совпадений)
      - метаданные: жанр, год, рейтинг, длительность, стоимость аренды
      - описание фильма

    Аргументы:
        index:  порядковый номер (1, 2, 3, ...)
        film:   словарь с данными фильма из MySQL
        search: строка поиска для подсветки совпадений в названии
    """

    def __init__(self, index: int, film: dict[str, Any], search: str = "") -> None:
        title    = film.get("title",        "Unknown")
        desc     = film.get("description",  "")
        category = film.get("category",     "—")
        year     = film.get("release_year", "—")
        rating   = film.get("rating",       "—")
        length   = film.get("length",       "—")
        rate     = film.get("rental_rate",  "—")

        # pymysql возвращает Decimal для числовых полей — конвертируем в строку
        if isinstance(rate, Decimal):
            rate = f"{rate:.2f}"

        # Подсвечиваем слова из поискового запроса в названии
        title_hl = highlight_terms(title, search.split() if search else [])

        text = (
            f"[dim]{index}.[/dim] [bold]{title_hl}[/bold]"
            f"  [dim]{category} · {year} · {rating} · {length} min · ${rate}[/dim]\n"
            f"[dim]{desc}[/dim]"
        )
        super().__init__(text, markup=True)


class LoadMoreButton(Button):
    """
    Кнопка дозагрузки следующей страницы результатов.

    Монтируется динамически в конец #search__results после каждой
    загрузки страницы если есть ещё результаты (offset < total).
    При нажатии удаляется и появляется снова после загрузки.
    """

    def __init__(self) -> None:
        super().__init__("Load more", variant="default")
