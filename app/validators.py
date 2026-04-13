import re
from email_validator import validate_email, EmailNotValidError
from flask import jsonify
from app.models import REGIONS, GAME_MODES, TEAM_SIDES, TOURNAMENT_FORMATS, TOURNAMENT_STATUSES

def error_response(message, status=400):
    return jsonify({"error": message}), status

def success_response(data, status=200):
    return jsonify(data), status

def require_fields(data, *fields):
    missing = [f for f in fields if f not in data or data[f] is None]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")

def validate_username(value):
    value = value.strip()
    if not (3 <= len(value) <= 24):
        raise ValueError("username must be between 3 and 24 characters")
    # only allowing these characters, spaces would cause issues later
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", value):
        raise ValueError("username can only have letters, numbers, underscores and hyphens")
    return value

def validate_email_address(value):
    try:
        return validate_email(value, check_deliverability=False).normalized
    except EmailNotValidError as e:
        raise ValueError(f"invalid email: {e}")

def validate_region(value):
    value = value.upper().strip()
    if value not in REGIONS:
        raise ValueError(f"region must be one of: {', '.join(sorted(REGIONS))}")
    return value

def validate_string(value, field_name, min_len=1, max_len=80):
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    value = value.strip()
    if not (min_len <= len(value) <= max_len):
        raise ValueError(f"{field_name} must be between {min_len} and {max_len} characters")
    return value

# these two are basically the same, positive just rejects 0 as well
def validate_non_negative_int(value, field_name):
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be 0 or more")
    return value

def validate_positive_int(value, field_name):
    value = validate_non_negative_int(value, field_name)
    if value == 0:
        raise ValueError(f"{field_name} must be greater than 0")
    return value

def validate_enum(value, allowed, field_name):
    if value not in allowed:
        raise ValueError(f"{field_name} must be one of: {', '.join(allowed)}")
    return value
