import re
import uuid


def generate_router_identity(business_name, location):
    """
    Builds a URL-safe router identity from business name + location.
    e.g. "Hotel Kampala" + "Reception" -> "hotel-kampala-reception"
    Appends a short random suffix if needed to avoid collisions.
    """
    base = f"{business_name}-{location}".lower().strip()
    base = re.sub(r'[^a-z0-9\s-]', '', base)   # strip anything not alphanumeric/space/hyphen
    base = re.sub(r'\s+', '-', base)            # spaces -> hyphens
    base = re.sub(r'-+', '-', base).strip('-')  # collapse multiple hyphens

    return base