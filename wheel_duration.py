import re
from typing import Optional

TIME_REGEX = re.compile(
    r'(?:(\d+(?:\.\d+)?)\s*(?:d|days?)\s*)?'
    r'(?:(\d+(?:\.\d+)?)\s*(?:h|hrs?|hours?)\s*)?'
    r'(?:(\d+(?:\.\d+)?)\s*(?:m|mins?|minutes?)\s*)?'
    r'(?:(\d+(?:\.\d+)?)\s*(?:s|secs?|seconds?)\s*)?',
    re.IGNORECASE
)

def parse_duration(time_str: str) -> Optional[int]:
    if not time_str:
        return None
    cleaned = time_str.strip().lower()
    single_match = re.match(r'^(\d+(?:\.\d+)?)\s*([a-z]+)$', cleaned)
    if single_match:
        val = float(single_match.group(1))
        unit = single_match.group(2)
        if unit in ("d", "day", "days"):
            return int(val * 86400)
        elif unit in ("h", "hr", "hrs", "hour", "hours"):
            return int(val * 3600)
        elif unit in ("m", "min", "mins", "minute", "minutes"):
            return int(val * 60)
        elif unit in ("s", "sec", "secs", "second", "seconds"):
            return int(val)
        return None

    match = TIME_REGEX.fullmatch(cleaned)
    if not match:
        return None

    days, hours, minutes, seconds = match.groups()
    total_seconds = 0.0
    if days:
        total_seconds += float(days) * 86400
    if hours:
        total_seconds += float(hours) * 3600
    if minutes:
        total_seconds += float(minutes) * 60
    if seconds:
        total_seconds += float(seconds)

    total_int = int(total_seconds)
    return total_int if total_int > 0 else None

def format_duration(seconds: int) -> str:
    parts = []
    days = seconds // 86400
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
        seconds %= 86400

    hours = seconds // 3600
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        seconds %= 3600

    minutes = seconds // 60
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        seconds %= 60

    if seconds or not parts:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

    return " ".join(parts)
