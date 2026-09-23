"""Logica de negocio y forma de los datos, replicada 1 a 1 desde el frontend de
pororo-control (src/types.ts, src/lib/calculations.ts, src/lib/stock.ts, src/lib/id.ts,
src/store/defaultData.ts). No hay una API propia de pororo-control: el frontend web lee y
escribe directamente un unico registro JSON en Supabase (tabla pororo_control_state,
columna payload), protegido por Row Level Security para que cada cuenta solo vea el suyo.

Este bot usa exactamente la misma fila para que cualquier cambio hecho por Telegram
aparezca de inmediato en la web (y viceversa). Por eso esta capa reproduce el mismo
formato de datos y los mismos calculos que usa la web, para que ambas queden siempre
consistentes.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any

DEPOSIT_LOCATION_ID = "deposito-central"

MERCHANDISE_CATEGORIES = [
    "Golosinas",
    "Maíz",
    "Hielo",
    "Verdulería",
    "Gaseosas",
    "Bolsitas",
    "Chino",
]

PRODUCT_CATEGORIES = [
    "Elaboracion propia",
    "Snacks y Galletitas",
    "Golosinas y Kiosco",
    "Bebidas e Infusiones",
    "Juguetes",
    "Insumos y Materias Primas",
]

MOVEMENT_TYPES = ("entrada", "salida", "ajuste")

DATA_VERSION = 5


def generate_id(prefix: str = "id") -> str:
    """Mismo esquema que src/lib/id.ts: prefijo_tiempoBase36_azar."""
    t = int(time.time() * 1000)
    time_part = _to_base36(t)
    random_part = "".join(random.choice("0123456789abcdefghijklmnopqrstuvwxyz") for _ in range(8))
    return f"{prefix}_{time_part}_{random_part}"


def _to_base36(number: int) -> str:
    if number == 0:
        return "0"
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = []
    n = number
    while n:
        n, r = divmod(n, 36)
        out.append(digits[r])
    return "".join(reversed(out))


def income_key(cart_id: str, year: int, month: int, day: int) -> str:
    return f"{cart_id}|{year}|{month}|{day}"


def attendance_key(employee_id: str, year: int, month: int, day: int) -> str:
    return f"{employee_id}|{year}|{month}|{day}"


def merchandise_key(cart_id: str, year: int, month: int) -> str:
    return f"{cart_id}|{year}|{month}"


def empty_app_data(business_name: str = "Pororo Control") -> dict[str, Any]:
    """Estructura minima valida (una cuenta nueva creada desde el bot arranca vacia;
    si el/la usuaria ya tiene cuenta con datos de la web, load_app_data los trae tal cual)."""
    return {
        "version": DATA_VERSION,
        "carts": [],
        "employees": [],
        "dailyIncome": {},
        "attendance": {},
        "merchandisePercents": {},
        "merchandiseEntries": [],
        "otherCosts": [],
        "costTemplates": [],
        "products": [],
        "stockMovements": [],
        "settings": {"defaultMerchandisePercent": 30, "businessName": business_name},
    }


def normalize_app_data(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Rellena campos faltantes con valores por defecto, igual que normalizeAppData en la
    web, para tolerar datos guardados por versiones viejas de la app."""
    base = empty_app_data()
    if not raw:
        return base
    merged = {**base, **raw}
    merged["version"] = DATA_VERSION
    merged.setdefault("settings", base["settings"])
    merged["settings"] = {**base["settings"], **(raw.get("settings") or {})}
    return merged


# ---------------------------------------------------------------------------
# Stock
# ---------------------------------------------------------------------------


def get_total_balance(movements: list[dict[str, Any]], product_id: str) -> float:
    total = 0.0
    for m in movements:
        if m.get("productId") != product_id:
            continue
        qty = m.get("quantity", 0)
        if m.get("type") == "entrada":
            total += qty
        elif m.get("type") == "salida":
            total -= qty
        else:  # ajuste
            total += qty
    return total


def get_location_balance(movements: list[dict[str, Any]], product_id: str, location_id: str) -> float:
    total = 0.0
    for m in movements:
        if m.get("productId") != product_id or m.get("locationId") != location_id:
            continue
        qty = m.get("quantity", 0)
        if m.get("type") == "entrada":
            total += qty
        elif m.get("type") == "salida":
            total -= qty
        else:
            total += qty
    return total


