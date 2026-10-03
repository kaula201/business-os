"""Georgian business-rule validators."""
from fastapi import HTTPException


def validate_identification_code(code: str, is_person: bool) -> str:
    """Validate a Georgian identification code.

    Legal entities: exactly 9 digits.
    Physical persons: exactly 11 digits.
    Rule marked "needs verification" legally — confirm with Revenue Service
    before production use.
    """
    expected = 11 if is_person else 9
    label = "პირადი" if is_person else "კომპანიის"
    if len(code) != expected or not code.isdigit():
        raise HTTPException(
            status_code=422,
            detail=f"{label} ნომერი უნდა იყოს ზუსტად {expected} ციფრი",
        )
    return code
