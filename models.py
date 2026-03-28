"""
models.py — модели данных приложения.

Здесь описаны структуры данных которые передаются между
компонентами приложения.
"""

import re
from dataclasses import dataclass, replace as dc_replace
from typing import Any


@dataclass(frozen=True)
class Filters:
    """
    Неизменяемое (immutable) состояние фильтров поиска.

    Почему frozen=True?
    -------------------
    Поиск выполняется в отдельном потоке (@work(thread=True)).
    Если бы Filters был обычным изменяемым объектом, пока поток
    выполняет запрос пользователь мог бы изменить фильтры —
    и поток неожиданно увидел бы другие данные.

    С frozen=True при изменении фильтров создаётся НОВЫЙ объект
    (через dc_replace), а поток держит ссылку на старый — безопасно.

    Пример изменения:
        self.filters = dc_replace(self.filters, search="godfather")
    """

    search: str            = ""            # текст для FULLTEXT поиска
    genres: frozenset[str] = frozenset()   # выбранные жанры
    years:  frozenset[int] = frozenset()   # выбранные годы выпуска
    sort:   str            = "relevance"   # тип сортировки

    @property
    def is_empty(self) -> bool:
        """True если ни одно условие поиска не задано — запрос не нужен."""
        return not self.search and not self.genres and not self.years


def highlight_terms(text: str, terms: list[str]) -> str:
    """
    Подсвечивает вхождения поисковых слов в тексте.

    Оборачивает каждое совпадение в Rich-разметку [black on yellow]...[/]
    которую Textual умеет рендерить как цветной фон.
    Поиск регистронезависимый — "god" найдёт и "God" и "god".

    Аргументы:
        text:  исходный текст
        terms: список слов для подсветки

    Пример:
        highlight_terms("The Godfather", ["god"])
        → "The [black on yellow]God[/]father"
    """
    if not terms:
        return text
    for term in terms:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        text = pattern.sub(lambda m: f"[black on yellow]{m.group()}[/]", text)
    return text
