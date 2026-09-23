from bot.domain import (
    empty_app_data,
    generate_id,
    get_cart_monthly_gross,
    get_low_stock_products,
    get_location_balance,
    get_monthly_profit_summary,
    get_total_balance,
    income_key,
    normalize_app_data,
)


def test_generate_id_has_prefix_and_is_unique():
    a = generate_id("prod")
    b = generate_id("prod")
    assert a.startswith("prod_")
    assert a != b


def test_income_key_format_matches_web():
    assert income_key("cart1", 2026, 9, 22) == "cart1|2026|9|22"


def test_normalize_app_data_fills_defaults_for_none():
    data = normalize_app_data(None)
    assert data["version"] == 5
    assert data["carts"] == []
    assert data["settings"]["defaultMerchandisePercent"] == 30


def test_normalize_app_data_preserves_existing_fields():
    raw = {"carts": [{"id": "c1", "name": "Oroño"}], "settings": {"businessName": "Mi negocio"}}
    data = normalize_app_data(raw)
    assert data["carts"] == [{"id": "c1", "name": "Oroño"}]
    assert data["settings"]["businessName"] == "Mi negocio"
    assert data["settings"]["defaultMerchandisePercent"] == 30  # default preserved


def test_stock_balance_entrada_salida_ajuste():
    movements = [
        {"productId": "p1", "locationId": "deposito-central", "type": "entrada", "quantity": 10},
        {"productId": "p1", "locationId": "deposito-central", "type": "salida", "quantity": 3},
        {"productId": "p1", "locationId": "deposito-central", "type": "ajuste", "quantity": -1},
        {"productId": "p2", "locationId": "deposito-central", "type": "entrada", "quantity": 100},
    ]
    assert get_total_balance(movements, "p1") == 6
    assert get_location_balance(movements, "p1", "deposito-central") == 6
    assert get_location_balance(movements, "p1", "otro-lugar") == 0


def test_low_stock_products_sorted_by_deficit_desc():
    data = empty_app_data()
    data["products"] = [
        {"id": "p1", "name": "A", "minStock": 10, "unit": "unid"},
        {"id": "p2", "name": "B", "minStock": 5, "unit": "unid"},
    ]
    data["stockMovements"] = [
        {"productId": "p1", "locationId": "x", "type": "entrada", "quantity": 2},  # deficit 8
        {"productId": "p2", "locationId": "x", "type": "entrada", "quantity": 4},  # deficit 1
    ]
    low = get_low_stock_products(data)
    assert [item.product["id"] for item in low] == ["p1", "p2"]
    assert low[0].deficit == 8


def test_monthly_profit_summary_matches_expected_math():
    data = empty_app_data()
    data["carts"] = [{"id": "c1", "name": "Oroño"}]
    data["employees"] = [{"id": "e1", "cartId": "c1", "name": "Ana", "hourlyRate": 100, "active": True}]
    data["dailyIncome"] = {income_key("c1", 2026, 9, 1): 1000, income_key("c1", 2026, 9, 2): 500}
    data["attendance"] = {"e1|2026|9|1": {"hoursWorked": 4}}
    data["otherCosts"] = [{"id": "co1", "year": 2026, "month": 9, "description": "Nafta", "amount": 200}]

    report = get_monthly_profit_summary(data, 2026, 9)

    assert get_cart_monthly_gross(data, "c1", 2026, 9) == 1500
    assert report.total_gross == 1500
    assert report.total_employees == 400  # 4 horas * 100
    assert report.total_ventas_net == 1100
    assert report.total_other_costs == 200
    assert report.net_profit == 900  # 1100 - 200
