"""Manzil Web-UI test suite — Playwright-driven, three layers.

Layout:
- supplier/ — Senior-QA coverage of the Поставщик side (3 sub-roles)
- tk/       — Senior-QA coverage of the Транспортная Компания side
- e2e/      — cross-role scenarios with two parallel browser contexts

Page Objects live in pages/ and are shared between all three layers.
Real shared accounts (set in .env) are used post-OTP — pre-OTP coverage
exercises only the registration form and stops at the OTP screen.
"""
