"""Tests for authentication endpoints."""

import pytest
from backend.core.security import hash_password, verify_password, create_access_token, decode_access_token


class TestPasswordHashing:
    def test_hash_password(self):
        """Password should be hashed and different from original."""
        hashed = hash_password("mypassword123")
        assert hashed != "mypassword123"
        assert len(hashed) > 20

    def test_verify_correct_password(self):
        """Correct password should verify successfully."""
        hashed = hash_password("mypassword123")
        assert verify_password("mypassword123", hashed) is True

    def test_verify_wrong_password(self):
        """Wrong password should fail verification."""
        hashed = hash_password("mypassword123")
        assert verify_password("wrongpassword", hashed) is False


class TestJWT:
    def test_create_and_decode_token(self):
        """JWT token should be created and decoded correctly."""
        data = {"sub": "user-123", "email": "test@test.com"}
        token = create_access_token(data)
        payload = decode_access_token(token)
        assert payload["sub"] == "user-123"
        assert payload["email"] == "test@test.com"

    def test_invalid_token_raises_error(self):
        """Invalid token should raise HTTPException."""
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            decode_access_token("invalid.token.here")

    def test_expired_token_raises_error(self):
        """Expired token should raise HTTPException."""
        from fastapi import HTTPException
        # Create token that expires immediately
        from backend.core import security
        original = security.settings.jwt_expiry_minutes
        security.settings.jwt_expiry_minutes = -1  # Already expired
        try:
            token = create_access_token({"sub": "user-123"})
            with pytest.raises(HTTPException):
                decode_access_token(token)
        finally:
            security.settings.jwt_expiry_minutes = original