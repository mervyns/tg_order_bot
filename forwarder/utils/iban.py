# iban_validator.py
import re
from typing import Tuple
from forwarder import LOGGER

class IBANValidator:
    # Countries where IBAN is mandatory
    IBAN_MANDATORY_COUNTRIES = {
        'ALBANIA', 'ANDORRA', 'AUSTRIA', 'AZERBAIJAN', 'BAHRAIN', 'BELGIUM', 'BOSNIA AND HERZEGOVINA',
        'BULGARIA', 'CROATIA', 'CYPRUS', 'CZECH REPUBLIC', 'DENMARK', 'ESTONIA', 'FAROE ISLANDS',
        'FINLAND', 'FRANCE', 'GEORGIA', 'GERMANY', 'GIBRALTAR', 'GREECE', 'GREENLAND', 'HUNGARY',
        'ICELAND', 'IRELAND', 'ISRAEL', 'ITALY', 'JORDAN', 'KAZAKHSTAN', 'KUWAIT', 'LATVIA',
        'LEBANON', 'LIECHTENSTEIN', 'LITHUANIA', 'LUXEMBOURG', 'MALTA', 'MAURITANIA', 'MAURITIUS',
        'MONACO', 'MONTENEGRO', 'NETHERLANDS', 'NORTH MACEDONIA', 'NORWAY', 'PAKISTAN', 'PALESTINE',
        'POLAND', 'PORTUGAL', 'QATAR', 'ROMANIA', 'SAINT LUCIA', 'SAN MARINO', 'SAUDI ARABIA',
        'SERBIA', 'SEYCHELLES', 'SLOVAKIA', 'SLOVENIA', 'SPAIN', 'SWEDEN', 'SWITZERLAND', 'TIMOR-LESTE',
        'TURKEY', 'UKRAINE', 'UNITED ARAB EMIRATES', 'UNITED KINGDOM', 'VATICAN CITY STATE'
    }

    # IBAN length by country
    IBAN_LENGTHS = {
        'AL': 28, 'AD': 24, 'AT': 20, 'AZ': 28, 'BH': 22, 'BE': 16, 'BA': 20, 'BG': 22,
        'HR': 21, 'CY': 28, 'CZ': 24, 'DK': 18, 'EE': 20, 'FO': 18, 'FI': 18, 'FR': 27,
        'GE': 22, 'DE': 22, 'GI': 23, 'GR': 27, 'GL': 18, 'HU': 28, 'IS': 26, 'IE': 22,
        'IL': 23, 'IT': 27, 'JO': 30, 'KZ': 20, 'KW': 30, 'LV': 21, 'LB': 28, 'LI': 21,
        'LT': 20, 'LU': 20, 'MT': 31, 'MR': 27, 'MU': 30, 'MC': 27, 'ME': 22, 'NL': 18,
        'MK': 19, 'NO': 15, 'PK': 24, 'PS': 29, 'PL': 28, 'PT': 25, 'QA': 29, 'RO': 24,
        'LC': 32, 'SM': 27, 'SA': 24, 'RS': 22, 'SC': 31, 'SK': 24, 'SI': 19, 'ES': 24,
        'SE': 24, 'CH': 21, 'TL': 23, 'TR': 26, 'UA': 29, 'AE': 23, 'GB': 22, 'VA': 22
    }

    @staticmethod
    def requires_iban(country: str) -> bool:
        """Check if a country requires IBAN"""
        return country.upper() in IBANValidator.IBAN_MANDATORY_COUNTRIES

    @staticmethod
    def clean_iban(iban: str) -> str:
        """Remove spaces and convert to uppercase"""
        return ''.join(iban.split()).upper()

    @staticmethod
    def validate_iban(iban: str) -> Tuple[bool, str]:
        """
        Validate IBAN number
        Returns: (is_valid, error_message)
        """
        try:
            if not iban:
                return False, "IBAN is empty"

            # Clean the IBAN
            iban = IBANValidator.clean_iban(iban)
            
            # Basic format check
            if not re.match(r'^[A-Z]{2}[0-9A-Z]{2,}$', iban):
                return False, "IBAN format is invalid (must start with country code)"

            # Get country code and check length
            country_code = iban[:2]
            if country_code not in IBANValidator.IBAN_LENGTHS:
                return False, f"Unknown country code: {country_code}"

            expected_length = IBANValidator.IBAN_LENGTHS[country_code]
            if len(iban) != expected_length:
                return False, f"IBAN length incorrect. Expected {expected_length} characters, got {len(iban)}"

            # Move first 4 characters to end and convert letters to numbers
            iban = iban[4:] + iban[:4]
            iban_numeric = ''
            for ch in iban:
                if ch.isdigit():
                    iban_numeric += ch
                else:
                    iban_numeric += str(ord(ch) - ord('A') + 10)

            # Calculate checksum using mod-97
            remainder = int(iban_numeric) % 97
            if remainder != 1:
                return False, "IBAN checksum is invalid"

            return True, "IBAN is valid"

        except Exception as e:
            LOGGER.error(f"IBAN validation error: {str(e)}")
            return False, f"IBAN validation error: {str(e)}"