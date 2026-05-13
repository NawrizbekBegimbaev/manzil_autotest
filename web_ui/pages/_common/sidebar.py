"""Sidebar navigation — visible on every authenticated page.

Sidebar items differ per role (verified live):
  SUPPLIER_ADMIN       → Аналитика, Заявки, Склады, Сотрудники
  SUPPLIER_DISPATCHER  → Заявки, Склады
  SUPPLIER_MANAGER     → Заявки
  TK_ADMIN             → Лента заявок, Автопарк, Отклики

A test "Sidebar shows X for role Y" is itself a strong RBAC check —
hidden items mean missing permission OR wrong role binding.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

SUPPLIER_ADMIN_SIDEBAR = ("Аналитика", "Заявки", "Склады", "Сотрудники")
SUPPLIER_DISPATCHER_SIDEBAR = ("Заявки", "Склады")
SUPPLIER_MANAGER_SIDEBAR = ("Заявки",)
TK_SIDEBAR = ("Лента заявок", "Автопарк", "Отклики")

# Items that NO supplier sub-role should ever see (TK-only).
_TK_ONLY = set(TK_SIDEBAR)
# Items that no TK role should ever see.
_SUPPLIER_ONLY = set(SUPPLIER_ADMIN_SIDEBAR)


class Sidebar:
    """Thin wrapper around the left navigation rail."""

    def __init__(self, page: Page) -> None:
        self.page = page

    def link(self, name: str):
        return self.page.get_by_role("link", name=name)

    def _expect_exact(self, items: tuple[str, ...], *, timeout: float | None = None) -> None:
        expected = set(items)
        for item in expected:
            expect(self.link(item)).to_be_visible(timeout=timeout)
        # Verify nothing extra from the OTHER side leaks in.
        for foreign in (_TK_ONLY | _SUPPLIER_ONLY) - expected:
            expect(self.link(foreign)).to_have_count(0)

    def expect_supplier_admin(self, *, timeout: float | None = None) -> None:
        self._expect_exact(SUPPLIER_ADMIN_SIDEBAR, timeout=timeout)

    def expect_supplier_dispatcher(self, *, timeout: float | None = None) -> None:
        self._expect_exact(SUPPLIER_DISPATCHER_SIDEBAR, timeout=timeout)

    def expect_supplier_manager(self, *, timeout: float | None = None) -> None:
        self._expect_exact(SUPPLIER_MANAGER_SIDEBAR, timeout=timeout)

    def expect_tk(self, *, timeout: float | None = None) -> None:
        self._expect_exact(TK_SIDEBAR, timeout=timeout)

    # Legacy: smoke uses `.expect_supplier()` from before sub-roles existed.
    # Treat it as the admin layout.
    def expect_supplier(self, *, timeout: float | None = None) -> None:
        self.expect_supplier_admin(timeout=timeout)

    def navigate_to(self, name: str) -> None:
        self.link(name).click()
