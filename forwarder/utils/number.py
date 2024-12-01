"""Number formatting utilities."""

def parse_float(value: str) -> float:
    """Parse a string to float, handling common number formats."""
    if not value:
        raise ValueError("Empty value")
        
    # Remove any whitespace
    value = value.strip()
    
    # Remove any currency symbols or other common prefixes/suffixes
    value = value.replace('$', '').replace('€', '').replace('£', '')
    value = value.replace(' ', '')
    
    # Replace comma as thousand separator
    if ',' in value and '.' in value:
        # Handles case like "1,234.56"
        value = value.replace(',', '')
    elif ',' in value and '.' not in value:
        # Handles case like "1,234" or European format "1,23"
        if value.count(',') == 1 and len(value.split(',')[1]) <= 2:
            # Likely European format using comma as decimal
            value = value.replace(',', '.')
        else:
            # Likely using comma as thousand separator
            value = value.replace(',', '')
            
    try:
        return float(value)
    except ValueError as e:
        raise ValueError(f"Could not parse number: {value}") from e