@dataclass
class LowStockItem:
    product: dict[str, Any]
    total_stock: float
    deficit: float


def get_low_stock_products(data: dict[str, Any]) -> list[LowStockItem]:
    items = []
    for product in data.get("products", []):
        total_stock = get_total_balance(data.get("stockMovements", []), product["id"])
        deficit = product.get("minStock", 0) - total_stock
        if deficit > 0:
            items.append(LowStockItem(product=product, total_stock=total_stock, deficit=deficit))
    items.sort(key=lambda i: i.deficit, reverse=True)
    return items


# ---------------------------------------------------------------------------
# Ganancias / resumen mensual (misma logica que getMonthlyProfitSummary)
# ---------------------------------------------------------------------------


def get_day_range(year: int, month: int) -> list[int]:
    import calendar

    _, days_in_month = calendar.monthrange(year, month)
    return list(range(1, days_in_month + 1))


def get_cart_monthly_gross(data: dict[str, Any], cart_id: str, year: int, month: int) -> float:
    daily_income = data.get("dailyIncome", {})
    return sum(daily_income.get(income_key(cart_id, year, month, d), 0) for d in get_day_range(year, month))


def get_day_hours_worked(data: dict[str, Any], employee_id: str, year: int, month: int, day: int) -> float:
    record = data.get("attendance", {}).get(attendance_key(employee_id, year, month, day))
    return record.get("hoursWorked", 0) if record else 0


def get_employee_monthly_total(data: dict[str, Any], employee: dict[str, Any], year: int, month: int) -> float:
    total = 0.0
    for day in get_day_range(year, month):
        hours = get_day_hours_worked(data, employee["id"], year, month, day)
        if hours > 0:
            total += hours * employee.get("hourlyRate", 0)
    return total


def get_cart_employees_total(data: dict[str, Any], cart_id: str, year: int, month: int) -> float:
    return sum(
        get_employee_monthly_total(data, e, year, month)
        for e in data.get("employees", [])
        if e.get("cartId") == cart_id
    )


def get_monthly_other_costs_total(data: dict[str, Any], year: int, month: int) -> float:
    return sum(
        c.get("amount", 0)
        for c in data.get("otherCosts", [])
        if c.get("year") == year and c.get("month") == month
    )


def get_monthly_merchandise_total(data: dict[str, Any], year: int, month: int) -> float:
    return sum(
        e.get("amount", 0)
        for e in data.get("merchandiseEntries", [])
        if e.get("year") == year and e.get("month") == month
    )


@dataclass
class CartVentasSummary:
    cart_id: str
    cart_name: str
    gross: float
    employees_total: float
    net_after_employees: float


@dataclass
class MonthlyProfitSummary:
    carts: list[CartVentasSummary] = field(default_factory=list)
    total_gross: float = 0
    total_employees: float = 0
    total_ventas_net: float = 0
    total_merchandise: float = 0
    total_other_costs: float = 0
    total_expenses: float = 0
    net_profit: float = 0


def get_monthly_profit_summary(data: dict[str, Any], year: int, month: int) -> MonthlyProfitSummary:
    carts = []
    for cart in data.get("carts", []):
        gross = get_cart_monthly_gross(data, cart["id"], year, month)
        employees_total = get_cart_employees_total(data, cart["id"], year, month)
        carts.append(
            CartVentasSummary(
                cart_id=cart["id"],
                cart_name=cart["name"],
                gross=gross,
                employees_total=employees_total,
                net_after_employees=gross - employees_total,
            )
        )
    total_gross = sum(c.gross for c in carts)
    total_employees = sum(c.employees_total for c in carts)
    total_ventas_net = total_gross - total_employees
    total_merchandise = get_monthly_merchandise_total(data, year, month)
    total_other_costs = get_monthly_other_costs_total(data, year, month)
    total_expenses = total_merchandise + total_other_costs
    return MonthlyProfitSummary(
        carts=carts,
        total_gross=total_gross,
        total_employees=total_employees,
        total_ventas_net=total_ventas_net,
        total_merchandise=total_merchandise,
        total_other_costs=total_other_costs,
        total_expenses=total_expenses,
        net_profit=total_ventas_net - total_expenses,
    )
