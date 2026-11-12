"""Mission phase timing, independent of the surface simulation."""

from datetime import timezone


def calculate_transit(launch_date, landing_date):
    """Return UTC phase dates and elapsed flight time for aware datetimes."""
    if any(value.tzinfo is None or value.utcoffset() is None
           for value in (launch_date, landing_date)):
        raise ValueError("Даты миссии должны содержать часовой пояс")
    launch_date = launch_date.astimezone(timezone.utc)
    landing_date = landing_date.astimezone(timezone.utc)
    if landing_date <= launch_date:
        raise ValueError("landing_date должна быть позже launch_date")
    transit_hours = (landing_date - launch_date).total_seconds() / 3600
    return {
        "launch_date": launch_date.isoformat().replace("+00:00", "Z"),
        "landing_date": landing_date.isoformat().replace("+00:00", "Z"),
        "transit_hours": transit_hours,
    }
