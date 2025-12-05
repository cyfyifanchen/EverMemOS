import datetime
from zoneinfo import ZoneInfo
import os
from core.observation.logger import get_logger

logger = get_logger(__name__)


def get_timezone() -> ZoneInfo:
    """
    获取时区
    """
    tz = os.getenv("TZ", "Asia/Shanghai")
    return ZoneInfo(tz)


timezone = get_timezone()


def get_now_with_timezone() -> datetime.datetime:
    """
    获取当前时间，使用本地时区
    return datetime.datetime(2025, 9, 16, 20, 17, 41, tzinfo=zoneinfo.ZoneInfo(key='Asia/Shanghai'))
    """
    return datetime.datetime.now(tz=timezone)


def to_timezone(dt: datetime.datetime, tz: ZoneInfo = None) -> datetime.datetime:
    """
    将datetime对象转换为指定时区
    """
    if tz is None:
        tz = timezone
    return dt.astimezone(tz)


def to_iso_format(dt: datetime.datetime) -> str:
    """
    将datetime对象转换为ISO格式字符串（带时区）
    return 2025-09-16T20:20:06.517301+08:00
    """
    if dt.tzinfo is None:
        # 如果没有，因为默认用的是TZ环境变量，所以需要手动设置时区
        dt = dt.replace(tzinfo=timezone)
    # 如果是utc之类的，转成本地时区
    return dt.astimezone(timezone).isoformat()


def from_timestamp(timestamp: int | float) -> datetime.datetime:
    """
    从时间戳转换为datetime对象，自动识别秒级和毫秒级精度

    Args:
        timestamp: 时间戳，支持秒级（10位数字）和毫秒级（13位数字）

    Returns:
        datetime.datetime(2025, 9, 16, 20, 17, 41, tzinfo=zoneinfo.ZoneInfo(key='Asia/Shanghai'))
    """
    # 自动识别时间戳精度
    # 毫秒级时间戳通常 >= 1e12 (1000000000000)，约13位数字
    # 秒级时间戳通常 < 1e12，约10位数字
    if timestamp >= 1e12:
        # 毫秒级时间戳，转换为秒级
        timestamp_seconds = timestamp / 1000.0
    else:
        # 秒级时间戳，直接使用
        timestamp_seconds = timestamp

    return datetime.datetime.fromtimestamp(timestamp_seconds, tz=timezone)


def to_timestamp(dt: datetime.datetime) -> int:
    """
    将datetime对象转换为时间戳，秒单位
    return 1758025061
    """
    return int(dt.timestamp())


def to_timestamp_ms(dt: datetime.datetime) -> int:
    """
    将datetime对象转换为毫秒级时间戳
    return 1758025061123
    """
    return int(dt.timestamp() * 1000)


def to_timestamp_ms_universal(time_value) -> int:
    """
    通用时间格式转毫秒级时间戳函数
    支持多种输入格式：
    - int/float: 时间戳（自动识别秒级或毫秒级）
    - str: ISO格式时间字符串
    - datetime对象
    - None: 返回0

    Args:
        time_value: 各种格式的时间值

    Returns:
        int: 毫秒级时间戳，失败时返回0
    """
    try:
        if time_value is None:
            return 0

        # 处理数字类型（时间戳）
        if isinstance(time_value, (int, float)):
            # 自动识别时间戳精度
            if time_value >= 1e12:
                # 毫秒级时间戳，直接返回
                return int(time_value)
            else:
                # 秒级时间戳，转换为毫秒级
                return int(time_value * 1000)

        # 处理字符串类型
        if isinstance(time_value, str):
            # 先尝试作为数字解析
            try:
                numeric_value = float(time_value)
                return to_timestamp_ms_universal(numeric_value)
            except ValueError:
                # 不是数字，尝试作为ISO格式时间字符串解析
                dt = from_iso_format(time_value)
                return to_timestamp_ms(dt)

        # 处理datetime对象
        if isinstance(time_value, datetime.datetime):
            return to_timestamp_ms(time_value)

        # 其他类型，尝试转换为字符串再解析
        return to_timestamp_ms_universal(str(time_value))

    except Exception as e:
        logger.error(
            "[DateTimeUtils] to_timestamp_ms_universal - Error converting time value %s: %s",
            time_value,
            str(e),
        )
        return 0


def _parse_datetime_core(time_value, target_timezone: ZoneInfo = None) -> datetime.datetime:
    """
    Core datetime parsing logic. Raises exception on failure.
    
    Supported inputs:
        - datetime object (passed through)
        - ISO format string: "2025-09-15T13:11:15.588000", "2025-09-15T13:11:15.588000Z"
        - Space-separated string: "2025-01-07 09:15:33" (Python 3.11+)
        - With timezone offset: "2025-09-15T13:11:15+08:00"
    
    Args:
        time_value: datetime object or time string
        target_timezone: Timezone for naive datetime (default: TZ env variable)
    
    Returns:
        Timezone-aware datetime object
    
    Raises:
        ValueError: If parsing fails
    """
    # Handle datetime object
    if isinstance(time_value, datetime.datetime):
        dt = time_value
    elif isinstance(time_value, str):
        time_str = time_value.strip()
        # Handle "Z" suffix (UTC)
        if time_str.endswith("Z"):
            time_str = time_str[:-1] + "+00:00"
        # Python 3.11+ fromisoformat supports space-separated format
        dt = datetime.datetime.fromisoformat(time_str)
    else:
        # Other types: convert to string first
        time_str = str(time_value).strip()
        if time_str.endswith("Z"):
            time_str = time_str[:-1] + "+00:00"
        dt = datetime.datetime.fromisoformat(time_str)
    
    # Add timezone if naive
    if dt.tzinfo is None:
        tz = target_timezone or get_timezone()
        dt_localized = dt.replace(tzinfo=tz)
    else:
        dt_localized = dt
    
    # Convert to system timezone
    return dt_localized.astimezone(get_timezone())


def from_iso_format(
    create_time,
    target_timezone: ZoneInfo = None,
    strict: bool = False,
) -> datetime.datetime:
    """
    Parse datetime string or object to timezone-aware datetime.
    
    Args:
        create_time: datetime object or time string
        target_timezone: Timezone for naive datetime (default: TZ env variable)
        strict: If True, raises ValueError on failure (for data import).
                If False (default), returns current time on failure (for runtime conversion).
    
    Supported formats:
        - datetime object (passed through)
        - "2025-01-07 09:15:33" (space-separated)
        - "2025-01-07T09:15:33" (ISO T-separated)
        - "2025-01-07 09:15:33.123456" (with microseconds)
        - "2025-01-07T09:15:33+08:00" (with timezone)
        - "2025-01-07T09:15:33Z" (UTC)

    Returns:
        Timezone-aware datetime object. Returns current time if parsing fails (when strict=False).
    
    Raises:
        ValueError: If strict=True and parsing fails
    
    Example:
        >>> from_iso_format("2025-01-07 09:15:33")
        datetime.datetime(2025, 1, 7, 9, 15, 33, tzinfo=ZoneInfo('Asia/Shanghai'))
        
        >>> from_iso_format("invalid", strict=True)
        ValueError: ...
    """
    if strict:
        # Strict mode: raise exception on failure
        return _parse_datetime_core(create_time, target_timezone)
    else:
        # Lenient mode: return current time on failure
        try:
            return _parse_datetime_core(create_time, target_timezone)
        except Exception as e:
            logger.error(
                "[DateTimeUtils] from_iso_format - Error converting time: %s", str(e)
            )
            return get_now_with_timezone()


