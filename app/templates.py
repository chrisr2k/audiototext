"""Shared Jinja2 templates instance with custom filters."""
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")


def format_timestamp(value):
    """Convert OCI timestamp (e.g. '143.400') to mm:ss format."""
    try:
        seconds = float(value)
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"
    except (ValueError, TypeError):
        return value


templates.env.filters["format_timestamp"] = format_timestamp
