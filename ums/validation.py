"""Shared validation, extracted without changing student-service behavior."""
import re


def required_text(values):
    cleaned = {}
    for field, value in values.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field.replace('_', ' ')} is required")
        cleaned[field] = value.strip()
        if len(cleaned[field]) > 200:
            raise ValueError(f"{field.replace('_', ' ')} must be 200 characters or fewer")
    return cleaned


def student_details(values):
    cleaned = required_text(values)
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", cleaned["email"]):
        raise ValueError("email must have a valid address format")
    return cleaned

