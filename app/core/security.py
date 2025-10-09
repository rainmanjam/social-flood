"""
Security utilities for the Social Flood application.

This module provides utilities for input sanitization, token handling,
and other security-related functionality.
"""

import base64
import hashlib
import html
import json
import logging
import re
import secrets
import string
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError, ValidationError

# Configure logger
logger = logging.getLogger(__name__)

# Security token bearer scheme
security = HTTPBearer()


def sanitize_html(content: str) -> str:
    """
    Sanitize HTML content to prevent XSS attacks.

    Args:
        content: The HTML content to sanitize

    Returns:
        str: Sanitized HTML content
    """
    # Simple HTML escaping
    return html.escape(content)


def sanitize_input(value: str, allow_html: bool = False) -> str:
    """
    Sanitize user input to prevent injection attacks.

    Args:
        value: The input value to sanitize
        allow_html: Whether to allow HTML content

    Returns:
        str: Sanitized input value
    """
    if not value:
        return value

    # Convert to string if not already
    if not isinstance(value, str):
        value = str(value)

    # Sanitize HTML if not allowed
    if not allow_html:
        value = sanitize_html(value)

    # Remove control characters
    value = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", value)

    return value


def validate_url(url: str, allowed_schemes: List[str] = None) -> bool:
    """
    Validate a URL for security.

    Args:
        url: The URL to validate
        allowed_schemes: List of allowed URL schemes

    Returns:
        bool: True if the URL is valid and secure
    """
    if not url:
        return False

    if allowed_schemes is None:
        allowed_schemes = ["http", "https"]

    try:
        parsed = urlparse(url)

        # Check scheme
        if parsed.scheme not in allowed_schemes:
            return False

        # Check netloc (domain)
        if not parsed.netloc:
            return False

        # Additional checks can be added here

        return True
    except Exception:
        return False


def generate_random_string(length: int = 32) -> str:
    """
    Generate a cryptographically secure random string.

    Args:
        length: The length of the string

    Returns:
        str: Random string
    """
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def hash_password(password: str, salt: Optional[str] = None) -> Dict[str, str]:
    """
    Hash a password using a secure algorithm.

    Args:
        password: The password to hash
        salt: Optional salt (generated if not provided)

    Returns:
        Dict[str, str]: Dictionary with hash and salt
    """
    if not salt:
        salt = generate_random_string(16)

    # Use a secure hashing algorithm (SHA-256)
    hash_obj = hashlib.sha256((password + salt).encode())
    password_hash = hash_obj.hexdigest()

    return {"hash": password_hash, "salt": salt}


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """
    Verify a password against a hash.

    Args:
        password: The password to verify
        password_hash: The stored password hash
        salt: The salt used for hashing

    Returns:
        bool: True if the password is correct
    """
    # Hash the provided password with the same salt
    hash_obj = hashlib.sha256((password + salt).encode())
    computed_hash = hash_obj.hexdigest()

    # Compare the hashes
    return computed_hash == password_hash


def create_access_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None, settings: Optional[Settings] = None
) -> str:
    """
    Create a JWT access token.

    Args:
        data: The data to encode in the token
        expires_delta: Optional expiration time
        settings: Optional settings instance

    Returns:
        str: JWT access token
    """
    if settings is None:
        settings = get_settings()

    # Copy the data to avoid modifying the original
    to_encode = data.copy()

    # Set expiration time
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode.update({"exp": expire.timestamp()})

    # Create a simple token (not a real JWT)
    # In a real application, use a proper JWT library
    payload = base64.b64encode(json.dumps(to_encode).encode()).decode()
    signature = hashlib.sha256((payload + settings.SECRET_KEY).encode()).hexdigest()

    return f"{payload}.{signature}"


def decode_access_token(token: str, settings: Optional[Settings] = None) -> Dict[str, Any]:
    """
    Decode a JWT access token.

    Args:
        token: The token to decode
        settings: Optional settings instance

    Returns:
        Dict[str, Any]: The decoded token data

    Raises:
        AuthenticationError: If the token is invalid
    """
    if settings is None:
        settings = get_settings()

    try:
        # Split the token
        parts = token.split(".")
        if len(parts) != 2:
            raise AuthenticationError("Invalid token format")

        payload, signature = parts

        # Verify the signature
        expected_signature = hashlib.sha256((payload + settings.SECRET_KEY).encode()).hexdigest()
        if signature != expected_signature:
            raise AuthenticationError("Invalid token signature")

        # Decode the payload
        decoded_payload = json.loads(base64.b64decode(payload).decode())

        # Check expiration
        if "exp" in decoded_payload:
            expiration = decoded_payload["exp"]
            if expiration < time.time():
                raise AuthenticationError("Token has expired")

        return decoded_payload
    except Exception as e:
        if isinstance(e, AuthenticationError):
            raise

        logger.exception("Token decoding failed")
        raise AuthenticationError("Invalid token")


