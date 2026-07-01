# Manzil — Mobile Sanity (Android, Maestro)

Covers the **mobile-only** steps the web suite can't: the warehouse operator
creating an order (заявка). Once an order exists, the web carrier/shipper flows
(offer → winner select) can run.

> Status (2026-06-23): **both flows pass on the staging emulator** (2/2).
> `01_warehouse_login` and `02_warehouse_create_order` are fully automated and
> validated — the latter publishes a REAL order (e.g. QOFK-00001). App id:
> `uz.logos.manzil.warehouse.staging`; UI is **Uzbek**. Emulator AVD `manzil`
> (Pixel 6, Android 14/API 34) is set up locally.
>
> Route addresses (Shahar/Davlat/Tuman) are free-text and saved server-side per
> account: the first order adds them inline; later orders default to the saved
> from/to warehouses. The flow adds an address only if its placeholder is still
> shown (Maestro `when:`), so it works on a fresh and an established account.
> The warehouse login is a SHIPPER staff (role "Сотрудник склада"); put its
> NATIONAL phone + password in `config/maestro.env`. Keep this a dedicated,
> persistent account (the web suite only deletes the tenants it creates by exact
> name, so it won't remove a separately-provisioned mobile account).

## Prerequisites

1. **Maestro CLI**: `curl -fsSL https://get.maestro.mobile.dev | bash`
2. **Android SDK + adb** and a **running emulator** (`emulator -avd <name>`) or a
   USB device with debugging on. Verify with `adb devices`.
3. **Staging APK** installed: `adb install -r manzil-staging.apk`.
4. **Config**: `cp config/maestro.env.example config/maestro.env` and fill
   `APP_ID` + warehouse credentials.

## What's needed to finish the flows

- The staging **APK** (or where to download CI artifacts).
- The Android **application id** of the staging build.
- A way to inspect screens: `maestro studio` (records taps → gives selectors).

## Run

```bash
cd mobile
maestro studio                 # one-time: capture real selectors, fix the YAMLs
scripts/run_mobile_sanity.sh   # daily run (needs emulator + APK + maestro.env)
```

## Structure

```
mobile/
  config/maestro.env.example      — APP_ID + credentials (copy to maestro.env)
  flows/common/login.yaml         — reusable phone+password login subflow
  flows/01_warehouse_login.yaml   — M1: warehouse login
  flows/02_warehouse_create_order.yaml — M2: create order (mobile-only step)
  scripts/run_mobile_sanity.sh    — runner (Maestro → JUnit)
```
