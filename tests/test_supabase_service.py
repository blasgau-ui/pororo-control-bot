from types import SimpleNamespace

from bot.supabase_service import _extract_payload


def test_extract_payload_none_response_means_no_row_yet():
    # Comportamiento real observado de postgrest-py 2.x: maybe_single().execute()
    # devuelve None (no un objeto con .data=None) cuando la cuenta todavía no tiene fila.
    assert _extract_payload(None) is None


def test_extract_payload_response_with_no_data():
    assert _extract_payload(SimpleNamespace(data=None)) is None


def test_extract_payload_response_with_row():
    payload = {"version": 5, "carts": []}
    res = SimpleNamespace(data={"payload": payload})
    assert _extract_payload(res) == payload
