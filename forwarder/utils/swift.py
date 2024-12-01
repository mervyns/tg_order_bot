import string
import aiohttp
from typing import Optional, Tuple
from forwarder import LOGGER

class Swift:
    def __init__(self, api_key: str, api_url: str):
        self.api_key = api_key
        self.api_url = api_url

    @staticmethod
    def clean_text(text: str) -> str:
        """Remove punctuation, extra spaces, and convert to uppercase"""
        # Remove all punctuation
        text = text.translate(str.maketrans('', '', string.punctuation))

        # Convert to uppercase and split into words
        words = text.upper().split()

        # Remove company designations
        company_designations = {'CO', 'LTD', 'COLTD'}
        words = [word for word in words if word not in company_designations]
        
        # Join words back together
        return ' '.join(words)

    @staticmethod
    def get_country_from_swift(swift_code: str) -> Optional[str]:
        """Extract country code from SWIFT code"""
        if not swift_code or len(swift_code) < 6:
            return None
        return swift_code[4:6].upper()

    async def verify_swift_and_iban(
        self,
        session: aiohttp.ClientSession,
        swift_code: str,
        bank_name: Optional[str],
        account_number: Optional[str]
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Verify SWIFT code, bank name, and IBAN if applicable.
        Returns: (is_valid, message, country_name)
        """
        try:
            headers = {
                "Accept": "application/json",
                "X-Api-Key": self.api_key
            }
            
            # Clean the SWIFT code
            cleaned_swift = self.clean_text(swift_code)
            
            async with session.get(
                f"{self.api_url}/{cleaned_swift}",
                headers=headers
            ) as response:
                if response.status != 200:
                    return False, f"❌ Invalid SWIFT code: {swift_code}", None
                    
                response_data = await response.json()
                
                if not response_data.get('success'):
                    return False, f"❌ Invalid SWIFT code: {swift_code}", None
                
                # Extract data from the response structure
                swift_data = response_data['data']
                bank_data = swift_data['bank']
                country_data = swift_data['country']
                
                # Extract relevant information
                swift_bank_name = bank_data['name']
                branch_name = swift_data.get('branch_name', '')
                api_address = swift_data.get('address', 'N/A')
                api_country = country_data['name']
                
                # Check if provided bank name contains the SWIFT bank name
                if bank_name:
                    # Clean and normalize both names for comparison
                    normalized_swift_name = self.clean_text(swift_bank_name)
                    normalized_bank_name = self.clean_text(bank_name)
                    
                    # Log the cleaned names for debugging
                    LOGGER.info(f"Normalized SWIFT name: {normalized_swift_name}")
                    LOGGER.info(f"Normalized bank name: {normalized_bank_name}")
                    
                    # Check if SWIFT bank name is a substring of the provided name
                    if (normalized_swift_name not in normalized_bank_name and 
                        normalized_bank_name not in normalized_swift_name):
                        return False, (
                            f"❌ Bank name mismatch!\n\n"
                            f"PROVIDED BANK NAME:\n{bank_name}\n"
                            f"(Normalized: {normalized_bank_name})\n\n"
                            f"SWIFT BANK NAME:\n{swift_bank_name}\n"
                            f"(Normalized: {normalized_swift_name})\n\n"
                            f"SWIFT Bank Branch: {branch_name}\n"
                            f"\nNote: The SWIFT bank name should be part of the provided bank name."
                        ), api_country
                
                return True, (
                    f"Order Bank Name: {bank_name}\n"
                    f"Swift Bank Name: {swift_bank_name}\n"
                    f"Branch: {branch_name}\n"
                    f"Address: {api_address}\n"
                ), api_country
                
        except Exception as e:
            LOGGER.error(f"Failed to verify SWIFT code: {str(e)}")
            return False, f"❌ SWIFT verification failed: {str(e)}", None