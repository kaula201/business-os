import pytest
from fastapi import HTTPException

from app.core.georgia import validate_identification_code


def test_legal_valid_9_digits():
    assert validate_identification_code("123456789", False) == "123456789"


def test_legal_invalid_length_raises_422():
    with pytest.raises(HTTPException) as exc:
        validate_identification_code("12345678", False)
    assert exc.value.status_code == 422
    assert "9" in exc.value.detail


def test_legal_non_digit_raises_422():
    with pytest.raises(HTTPException) as exc:
        validate_identification_code("12345678A", False)
    assert exc.value.status_code == 422


def test_person_valid_11_digits():
    assert validate_identification_code("01234567890", True) == "01234567890"


def test_person_invalid_length_raises_422():
    with pytest.raises(HTTPException) as exc:
        validate_identification_code("0123456789", True)
    assert exc.value.status_code == 422
    assert "11" in exc.value.detail


def test_person_non_digit_raises_422():
    with pytest.raises(HTTPException) as exc:
        validate_identification_code("0123456789A", True)
    assert exc.value.status_code == 422
