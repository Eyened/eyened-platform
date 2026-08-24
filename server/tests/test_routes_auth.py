from server.routes.auth import generate_secure_token, validate_secure_token


def test_generate_verify_secure_token():
    """Test that we can generate and validate a token"""
    secret_key = "some-secret-key"
    token, token_hash = generate_secure_token(secret_key)
    assert token is not None
    assert token_hash is not None
    assert token != token_hash

    assert validate_secure_token(token, token_hash, secret_key)
