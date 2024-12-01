# sanctions_service.py
import aiohttp
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import quote
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

    def generate_name_variations(self, company_name: str) -> List[str]:
        variations = []
        
        cleaned = company_name.replace("&", "and")
        cleaned = re.sub(r'[(),.]', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        base_name = re.sub(r'\b(Co|Ltd|Limited|Import|Export|Company|Foreign|Trade|Trading|COLTD|and)\b', '', cleaned, flags=re.IGNORECASE)
        base_name = re.sub(r'\s+', ' ', base_name).strip()
        
        variations.append(cleaned)
        variations.append(base_name)
        
        if '(' in company_name:
            core_name = company_name.split('(')[0].strip()
            variations.append(core_name)
        
        return list(set(variations))

    async def check_entity(self, session: aiohttp.ClientSession, beneficiary_name: str, beneficiary_address: str = "") -> Dict:
        """
        Check entity against sanctions lists with proper name and alias handling
        """
        try:
            name_data = self.generate_name_variations(beneficiary_name)
            LOGGER.info(f"Checking name: {name_data['name']} with aliases: {name_data['alias_names']}")
            
            # Construct query parameters
            query_params = {
                "names": quote(name_data['name']),
                "address": quote(beneficiary_address) if beneficiary_address else ""
            }
            
            # Build query string
            query_string = "&".join(f"{k}={v}" for k, v in query_params.items() if v)
            
            headers = {"x-api-key": self.api_key}
            
            async with session.get(
                f"{self.api_base_url}/checkEntity?{query_string}",
                headers=headers
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # Add the name variations we used for reference
                    result["name_variations"] = name_data
                    return result
                    
            return {"total_hits": 0, "found_records": [], "name_variations": name_data}
            
        except Exception as e:
            LOGGER.error(f"Failed to check entity: {e}")
            return {}

    def format_sanction_message(self, beneficiary_name: str, sanction_result: Dict) -> str:
        sanction_hits = sanction_result.get("total_hits", 0)
        found_records = sanction_result.get("found_records", [])
        matched_variation = sanction_result.get("matched_variation", "")
        scanned_variations = sanction_result.get("name_variations", "")
        LOGGER.info(f"something {sanction_hits} {found_records}")
        if sanction_hits > 0 and found_records:
            found_record = found_records[0]
            found_name = found_record.get("name", "Unknown")
            source_type = found_record.get("source_type", "Unknown")
            sanction_details = found_record.get("sanction_details", [])
            address = found_record.get("address", [])
            
            address_str = ", ".join(address) if address else "No address available"
            sanctions_str = "\n• ".join(sanction_details) if sanction_details else "No details available"
            variation_info = f"\nMatched Variation: `{matched_variation}`" if matched_variation else ""
            
            return (
                "🚫 *SANCTIONS CHECK FAILED*\n\n"
                f"Company: `{beneficiary_name}`{variation_info}\n"
                f"Matched Entity: `{found_name}`\n"
                f"Source Type: `{source_type}`\n"
                f"Address: `{address_str}`\n\n"
                f"Sanction Details:\n• {sanctions_str}\n\n"
                "Status: ❌ SANCTIONED\n\n"
                "⚠️ This transaction cannot proceed due to sanctions."
            )
        else:
            variations_list = "\n• ".join([f"`{var}`" for var in scanned_variations])
        return (
            "✅ *SANCTIONS CHECK PASSED*\n\n"
            f"*Name Variations Checked*:\n"
            f"• {variations_list}\n"
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