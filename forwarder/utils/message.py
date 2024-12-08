import re

from typing import Dict, List, Optional, Tuple

from forwarder import LOGGER


def predicate_text(filters: List[str], text: str) -> bool:
    """Check if the text contains any of the filters"""
    for i in filters:
        pattern = r"( |^|[^\w])" + re.escape(i) + r"( |$|[^\w])"
        if re.search(pattern, text, flags=re.IGNORECASE):
            return True

    return False

def is_order_message(message_text: str) -> bool:
    """
    Check if the message is an order message by looking for Order Reference.
    """
    order_ref_pattern = r'\[?(?:Order\s*Ref(?:erence)?(?:\s*No\.)?|Order\s*No\.):?]?'
    return bool(re.search(order_ref_pattern, message_text, re.IGNORECASE | re.MULTILINE))

def is_valid_order_format(message_text: str) -> Tuple[bool, Optional[str]]:
    """
    Validates if the message follows the required order format.
    Returns a tuple of (is_valid, error_message).
    """
    # First check if this is an order message
    if not is_order_message(message_text):
        return False, None

    # Required fields that must be present in the message
    required_fields = [
        (r'\[?(?:Order\s*Ref(?:erence)?(?:\s*No\.)?|Order\s*No\.):?]?', "Order Reference"),
        (r'\[?Currency:?]?', "Currency"),
        (r'\[?Amount:?]?', "Amount"),
        (r'\[?Pay\s*Out\s*Company[^:]*:?]?', "Pay Out Company"),
    ]
    
    # Check if all required fields are present in the message
    for pattern, field_name in required_fields:
        if not re.search(pattern, message_text, re.IGNORECASE | re.MULTILINE):
            error_msg = f"❌ *Invalid Order Format*\nMissing required field: {field_name}"
            LOGGER.info(f"Missing required field: {field_name}")
            return False, error_msg
    
    # Define all possible field labels
    field_labels = [
        r'Order\s*Ref(?:erence)?(?:\s*No\.)?|Order\s*No\.',
        r'Currency',
        r'Amount',
        r'Pay\s*Out\s*Company',
        r'Purpose',
        r'Remark',
        r'Beneficiary\s*Name',
        r'Beneficiary\s*country',
        r'Beneficiary\s*address',
        r'Bank\s*Account\s*Number',
        r'IBAN',
        r'(?:Bank\s*)?SWIFT',
        r'Bank\s*Name',
        r'Bank\s*address',
        r'Bank\s*country'
    ]
    
    # Split the message into sections based on field labels
    lines = message_text.strip().split('\n')
    current_field = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check if this line starts a new field
        is_field_label = False
        for label in field_labels:
            if re.match(rf'\[?{label}:?\]?', line, re.IGNORECASE):
                current_field = label
                is_field_label = True
                # Verify this field label line contains a colon
                if ':' not in line:
                    error_msg = (
                        "❌ *Invalid Order Format*\n"
                        f"Field label missing colon: {line}\n"
                        "Each field must be in the format 'Field: Value'"
                    )
                    LOGGER.info(f"Field label missing colon: {line}")
                    return False, error_msg
                break
                
        # If it's not a field label and we're not in any field, it's invalid
        if not is_field_label and current_field is None:
            error_msg = (
                "❌ *Invalid Order Format*\n"
                f"Found content without a field label: {line}\n"
                "Each section must start with a proper field label"
            )
            LOGGER.info(f"Content without field label: {line}")
            return False, error_msg
    
    return True, None

def clean_field_value(field: str, value: str) -> str:
    """
    Clean and standardize field values based on their type.
    
    Args:
        field: The field name (e.g., 'amount', 'iban', 'account_number')
        value: The value to clean
        
    Returns:
        Cleaned and standardized value
    """
    if not value:
        return value
        
    # Remove any square brackets that might have been left
    value = value.strip('[]')
    
    # Basic cleaning for all fields
    value = value.strip()
    
    if field == 'amount':
        # Remove any currency symbols or letters
        value = ''.join(c for c in value if c.isdigit() or c in ',.')
        # Convert European number format (123.456,78) to standard format (123456.78)
        if ',' in value and '.' not in value:
            value = value.replace(',', '.')
        elif ',' in value and '.' in value:
            # Handle cases like 1,234.56 or 1.234,56
            # Count the digits after each symbol to determine which is the decimal separator
            parts = value.replace(',', '.').split('.')
            if len(parts[-1]) == 2:  # If the last part has 2 digits, it's cents
                value = ''.join(parts[:-1]).replace('.', '') + '.' + parts[-1]
            else:  # Otherwise, just remove all separators except the last one
                value = ''.join(parts[:-1]).replace('.', '') + '.' + parts[-1]
                
    elif field in ['iban', 'account_number', 'swift_code']:
        # Remove all spaces, dashes, and special characters
        value = ''.join(c for c in value if c.isalnum())
        if field == 'swift_code':
            value = value.upper()
        elif field == 'iban':
            value = value.upper()
            
    return value

