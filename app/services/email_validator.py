"""Email format and domain deliverability validation using email-validator.

Validates email syntax, normalizes addresses, and checks domain deliverability
via DNS/MX records without sending any OTPs, verification emails, or fake SMTP probes.
Handles DNS timeouts and transient network errors gracefully so valid addresses
are not rejected due to network hiccups.
"""
from __future__ import annotations

import logging
import socket
from email_validator import (
    validate_email,
    EmailNotValidError,
    EmailSyntaxError,
    EmailUndeliverableError,
    ValidatedEmail,
)
import dns.exception

log = logging.getLogger("internradar.email_validator")

# Common disposable / temporary email domains to reject
_DISPOSABLE_DOMAINS: set[str] = {
    "mailinator.com", "guerrillamail.com", "tempmail.com", "throwaway.email",
    "yopmail.com", "trashmail.com", "sharklasers.com", "guerrillamailblock.com",
    "grr.la", "dispostable.com", "temp-mail.org", "fakeinbox.com",
    "maildrop.cc", "10minutemail.com", "getnada.com",
}


def validate_email_deliverable(email: str) -> tuple[bool, str, str]:
    """Validate email syntax and domain deliverability without sending emails or OTPs.

    Returns:
        (is_valid: bool, normalized_email: str, error_detail: str)
        If valid: (True, normalized_email, "")
        If invalid: (False, original_email, user_friendly_error_message)

    LIMITATION NOTE:
        DNS/MX deliverability checks verify that the destination domain exists and has
        configured mail exchangers capable of receiving email. This does NOT guarantee
        that an individual mailbox or user exists on that domain (which cannot be verified
        reliably without sending an email or violating provider policies).
    """
    if not email or not isinstance(email, str) or not email.strip():
        return False, email or "", "Email address is required."

    raw_email = email.strip()

    # Block disposable email services
    parts = raw_email.rsplit("@", 1)
    if len(parts) == 2:
        domain = parts[1].lower().strip()
        if domain in _DISPOSABLE_DOMAINS:
            return False, raw_email, "Disposable email addresses are not allowed. Please use a permanent email address."

    # Perform syntax validation and domain deliverability check
    try:
        validated: ValidatedEmail = validate_email(raw_email, check_deliverability=True)
        return True, validated.normalized.lower(), ""

    except EmailSyntaxError as e:
        return False, raw_email, f"Invalid email format: {e}"

    except EmailUndeliverableError as e:
        err_msg = str(e)
        low_err = err_msg.lower()

        # Check if error is due to a temporary network or DNS timeout/resolution glitch
        transient_indicators = ["timeout", "temporary", "connection", "try again", "nameserver"]
        if any(ind in low_err for ind in transient_indicators):
            log.warning(
                "DNS deliverability check encountered transient error for %s: %s; falling back to syntax validation",
                raw_email, err_msg
            )
            try:
                syntax_validated: ValidatedEmail = validate_email(raw_email, check_deliverability=False)
                return True, syntax_validated.normalized, ""
            except EmailNotValidError as se:
                return False, raw_email, f"Invalid email address: {se}"

        # Real deliverability failure: domain does not exist, does not accept email, or reject-all SPF
        return False, raw_email, f"Undeliverable email domain: {err_msg}"

    except (dns.exception.DNSException, socket.error, TimeoutError) as e:
        # Graceful handling for DNS timeouts and network failures:
        # Do not incorrectly reject valid addresses solely due to a temporary DNS/network issue
        log.warning(
            "DNS timeout / network error during deliverability check for %s: %s; falling back to syntax check",
            raw_email, e
        )
        try:
            syntax_validated: ValidatedEmail = validate_email(raw_email, check_deliverability=False)
            return True, syntax_validated.normalized, ""
        except EmailNotValidError as se:
            return False, raw_email, f"Invalid email address: {se}"

    except EmailNotValidError as e:
        return False, raw_email, f"Email validation failed: {e}"

    except Exception as e:
        log.exception("Unexpected error during email validation for %s", raw_email)
        try:
            syntax_validated = validate_email(raw_email, check_deliverability=False)
            return True, syntax_validated.normalized, ""
        except Exception:
            return False, raw_email, "Unable to validate email address. Please verify your email format."
