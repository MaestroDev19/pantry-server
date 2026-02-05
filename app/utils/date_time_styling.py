from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal

# Format style constants
ISO_DATE_FORMAT = "%Y-%m-%d"
ISO_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"
ISO_DATETIME_WITH_TZ_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
DISPLAY_DATE_FORMAT = "%B %d, %Y"
SHORT_DATE_FORMAT = "%b %d, %Y"
VERBOSE_DATE_FORMAT = "%A, %B %d, %Y"
TIME_FORMAT = "%I:%M %p"
TIME_24H_FORMAT = "%H:%M"


def format_iso_date(*, value: date) -> str:
    """
    Format a date object to ISO 8601 format (YYYY-MM-DD).
    
    Args:
        value: The date to format.
        
    Returns:
        ISO formatted date string.
    """
    if not isinstance(value, date):
        raise TypeError(f"Expected date, got {type(value).__name__}")
    return value.strftime(ISO_DATE_FORMAT)


def format_iso_datetime(*, value: datetime, include_timezone: bool = False) -> str:
    """
    Format a datetime object to ISO 8601 format.
    
    Args:
        value: The datetime to format.
        include_timezone: If True, includes timezone offset in format.
        
    Returns:
        ISO formatted datetime string.
    """
    if not isinstance(value, datetime):
        raise TypeError(f"Expected datetime, got {type(value).__name__}")
    
    if include_timezone and value.tzinfo is not None:
        return value.strftime(ISO_DATETIME_WITH_TZ_FORMAT)
    return value.strftime(ISO_DATETIME_FORMAT)


def format_display_date(*, value: date, style: Literal["full", "short", "verbose"] = "full") -> str:
    """
    Format a date object for human-readable display.
    
    Args:
        value: The date to format.
        style: Display style - "full" (January 15, 2024), "short" (Jan 15, 2024), 
               or "verbose" (Monday, January 15, 2024).
        
    Returns:
        Formatted date string.
    """
    if not isinstance(value, date):
        raise TypeError(f"Expected date, got {type(value).__name__}")
    
    format_map = {
        "full": DISPLAY_DATE_FORMAT,
        "short": SHORT_DATE_FORMAT,
        "verbose": VERBOSE_DATE_FORMAT,
    }
    
    if style not in format_map:
        raise ValueError(f"Invalid style: {style}. Must be one of: {list(format_map.keys())}")
    
    return value.strftime(format_map[style])


def format_time(*, value: datetime | date, use_24h: bool = False) -> str:
    """
    Format the time portion of a datetime or date object.
    
    Args:
        value: The datetime or date to extract time from.
        use_24h: If True, uses 24-hour format (HH:MM), otherwise 12-hour with AM/PM.
        
    Returns:
        Formatted time string.
    """
    if isinstance(value, date) and not isinstance(value, datetime):
        raise ValueError("Cannot extract time from date object without time component")
    
    if not isinstance(value, datetime):
        raise TypeError(f"Expected datetime, got {type(value).__name__}")
    
    format_str = TIME_24H_FORMAT if use_24h else TIME_FORMAT
    return value.strftime(format_str)


