from bot.crypto_utils import decrypt, encrypt


def test_encrypt_decrypt_round_trip():
    plain = "un-token-secreto"
    token = encrypt(plain)
    assert token != plain
    assert decrypt(token) == plain


def test_decrypt_invalid_token_returns_none():
    assert decrypt("esto-no-es-un-token-valido") is None
