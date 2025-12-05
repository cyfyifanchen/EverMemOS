import datetime
from zoneinfo import ZoneInfo
import os
from core.observation.logger import get_logger

logger = get_logger(__name__)


def get_timezone() -> ZoneInfo:
    """Get timezone from TZ env var (default: Asia/Shanghai)."""
    tz = os.getenv("TZ", "Asia/Shanghai")
    return ZoneInfo(tz)


timezone = get_timezone()


def get_now_with_timezone() -> datetime.datetime:
    """Get current time with local timezone."""
    return datetime.datetime.now(tz=timezone)


def to_timezone(dt: datetime.datetime, tz: ZoneInfo = None) -> datetime.datetime:
    """Convert datetime to specified timezone."""
    if tz is None:
        tz = timezone
    return dt.astimezone(tz)


def to_iso_format(
    time_value: datetime.datetime | int | float | str | None,
) -> str | None:
    """Convert time value to ISO format string with timezone.
    
    Supports: datetime, int/float (unix timestamp), str, None.
    
    Args:
        time_value: Time value to convert.
        
    Returns:
        ISO format string (e.g. 2025-09-16T20:20:06+08:00), or None.
        
    Raises:
        TypeError: If time_value is not a supported type.
        ValueError: If timestamp is invalid.
    """

    if time_value is None:
        return None

    value_type = type(time_value)
    
    if value_type is str:
        if not time_value:
            return None
        # Validate and parse ISO format string
        time_str = time_value.replace("Z", "+00:00") if time_value.endswith("Z") else time_value
        dt = datetime.datetime.fromisoformat(time_str)
    elif value_type in (int, float):
        if time_value <= 0:
            raise ValueError(f"Invalid timestamp: {time_value}. Must be positive.")
        dt = from_timestamp(time_value)
    elif value_type is datetime.datetime:
        dt = time_value
    else:
        raise TypeError(
            f"Unsupported type: {value_type.__name__}. "
            f"Expected: datetime, int, float, str, or None."
        )

    # Ensure timezone and convert to local
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone)
    return dt.astimezone(timezone).isoformat()


def from_timestamp(timestamp: int | float) -> datetime.datetime:
    """Convert unix timestamp to datetime. Auto-detects seconds vs milliseconds."""
    # >= 1e12 is milliseconds, < 1e12 is seconds
    if timestamp >= 1e12:
        timestamp_seconds = timestamp / 1000.0
    else:
        timestamp_seconds = timestamp
    return datetime.datetime.fromtimestamp(timestamp_seconds, tz=timezone)


def to_timestamp(dt: datetime.datetime) -> int:
    """Convert datetime to unix timestamp (seconds)."""
    return int(dt.timestamp())


def to_timestamp_ms(dt: datetime.datetime) -> int:
    """Convert datetime to unix timestamp (milliseconds)."""
    return int(dt.timestamp() * 1000)


def to_timestamp_ms_universal(time_value) -> int:
    """Convert any time format to milliseconds timestamp.
    
    Supports: int/float (timestamp), str (ISO format), datetime, None.
    Returns 0 on failure or None input.
    """
    try:
        if time_value is None:
            return 0

        if isinstance(time_value, (int, float)):
            # Auto-detect: >= 1e12 is ms, otherwise seconds
            if time_value >= 1e12:
                return int(time_value)
            return int(time_value * 1000)

        if isinstance(time_value, str):
            try:
                return to_timestamp_ms_universal(float(time_value))
            except ValueError:
                return to_timestamp_ms(from_iso_format(time_value))

        if isinstance(time_value, datetime.datetime):
            return to_timestamp_ms(time_value)

        return to_timestamp_ms_universal(str(time_value))

    except Exception as e:
        logger.error(
            "[DateTimeUtils] to_timestamp_ms_universal - Error converting %s: %s",
            time_value,
            str(e),
        )
        return 0


def from_iso_format(create_time, target_timezone: ZoneInfo = None) -> datetime.datetime:
    """Parse ISO format string or datetime to timezone-aware datetime.
    
    Args:
        create_time: datetime object or ISO string (supports "Z" suffix).
        target_timezone: Target timezone. Defaults to TZ env var.
        
    Returns:
        Timezone-aware datetime. Falls back to current time on error.
    """
    try:
        if isinstance(create_time, datetime.datetime):
            dt = create_time
        elif isinstance(create_time, str):
            # Handle "Z" suffix (UTC) for Python < 3.11 compatibility
            time_str = create_time.replace("Z", "+00:00") if create_time.endswith("Z") else create_time
            dt = datetime.datetime.fromisoformat(time_str)
        else:
            time_str = str(create_time)
            time_str = time_str.replace("Z", "+00:00") if time_str.endswith("Z") else time_str
            dt = datetime.datetime.fromisoformat(time_str)

        if dt.tzinfo is None:
            tz = target_timezone or get_timezone()
            dt = dt.replace(tzinfo=tz)

        return dt.astimezone(get_timezone())

    except Exception as e:
        logger.error("[DateTimeUtils] from_iso_format - Error: %s", str(e))
        return get_now_with_timezone()
