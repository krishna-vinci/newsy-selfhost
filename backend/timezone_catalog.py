from __future__ import annotations

import pytz

DEFAULT_TIMEZONE = "Asia/Kolkata"


def is_valid_timezone(timezone_name: str | None) -> bool:
    if not timezone_name:
        return False

    try:
        pytz.timezone(timezone_name)
        return True
    except pytz.UnknownTimeZoneError:
        return False


def normalize_timezone(
    timezone_name: str | None, fallback: str = DEFAULT_TIMEZONE
) -> str:
    return timezone_name if is_valid_timezone(timezone_name) else fallback


def build_timezone_options() -> list[dict[str, str | None]]:
    country_names = pytz.country_names
    country_timezones = pytz.country_timezones
    timezone_to_countries: dict[str, list[str]] = {}

    for country_code, tz_list in country_timezones.items():
        country_name = country_names.get(country_code, country_code)
        for tz_name in tz_list:
            timezone_to_countries.setdefault(tz_name, []).append(country_name)

    options: list[dict[str, str | None]] = []
    for tz_name in pytz.common_timezones:
        parts = tz_name.split("/")
        city = parts[-1].replace("_", " ")
        region = "/".join(parts[:-1]).replace("_", " ") if len(parts) > 1 else None
        countries = sorted(timezone_to_countries.get(tz_name, []))
        country = countries[0] if countries else None
        label_parts = [city]
        if country:
            label_parts.append(country)
        if region:
            label_parts.append(region)

        options.append(
            {
                "value": tz_name,
                "label": " • ".join(label_parts),
                "country": country,
                "region": region,
                "city": city,
            }
        )

    return options
