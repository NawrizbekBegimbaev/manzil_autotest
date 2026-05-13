"""Order creation form — `/orders/create` (DISPATCHER only).

Live recon (2026-05-03): three sections + footer:

  Груз:
    - cargoType        — «Тип груза»            text
    - weightKg         — «Вес, кг»              text (default 0)
    - volumeM3         — «Объём, м³»            text (default 0)
    - bodyType         — «Тип кузова»           combobox, default «Тент»
                          options: Тент, Рефрижератор, Изотерм,
                                   Контейнер, Низкая платформа, Другое
    - loadingMethods   — «Способ погрузки/разгрузки»  combobox
                          options: Боковая, Задняя, Верхняя

  Маршрут:
    - warehouseId      — «Склад погрузки»       combobox (own warehouses)
    - unloadAddress    — «Адрес выгрузки»       combobox (saved addresses)
    - desiredDate      — «Желаемая дата»        date input

  Дополнительно:
    - currency         — «Валюта расчёта»       combobox, default «USD»
    - notes            — «Дополнительные опции» text (optional)
    - publish          — checkbox «Опубликовать сразу…», pre-checked

  Buttons:
    - «Сохранить черновик»     → POST with publish=false, status=DRAFT
    - «Опубликовать заявку»    → POST with publish=true,  status=ACTIVE

Inline errors (assert in negative tests):
  «Укажите тип груза»
  «Вес должен быть больше нуля»
  «Объём должен быть больше нуля»
  «Выберите склад погрузки»
  «Укажите адрес выгрузки»
  «Укажите дату»

After successful submit: SPA navigates to /orders (list view).
"""

from __future__ import annotations

from playwright.sync_api import expect

from web_ui.pages._base import BasePage


class OrderCreatePage(BasePage):
    path = "/orders/create"

    # ---------- header ----------------------------------------------------

    @property
    def heading(self):
        return self.page.get_by_role("heading", name="Создание заявки")

    @property
    def back_button(self):
        return self.page.get_by_role("button", name="Назад")

    # ---------- inputs ----------------------------------------------------

    @property
    def cargo_type_input(self):
        return self.page.get_by_role("textbox", name="Тип груза")

    @property
    def weight_input(self):
        return self.page.get_by_role("textbox", name="Вес, кг")

    @property
    def volume_input(self):
        return self.page.get_by_role("textbox", name="Объём, м³")

    @property
    def body_type_select(self):
        return self.page.get_by_role("combobox", name="Тип кузова")

    @property
    def loading_methods_select(self):
        # This MUI Select has no accessible label — locate by its
        # generated id (live recon: `mui-component-select-loadingMethods`).
        return self.page.locator("#mui-component-select-loadingMethods")

    @property
    def warehouse_select(self):
        # The underlying MUI Select renders both the native `<input>` (with
        # the form name) and a sibling `<div role="combobox">` (the
        # clickable area). The visible combobox is the previous sibling.
        return self.page.locator(
            '[role="combobox"]:has(~ input[name="warehouseId"])',
        )

    @property
    def unload_address_select(self):
        return self.page.locator(
            '[role="combobox"]:has(~ input[name="unloadAddress"])',
        )

    @property
    def desired_date_picker(self):
        """The MUI X DatePicker GROUP, not a plain input.

        The «control» is a `<div role="group" name="Желаемая дата">`
        containing three `<span role="spinbutton">` sub-fields for День /
        Месяц / Год. Use `fill_desired_date()` to set a value (a plain
        `.fill()` does not work — sections are contenteditable spans).
        """
        return self.page.get_by_role("group", name="Желаемая дата")

    def fill_desired_date(self, *, day: int, month: int, year: int) -> None:
        """Set the desired-date picker via its three spinbutton sections."""
        group = self.desired_date_picker
        group.get_by_role("spinbutton", name="День").click()
        self.page.keyboard.type(f"{day:02d}")
        group.get_by_role("spinbutton", name="Месяц").click()
        self.page.keyboard.type(f"{month:02d}")
        group.get_by_role("spinbutton", name="Год").click()
        self.page.keyboard.type(f"{year:04d}")

    @property
    def currency_select(self):
        return self.page.get_by_role("combobox", name="Валюта расчёта")

    @property
    def notes_input(self):
        return self.page.get_by_role("textbox", name="Дополнительные опции")

    @property
    def publish_checkbox(self):
        return self.page.get_by_role(
            "checkbox", name="Опубликовать сразу (иначе — сохранить как черновик)",
        )

    # ---------- actions ---------------------------------------------------

    @property
    def save_draft_button(self):
        return self.page.get_by_role("button", name="Сохранить черновик")

    @property
    def publish_button(self):
        return self.page.get_by_role("button", name="Опубликовать заявку")

    # ---------- helpers ---------------------------------------------------

    def field_error(self, message: str):
        return self.page.get_by_text(message, exact=True)

    def select_option(self, combobox, option_text: str) -> None:
        """Open a Select and pick an option by visible text (substring)."""
        combobox.click()
        # `has_text=` is a substring match — works for option labels with
        # extra metadata (e.g. warehouse «Name — City, Address»).
        self.page.get_by_role("option").filter(has_text=option_text).first.click()
        # MUI Backdrop briefly intercepts pointer events; multi-select
        # popovers stay open after a click, so we Escape unconditionally.
        self.page.keyboard.press("Escape")
        self.page.locator(
            '[role="presentation"]:visible',
        ).first.wait_for(state="hidden", timeout=2_000)

    def select_first_warehouse(self) -> str:
        """Open the warehouse combobox and pick the first available option.

        Returns the option text (useful in assertions). Raises if there
        are no warehouses — meaning setup failed and the test should fail
        loudly, not silently.
        """
        self.warehouse_select.click()
        first = self.page.get_by_role("option").first
        first.wait_for(state="visible")
        text = first.inner_text()
        first.click()
        self.page.locator('[role="presentation"][aria-hidden="true"]').wait_for(
            state="hidden", timeout=2_000,
        )
        return text

    def select_first_unload_address(self) -> str:
        self.unload_address_select.click()
        first = self.page.get_by_role("option").first
        first.wait_for(state="visible")
        text = first.inner_text()
        first.click()
        self.page.locator('[role="presentation"][aria-hidden="true"]').wait_for(
            state="hidden", timeout=2_000,
        )
        return text

    def fill_required_fields(
        self,
        *,
        cargo_type: str,
        weight: int,
        volume: int,
        desired_date_iso: str,
        body_type: str = "Тент",
        loading_method: str = "Боковая",
    ) -> None:
        """Fill everything that's required to make the form submittable.

        `desired_date_iso` is an ISO string `YYYY-MM-DD` — split into
        day/month/year and typed into the MUI X DatePicker spinbuttons.
        Warehouse + unload address are picked separately.
        """
        from datetime import date as _date
        self.cargo_type_input.fill(cargo_type)
        self.weight_input.fill(str(weight))
        self.volume_input.fill(str(volume))
        self.select_option(self.body_type_select, body_type)
        self.select_option(self.loading_methods_select, loading_method)
        d = _date.fromisoformat(desired_date_iso)
        self.fill_desired_date(day=d.day, month=d.month, year=d.year)

    # ---------- assertions ------------------------------------------------

    def expect_loaded(self, *, timeout: float | None = None) -> None:
        super().expect_loaded(timeout=timeout)
        expect(self.heading).to_be_visible(timeout=timeout)
