import re


def normalize_space(value: str) -> str:
    return " ".join(value.split())


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower())
    return cleaned.strip("-")


def truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)] + "…"


def initials(name: str) -> str:
    return "".join(part[0].upper() for part in name.split() if part)


def word_count(value: str) -> int:
    return len(value.split())


def is_palindrome(value: str) -> bool:
    normalized = "".join(char.lower() for char in value if char.isalnum())
    return normalized == normalized[::-1]


def common_prefix(values: list[str]) -> str:
    if not values:
        return ""
    prefix = values[0]
    for value in values[1:]:
        while prefix and not value.startswith(prefix):
            prefix = prefix[:-1]
    return prefix


def mask_email(value: str) -> str:
    local, domain = value.split("@", 1)
    visible = local[:1]
    return f"{visible}{'*' * max(1, len(local) - 1)}@{domain}"


def wrap_words(words: list[str], width: int) -> list[list[str]]:
    return [words[index : index + width] for index in range(0, len(words), width)]


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise ValueError(f"Unsupported boolean: {value}")