def extract_message_details(message_text: str) -> Dict[str, Optional[str]]:
    """
    Extract order details from the message with improved pattern matching
    """
    try:
        # Define all possible field labels for lookahead
        field_labels = (
            r'Order\s*Ref(?:erence)?|Currency|Amount|Pay\s*Out\s*Company|Purpose|Remark|'
            r'Beneficiary\s*Name|Beneficiary\s*country|Beneficiary\s*address|'
            r'Bank\s*Account\s*Number|IBAN|(?:Bank\s*)?SWIFT|Bank\s*Name|Bank\s*address|Bank\s*country'
        )
        
        # Create a lookahead pattern that matches until the next field or end of text
        next_field_pattern = f'(?=\\[?(?:{field_labels}):?\\]?|$)'
        
        patterns = {
            'order_ref': f'\\[?Order\\s*Ref(?:erence)?:?\\]?\\s*(.+?){next_field_pattern}',
            'currency': f'\\[?Currency:?\\]?\\s*(.+?){next_field_pattern}',
            'amount': f'\\[?Amount:?\\]?\\s*(.+?){next_field_pattern}',
            'payout_company': f'\\[?Pay\\s*Out\\s*Company[^:]*:?\\]?\\s*(.+?){next_field_pattern}',
            'purpose': f'\\[?Purpose:?\\]?\\s*(.+?){next_field_pattern}',
            'remark': f'\\[?Remark:?\\]?\\s*(.+?){next_field_pattern}',
            'beneficiary_name': f'\\[?Beneficiary\\s*Name:?\\]?\\s*(.+?){next_field_pattern}',
            'beneficiary_country': f'\\[?Beneficiary\\s*country:?\\]?\\s*(.+?){next_field_pattern}',
            'beneficiary_address': f'\\[?Beneficiary\\s*address:?\\]?\\s*(.+?){next_field_pattern}',
            'account_number': f'\\[?Bank\\s*Account\\s*Number:?\\]?\\s*(.+?){next_field_pattern}',
            'iban': f'IBAN:\\s*(.+?){next_field_pattern}',
            'swift_code': f'\\[?(?:Bank\\s*)?SWIFT:?\\]?\\s*(.+?){next_field_pattern}',
            'bank_name': f'\\[?Bank\\s*Name:?\\]?\\s*(.+?){next_field_pattern}',
            'bank_address': f'\\[?Bank\\s*address:?\\]?\\s*(.+?){next_field_pattern}',
            'bank_country': f'\\[?Bank\\s*country:?\\]?\\s*(.+?){next_field_pattern}'
        }
        
        results = {}
        for field, pattern in patterns.items():
            match = re.search(pattern, message_text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if match:
                value = match.group(1).strip()
                # Remove trailing separators and spaces
                value = re.sub(r'[:|,\s]+$', '', value)
                # Clean and standardize the value
                value = clean_field_value(field, value)
                if value:
                    results[field] = value
            else:
                results[field] = None
                
        # Log extracted details for debugging
        LOGGER.info("Extracted order details:")
        for field, value in results.items():
            LOGGER.info(f"{field}: {value}")
            
        return results
        
    except Exception as e:
        LOGGER.error(f"Failed to extract message details: {e}")
        return {
            'order_ref': None,
            'currency': None,
            'amount': None,
            'payout_company': None,
            'purpose': None,
            'remark': None,
            'beneficiary_name': None,
            'beneficiary_country': None,
            'beneficiary_address': None,
            'account_number': None,
            'iban': None,
            'swift_code': None,
            'bank_name': None,
            'bank_address': None,
            'bank_country': None
        }