def format_relative_time(*, value: datetime, reference: datetime | None = None) -> str:
    """
    Format a datetime as a relative time string (e.g., "2 days ago", "in 3 hours").
    
    Args:
        value: The datetime to format.
        reference: Reference datetime for comparison. Defaults to current UTC time.
        
    Returns:
        Relative time string.
    """
    if not isinstance(value, datetime):
        raise TypeError(f"Expected datetime, got {type(value).__name__}")
    
    if reference is None:
        reference = datetime.now(timezone.utc)
    
    if not isinstance(reference, datetime):
        raise TypeError(f"Expected datetime for reference, got {type(reference).__name__}")
    
    # Normalize to UTC for comparison if timezone-aware
    if value.tzinfo is not None:
        value_utc = value.astimezone(timezone.utc)
    else:
        value_utc = value.replace(tzinfo=timezone.utc)
    
    if reference.tzinfo is not None:
        reference_utc = reference.astimezone(timezone.utc)
    else:
        reference_utc = reference.replace(tzinfo=timezone.utc)
    
    delta = value_utc - reference_utc
    total_seconds = int(delta.total_seconds())
    abs_seconds = abs(total_seconds)
    
    if abs_seconds < 60:
        return "just now" if total_seconds >= 0 else "a moment ago"
    
    if abs_seconds < 3600:
        minutes = abs_seconds // 60
        suffix = "ago" if total_seconds < 0 else "from now"
        return f"{minutes} minute{'s' if minutes != 1 else ''} {suffix}"
    
    if abs_seconds < 86400:
        hours = abs_seconds // 3600
        suffix = "ago" if total_seconds < 0 else "from now"
        return f"{hours} hour{'s' if hours != 1 else ''} {suffix}"
    
    if abs_seconds < 604800:
        days = abs_seconds // 86400
        suffix = "ago" if total_seconds < 0 else "from now"
        return f"{days} day{'s' if days != 1 else ''} {suffix}"
    
    if abs_seconds < 2592000:
        weeks = abs_seconds // 604800
        suffix = "ago" if total_seconds < 0 else "from now"
        return f"{weeks} week{'s' if weeks != 1 else ''} {suffix}"
    
    if abs_seconds < 31536000:
        months = abs_seconds // 2592000
        suffix = "ago" if total_seconds < 0 else "from now"
        return f"{months} month{'s' if months != 1 else ''} {suffix}"
    
    years = abs_seconds // 31536000
    suffix = "ago" if total_seconds < 0 else "from now"
    return f"{years} year{'s' if years != 1 else ''} {suffix}"


def format_days_until(*, expiry_date: date, reference: date | None = None) -> str:
    """
    Format the number of days until/since an expiry date.
    
    Args:
        expiry_date: The expiry date to compare.
        reference: Reference date for comparison. Defaults to today.
        
    Returns:
        Formatted string like "expires in 5 days" or "expired 2 days ago".
    """
    if not isinstance(expiry_date, date):
        raise TypeError(f"Expected date, got {type(expiry_date).__name__}")
    
    if reference is None:
        reference = date.today()
    
    if not isinstance(reference, date):
        raise TypeError(f"Expected date for reference, got {type(reference).__name__}")
    
    delta = expiry_date - reference
    days = delta.days
    
    if days < 0:
        return f"expired {abs(days)} day{'s' if abs(days) != 1 else ''} ago"
    
    if days == 0:
        return "expires today"
    
    if days == 1:
        return "expires tomorrow"
    
    return f"expires in {days} days"


def format_datetime_display(
    *,
    value: datetime,
    date_style: Literal["full", "short", "verbose"] = "full",
    include_time: bool = True,
    use_24h: bool = False,
) -> str:
    """
    Format a datetime for complete display with date and optional time.
    
    Args:
        value: The datetime to format.
        date_style: Display style for the date portion.
        include_time: If True, includes time in the output.
        use_24h: If True and include_time is True, uses 24-hour format.
        
    Returns:
        Formatted datetime string.
    """
    if not isinstance(value, datetime):
        raise TypeError(f"Expected datetime, got {type(value).__name__}")
    
    date_str = format_display_date(value=value.date(), style=date_style)
    
    if not include_time:
        return date_str
    
    time_str = format_time(value=value, use_24h=use_24h)
    return f"{date_str} at {time_str}"


def ensure_timezone_aware(*, value: datetime, default_tz: timezone = timezone.utc) -> datetime:
    """
    Ensure a datetime is timezone-aware. If naive, assigns the default timezone.
    
    Args:
        value: The datetime to make timezone-aware.
        default_tz: Timezone to assign if value is naive. Defaults to UTC.
        
    Returns:
        Timezone-aware datetime.
    """
    if not isinstance(value, datetime):
        raise TypeError(f"Expected datetime, got {type(value).__name__}")
    
    if value.tzinfo is not None:
        return value
    
    return value.replace(tzinfo=default_tz)


__all__ = [
    "format_iso_date",
    "format_iso_datetime",
    "format_display_date",
    "format_time",
    "format_relative_time",
    "format_days_until",
    "format_datetime_display",
    "ensure_timezone_aware",
    "ISO_DATE_FORMAT",
    "ISO_DATETIME_FORMAT",
    "ISO_DATETIME_WITH_TZ_FORMAT",
    "DISPLAY_DATE_FORMAT",
    "SHORT_DATE_FORMAT",
    "VERBOSE_DATE_FORMAT",
    "TIME_FORMAT",
    "TIME_24H_FORMAT",
]
