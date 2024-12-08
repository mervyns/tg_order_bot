# sanctions_service.py
import aiohttp
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import quote_plus
from forwarder import LOGGER

@dataclass
class SanctionsValidationResult:
    is_valid: bool
    status: str
    message: str
    details: Optional[Dict] = None

class SanctionsService:
    def __init__(self, api_key: str, api_base_url: str):
        self.api_key = api_key
        self.api_base_url = api_base_url

    def extract_core_name(self, company_name: str) -> str:
        """
        Extract the core entity name by removing common business terms and suffixes.
        """
        LOGGER.info(f"Extracting core name from: {company_name}")
        
        # Common terms to remove (business suffixes and descriptors)
        removable_terms = [
            # Company suffixes
            r'\bCO\.,?\s*LTD\b',
            r'\bCO\.,?\s*LIMITED\b',
            r'\bCORPORATION\b',
            r'\bCORP\b',
            r'\bINC\b',
            r'\bLLC\b',
            r'\bLTD\b',
            r'\bLIMITED\b',
            r'\bPTE\b',
            r'\bPVT\b',
            r'\bGMBH\b',
            # Business descriptors
            r'\bIMPORT\b',
            r'\bEXPORT\b',
            r'\bCOMPANY\b',
            r'\bFOREIGN\b',
            r'\bTECHNOLOGY\b',
            r'\bTRADE\b',
            r'\bTRADING\b',
            r'\bGROUP\b',
            r'\bHOLDINGS?\b',
            r'\bINDUSTRIES?\b',
            r'\bINTERNATIONAL\b',
            r'\bENTERPRISES?\b',
            r'\bSIRKETI?\b', #Turkish for Company
            # Common industry terms
            r'\bMANUFACTURING\b',
            r'\bPRODUCTS?\b',
            r'\bSOLUTIONS?\b',
            r'\bSERVICES?\b',
            r'\bSYSTEMS?\b'
            r'\bTICARET?\b', #Turkish for Trade
        ]
        
        # Initial cleaning
        cleaned = company_name.replace("&", "and")
        
        # Remove parenthetical content
        cleaned = re.sub(r'\([^)]*\)', '', cleaned)
        
        # Remove all the terms
        for term in removable_terms:
            cleaned = re.sub(term, '', cleaned, flags=re.IGNORECASE)
        
        # Remove remaining punctuation except spaces
        cleaned = re.sub(r'[^\w\s]', '', cleaned)
        
        # Clean up extra spaces and standardize
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        LOGGER.info(f"Extracted core name: {cleaned}")
        return cleaned

    async def check_entity(self, session: aiohttp.ClientSession, beneficiary_name: str, beneficiary_address: str = "") -> Dict:
        """
        Check entity against sanctions lists using core name
        """
        try:
            core_name = self.extract_core_name(beneficiary_name)
            LOGGER.info(f"Checking core name: {core_name}")
            
            # Construct query parameters
            query_params = {
                "names": quote_plus(core_name),
                "address": quote_plus(beneficiary_address) if beneficiary_address else ""
            }
            
            # Build query string
            query_string = "&".join(f"{k}={v}" for k, v in query_params.items() if v)
            
            headers = {"x-api-key": self.api_key}
            url = f"{self.api_base_url}/checkEntity?{query_string}"

            LOGGER.info(f"Full URL (without API key): {url}")
            
            async with session.get(
                url,
                headers=headers
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    result["core_name"] = core_name
                    result["original_name"] = beneficiary_name
                    return result
                    
            return {
                "total_hits": 0,
                "found_records": [],
                "core_name": core_name,
                "original_name": beneficiary_name
            }
            
        except Exception as e:
            LOGGER.error(f"Failed to check entity: {e}")
            return {}

    def format_sanction_message(self, beneficiary_name: str, sanction_result: Dict) -> str:
        sanction_hits = sanction_result.get("total_hits", 0)
        found_records = sanction_result.get("found_records", [])
        core_name = sanction_result.get("core_name", "")
        
        if sanction_hits > 0 and found_records:
            found_record = found_records[0]
            found_name = found_record.get("name", "Unknown")
            source_type = found_record.get("source_type", "Unknown")
            sanction_details = found_record.get("sanction_details", [])
            address = found_record.get("address", [])
            
            address_str = ", ".join(address) if address else "No address available"
            sanctions_str = "\n• ".join(sanction_details) if sanction_details else "No details available"
            
            return (
                "🚫 *SANCTIONS CHECK FAILED*\n\n"
                f"Original Name: `{beneficiary_name}`\n"
                f"Core Entity Name: `{core_name}`\n"
                f"Matched Entity: `{found_name}`\n"
                f"Source Type: `{source_type}`\n"
                f"Address: `{address_str}`\n\n"
                f"Sanction Details:\n• {sanctions_str}\n\n"
                "Status: ❌ SANCTIONED\n\n"
                "⚠️ This transaction cannot proceed due to sanctions."
            )
        
        return (
            "✅ *SANCTIONS CHECK PASSED*\n\n"
            f"Original Name: `{beneficiary_name}`\n"
            f"Core Entity Name: `{core_name}`\n"
            "Status: ✅ NO SANCTIONS FOUND"
        )

    async def validate_entity(self, details: Dict[str, str]) -> SanctionsValidationResult:
        """
        Main validation method that handles the entire sanctions check process
        """
        try:
            beneficiary_name = details.get('beneficiary_name')
            if not beneficiary_name:
                return SanctionsValidationResult(
                    is_valid=False,
                    status="failed",
                    message="❌ *Sanctions Check*: Missing beneficiary name",
                    details=None
                )

            async with aiohttp.ClientSession() as session:
                sanctions_result = await self.check_entity(session, beneficiary_name)
                formatted_message = self.format_sanction_message(beneficiary_name, sanctions_result)
                
                is_sanctioned = sanctions_result.get("total_hits", 0) > 0
                
                return SanctionsValidationResult(
                    is_valid=not is_sanctioned,
                    status="passed" if not is_sanctioned else "failed",
                    message=formatted_message,
                    details=sanctions_result
                )

        except Exception as e:
            LOGGER.error(f"Sanctions validation error: {e}")
            return SanctionsValidationResult(
                is_valid=False,
                status="error",
                message=f"❌ *Sanctions Check Error*: {str(e)}",
                details=None
            )