async def get_token_from_request(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Get the token from the request.

    Args:
        credentials: The HTTP authorization credentials

    Returns:
        str: The token

    Raises:
        AuthenticationError: If the token is missing or invalid
    """
    if not credentials:
        raise AuthenticationError("Missing authentication credentials")

    return credentials.credentials


async def get_current_token_data(
    token: str = Depends(get_token_from_request), settings: Settings = Depends(get_settings)
) -> Dict[str, Any]:
    """
    Get the data from the current token.

    Args:
        token: The token
        settings: Application settings

    Returns:
        Dict[str, Any]: The token data

    Raises:
        AuthenticationError: If the token is invalid
    """
    return decode_access_token(token, settings)


def validate_email(email: str) -> bool:
    """
    Validate an email address.

    Args:
        email: The email address to validate

    Returns:
        bool: True if the email is valid
    """
    # Simple email validation regex
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_phone_number(phone: str) -> bool:
    """
    Validate a phone number.

    Args:
        phone: The phone number to validate

    Returns:
        bool: True if the phone number is valid
    """
    # Simple phone number validation regex
    # Allows various formats like +1-123-456-7890, (123) 456-7890, 123.456.7890
    pattern = r"^(\+\d{1,3}[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}$"
    return bool(re.match(pattern, phone))


def validate_credit_card(card_number: str) -> bool:
    """
    Validate a credit card number using the Luhn algorithm.

    Args:
        card_number: The credit card number to validate

    Returns:
        bool: True if the credit card number is valid
    """
    # Remove spaces and dashes
    card_number = card_number.replace(" ", "").replace("-", "")

    # Check if the card number contains only digits
    if not card_number.isdigit():
        return False

    # Check length (most card numbers are 13-19 digits)
    if not 13 <= len(card_number) <= 19:
        return False

    # Luhn algorithm
    digits = [int(d) for d in card_number]
    checksum = 0

    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit

    return checksum % 10 == 0


def mask_sensitive_data(data: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
    """
    Mask sensitive data in a dictionary.

    Args:
        data: The data to mask
        fields: List of fields to mask

    Returns:
        Dict[str, Any]: The masked data
    """
    # Create a copy of the data
    masked_data = data.copy()

    # Mask each field
    for field in fields:
        if field in masked_data and masked_data[field]:
            value = str(masked_data[field])

            # Different masking strategies based on field type
            if field.lower() in ["password", "secret", "key", "token"]:
                # Completely mask passwords and secrets
                masked_data[field] = "********"
            elif field.lower() in ["credit_card", "card_number", "cc"]:
                # Mask credit card numbers (show last 4 digits)
                if len(value) > 4:
                    masked_data[field] = "*" * (len(value) - 4) + value[-4:]
                else:
                    masked_data[field] = "****"
            elif field.lower() in ["email", "mail"]:
                # Mask email addresses (show domain)
                parts = value.split("@")
                if len(parts) == 2:
                    username, domain = parts
                    if len(username) > 2:
                        masked_username = username[0] + "*" * (len(username) - 2) + username[-1]
                    else:
                        masked_username = "*" * len(username)
                    masked_data[field] = f"{masked_username}@{domain}"
                else:
                    masked_data[field] = "****@****.com"
            elif field.lower() in ["phone", "phone_number", "mobile"]:
                # Mask phone numbers (show last 4 digits)
                digits = "".join(c for c in value if c.isdigit())
                if len(digits) > 4:
                    masked_data[field] = "*" * (len(digits) - 4) + digits[-4:]
                else:
                    masked_data[field] = "****"
            else:
                # Default masking strategy (show first and last character)
                if len(value) > 2:
                    masked_data[field] = value[0] + "*" * (len(value) - 2) + value[-1]
                else:
                    masked_data[field] = "**"

    return masked_data


def rate_limit_key_generator(request: Request) -> str:
    """
    Generate a key for rate limiting based on the request.

    Args:
        request: The request object

    Returns:
        str: The rate limit key
    """
    # Try to get the API key from the request
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"rate_limit:api_key:{api_key}"

    # Fall back to IP address
    client_host = request.client.host if request.client else "unknown"
    return f"rate_limit:ip:{client_host}"


def get_client_info(request: Request) -> Dict[str, Any]:
    """
    Get information about the client from the request.

    Args:
        request: The request object

    Returns:
        Dict[str, Any]: Client information
    """
    return {
        "ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("User-Agent"),
        "referer": request.headers.get("Referer"),
        "accept_language": request.headers.get("Accept-Language"),
    }


def is_safe_redirect_url(url: str, allowed_hosts: List[str] = None) -> bool:
    """
    Check if a redirect URL is safe.

    Args:
        url: The redirect URL
        allowed_hosts: List of allowed hosts

    Returns:
        bool: True if the URL is safe
    """
    if not url:
        return False

    # Get settings
    settings = get_settings()

    # Use default allowed hosts if not provided
    if allowed_hosts is None:
        allowed_hosts = ["localhost", "127.0.0.1", "socialflood.com", "api.socialflood.com"]

    try:
        # Parse the URL
        parsed = urlparse(url)

        # Allow relative URLs
        if not parsed.netloc:
            return True

        # Check if the host is allowed
        return parsed.netloc in allowed_hosts
    except Exception:
        return False


def generate_csrf_token() -> str:
    """
    Generate a CSRF token.

    Returns:
        str: CSRF token
    """
    return generate_random_string(32)


def verify_csrf_token(request_token: str, session_token: str) -> bool:
    """
    Verify a CSRF token.

    Args:
        request_token: The token from the request
        session_token: The token from the session

    Returns:
        bool: True if the token is valid
    """
    if not request_token or not session_token:
        return False

    return request_token == session_token
