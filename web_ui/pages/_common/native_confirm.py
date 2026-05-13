"""Helpers for native browser confirm dialogs (`window.confirm()`).

Manzil's UI uses `window.confirm()` for destructive actions:
  Delete warehouse → «Удалить склад «{name}»?»
  Delete vehicle   → «Удалить автомобиль «{plate}»?»
  Delete employee  → «Удалить сотрудника «{full_name}»?»

These are NOT HTML modals — they're the native browser dialog. Playwright
captures them via `page.on("dialog", handler)` and the handler decides
to accept or dismiss before any later action runs.

Usage:

    with handle_next_confirm(page, accept=True) as captured:
        button.click()  # triggers window.confirm()
    assert "Удалить склад" in captured.message

For tests where you only want to assert the dialog APPEARS (without
actually deleting), use `accept=False`.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from playwright.sync_api import Dialog, Page


@dataclass
class CapturedDialog:
    message: str = ""
    type: str = ""
    appeared: bool = False


@contextmanager
def handle_next_confirm(
    page: Page, *, accept: bool,
) -> Iterator[CapturedDialog]:
    """Install a one-shot dialog handler. Yields a record of the dialog.

    The handler is removed before exiting the block so it doesn't catch
    later dialogs from the same page.
    """
    captured = CapturedDialog()

    def _handler(dialog: Dialog) -> None:
        captured.message = dialog.message
        captured.type = dialog.type
        captured.appeared = True
        if accept:
            dialog.accept()
        else:
            dialog.dismiss()

    page.on("dialog", _handler)
    try:
        yield captured
    finally:
        page.remove_listener("dialog", _handler)
