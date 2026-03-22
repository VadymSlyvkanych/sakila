"""
modals.py — модальные экраны для выбора фильтров.

Модальные экраны в Textual — это ModalScreen которые отображаются
поверх основного экрана. Они блокируют ввод пока открыты.

Для открытия используется app.push_screen(Modal(...), callback).
Callback вызывается когда экран закрывается через self.dismiss(value).
"""

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, SelectionList


# CSS для обоих модальных экранов.
# Вынесен в константу чтобы не дублировать в каждом классе.
MODAL_CSS = """
GenresModal, YearsModal {
    /* Центрируем модалку и затемняем фон */
    align: center middle;
    background: $background 50%;
}
#modal__container {
    width: 50;
    height: auto;
    max-height: 80%;
    background: $surface;
    border: thick $primary;
    padding: 1 2;
}
#modal__list {
    height: auto;
    max-height: 20;
}
Label {
    padding-bottom: 1;
    text-style: bold;
}
.modal__footer {
    height: auto;
    margin-top: 1;
}
.modal__footer Horizontal {
    height: auto;
}
.modal__footer Button {
    width: 100%;
}
.modal__footer Horizontal Button {
    width: 1fr;
}
"""


class GenresModal(ModalScreen[frozenset[str]]):
    """
    Модальный экран для выбора жанров фильмов.

    Тип возвращаемого значения ModalScreen[frozenset[str]] означает что
    dismiss() вернёт frozenset[str] — множество выбранных жанров.

    Принимает:
        genres:   полный список жанров из БД
        selected: уже выбранные жанры (для восстановления состояния
                  при повторном открытии модалки)
    """
    CSS = MODAL_CSS

    def __init__(self, genres: list[str], selected: frozenset[str]) -> None:
        super().__init__()
        self.genres   = genres
        self.selected = selected

    def compose(self) -> ComposeResult:
        with Vertical(id="modal__container"):
            yield Label("Select genres")
            yield SelectionList(id="modal__list")
            with Vertical(classes="modal__footer"):
                with Horizontal():
                    yield Button("Clear", id="modal__clear", variant="warning")
                    yield Button("Apply", id="modal__apply", variant="primary")

    def on_mount(self) -> None:
        """Заполняем список жанров и восстанавливаем предыдущий выбор."""
        sl = self.query_one("#modal__list", SelectionList)
        for g in self.genres:
            sl.add_option((g, g))
            if g in self.selected:
                sl.select(g)

    @on(Button.Pressed, "#modal__clear")
    def on_clear(self) -> None:
        """Снимаем выделение со всех жанров."""
        self.query_one("#modal__list", SelectionList).deselect_all()

    @on(Button.Pressed, "#modal__apply")
    def on_apply(self) -> None:
        """Закрываем модалку и передаём выбранные жанры в callback."""
        sl = self.query_one("#modal__list", SelectionList)
        self.dismiss(frozenset(sl.selected))


class YearsModal(ModalScreen[frozenset[int]]):
    """
    Модальный экран для выбора годов выпуска.

    Дополнительная кнопка "Fill gaps" удобна когда нужно выбрать
    диапазон: отмечаем первый и последний год, нажимаем Fill gaps —
    и все годы между ними выбираются автоматически.

    Тип возвращаемого значения: frozenset[int] — множество годов.
    """
    CSS = MODAL_CSS

    def __init__(self, years: list[int], selected: frozenset[int]) -> None:
        super().__init__()
        self.years    = years
        self.selected = selected

    def compose(self) -> ComposeResult:
        with Vertical(id="modal__container"):
            yield Label("Select years")
            yield SelectionList(id="modal__list")
            with Vertical(classes="modal__footer"):
                # Fill gaps — над кнопками Clear/Apply
                yield Button("Fill gaps", id="modal__fill", variant="default")
                with Horizontal():
                    yield Button("Clear", id="modal__clear", variant="warning")
                    yield Button("Apply", id="modal__apply", variant="primary")

    def on_mount(self) -> None:
        """Заполняем список годов и восстанавливаем предыдущий выбор."""
        sl = self.query_one("#modal__list", SelectionList)
        for y in self.years:
            sl.add_option((str(y), y))
            if y in self.selected:
                sl.select(y)

    @on(Button.Pressed, "#modal__clear")
    def on_clear(self) -> None:
        self.query_one("#modal__list", SelectionList).deselect_all()

    @on(Button.Pressed, "#modal__fill")
    def on_fill_gaps(self) -> None:
        """
        Выбирает все годы между минимальным и максимальным выбранными.
        Требует минимум 2 выбранных года.
        """
        sl       = self.query_one("#modal__list", SelectionList)
        selected = set(sl.selected)
        if len(selected) < 2:
            return
        lo, hi = min(selected), max(selected)
        for y in self.years:
            if lo <= y <= hi:
                sl.select(y)

    @on(Button.Pressed, "#modal__apply")
    def on_apply(self) -> None:
        """Закрываем модалку и передаём выбранные годы в callback."""
        sl = self.query_one("#modal__list", SelectionList)
        # Явно конвертируем в int — SelectionList может вернуть разные типы
        self.dismiss(frozenset(int(v) for v in sl.selected))
