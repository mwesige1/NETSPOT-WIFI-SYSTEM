import re
from django.utils.text import slugify


def generate_schema_name(business_name):
    """
    Converts a business name into a valid PostgreSQL schema name.
    Rules:
    - Lowercase only
    - No special characters
    - Spaces replaced with underscores
    - Max 63 characters (PostgreSQL limit)
    
    Examples:
    'Serena Hotel Kampala' -> 'serena_hotel_kampala'
    'St. Mary's School'   -> 'st_marys_school'
    "O'Brien's Café"      -> 'obriens_cafe'
    """
    # Use Django's slugify to handle special characters and spaces
    # slugify converts to lowercase, removes special chars, replaces spaces with hyphens
    slug = slugify(business_name)
    
    # Replace hyphens with underscores (PostgreSQL convention for schema names)
    schema_name = slug.replace('-', '_')
    
    # Remove any remaining non-alphanumeric characters except underscores
    schema_name = re.sub(r'[^a-z0-9_]', '', schema_name)
    
    # Ensure it doesn't start with a number (PostgreSQL requirement)
    if schema_name and schema_name[0].isdigit():
        schema_name = f"t_{schema_name}"
    
    # Truncate to 63 characters (PostgreSQL schema name limit)
    schema_name = schema_name[:63]
    
    return schema_name


def generate_subdomain(business_name):
    """
    Converts a business name into a valid subdomain.
    Similar to schema name but uses hyphens instead of underscores
    (subdomains use hyphens conventionally).
    
    Examples:
    'Serena Hotel Kampala' -> 'serena-hotel-kampala'
    'St. Mary's School'   -> 'st-marys-school'
    """
    slug = slugify(business_name)
    
    # Remove any remaining non-alphanumeric characters except hyphens
    subdomain = re.sub(r'[^a-z0-9-]', '', slug)
    
    # Truncate to 63 characters
    subdomain = subdomain[:63]
    
    return subdomain