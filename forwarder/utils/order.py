from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import aiohttp
from telegram import Update
from telegram.ext import ContextTypes

from typing import Dict, List, Optional
from forwarder import LOGGER, OUTPUT_SETTINGS
from forwarder.database.manager import DatabaseManager
from forwarder.database.repositories.order import OrderRepository
from forwarder.utils.iban import IBANValidator
from forwarder.utils.message import extract_message_details, is_valid_order_format
from forwarder.utils.sanctions_service import SanctionsService
from forwarder.utils.sheets_manager import GoogleSheetsManager
from forwarder.utils.swift import Swift

@dataclass
class ValidationResult:
    is_valid: bool
    message: str

@dataclass
class ProcessingResult:
    passed: List[str]
    failed: List[str]
    warnings: List[str]
    swift_message: Optional[str] = None
    bank_country: Optional[str] = None

class OrderProcessor:
    def __init__(
        self,
        sheets_managers: Dict[str, GoogleSheetsManager],
        swift_verifier: Swift,
        order_topic_id: int,
        db_manager: DatabaseManager,  # This should be an initialized instance, not a coroutine
        validation_rules: Dict[str, bool] = None,
        sanctions_config: Optional[Dict[str, str]] = None
    ):
        self.sheets_managers = sheets_managers
        self.swift_verifier = swift_verifier
        self.order_topic_id = order_topic_id
        self.db_manager = db_manager
        self.validation_rules = validation_rules or {
            'check_swift': True,
            'check_iban': True,
            'check_sanctions': False
        }
        self.validation_results = ProcessingResult([], [], [])

        self.sanctions_service = None
        if self.validation_rules.get('check_sanctions') and sanctions_config:
            self.sanctions_service = SanctionsService(
                api_key=sanctions_config.get('api_key'),
                api_base_url=sanctions_config.get('api_base_url')
            )

    @classmethod
    async def create(
        cls,
        sheets_managers: Dict[str, GoogleSheetsManager],
        swift_verifier: Swift,
        order_topic_id: int,
        db_url: str,
        validation_rules: Dict[str, bool] = None,
        sanctions_config: Optional[Dict[str, str]] = None
    ) -> 'OrderProcessor':
        """Factory method to create OrderProcessor with initialized DatabaseManager"""
        # Initialize the database manager
        db_manager = await DatabaseManager.initialize(database_url=db_url)
        return cls(
            sheets_managers=sheets_managers,
            swift_verifier=swift_verifier,
            order_topic_id=order_topic_id,
            db_manager=db_manager,
            validation_rules=validation_rules,
            sanctions_config=sanctions_config
        )

    async def process_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Main entry point for order processing"""
        message = update.effective_message
        if not self._is_valid_message(message):
            return False

        # Check topic ID
        if not await self._validate_topic(message.message_thread_id):
            return False
            
        # Check order format
        is_valid, error_message = is_valid_order_format(message.text)
        if not is_valid:
            if error_message and OUTPUT_SETTINGS.enable_verification_messages:
                await context.bot.send_message(
                    chat_id=OUTPUT_SETTINGS.verification_chat_id,
                    message_thread_id=OUTPUT_SETTINGS.verification_topic_id,
                    text=error_message,
                    parse_mode='Markdown'
                )
            return False

        # Extract and validate details
        details = extract_message_details(message.text)

        # Initialize overall validation status
        validation_passed = True

        # Validate required fields
        if not await self._validate_required_fields(details):
            validation_passed = False

        # Validate SWIFT and IBAN if required
        if self.validation_rules.get('check_swift', True) or self.validation_rules.get('require_iban', True):
            if not await self._validate_bank_details(details):
                validation_passed = False

        # Sanctions check if enabled
        if self.validation_rules.get('check_sanctions', False):
            sanctions_result = await self.sanctions_service.validate_entity(details)
            LOGGER.info(f"sanctions result {sanctions_result}")
            if sanctions_result.is_valid:
                self.validation_results.passed.append(sanctions_result.message)
            else:
                self.validation_results.failed.append(sanctions_result.message)
                validation_passed = False

        # If any validation failed, send validation message and return
        if not validation_passed:
            await self._send_validation_message(context)
            return False

        if validation_passed:
            async with self.db_manager.get_session() as session:
                order_repo = OrderRepository(session)
                try:
                    validation_messages = self._format_validation_message()
                    await order_repo.create_order(details, validation_messages)  # Make sure create_order is async
                    self.validation_results.passed.append("✅ *Database*: Order saved successfully")
                except Exception as e:
                    LOGGER.error(f"Database error: {str(e)}")
                    self.validation_results.warnings.append("⚠️ *Database*: Failed to save order")
                    validation_passed = False

        # Process sheets only if all validations passed
        if not await self._process_sheets(details):
            await self._send_validation_message(context)
            return False

        await self._send_success_message(context, details)
        return True

    def _is_valid_message(self, message) -> bool:
        """Check if message is valid"""
        return bool(message and message.text)

    async def _validate_topic(self, topic_id: int) -> bool:
        """Validate message topic"""
        if topic_id != self.order_topic_id:
            LOGGER.info(f"Ignoring message from topic {topic_id} - not our target topic {self.order_topic_id}")
            return False
        return True

    def _validate_order_format(self, text: str) -> bool:
        """Validate order format"""
        if not is_valid_order_format(text):
            return False
        return True

    async def _validate_required_fields(self, details: Dict[str, str]) -> bool:
        """Validate required fields"""
        # Basic required fields
        required_fields = {
            'SWIFT Code': details['swift_code'],
            'Bank Name': details['bank_name'],
            'Order Reference': details['order_ref'],
            'Currency': details['currency'],
            'Amount': details['amount'],
            'Beneficiary Name': details['beneficiary_name']
        }

        # Check if either IBAN or Account Number is provided
        has_account_info = bool(details.get('iban') or details.get('account_number'))
        if not has_account_info:
            self.validation_results.failed.append("❌ *Account Information*: Either IBAN or Account Number is required")

        is_valid = True
        # Validate basic required fields
        for field, value in required_fields.items():
            if not value:
                self.validation_results.failed.append(f"❌ *{field}*: Missing")
                is_valid = False

        # Account information validation is part of the overall validation
        return is_valid and has_account_info

    async def _validate_bank_details(self, details: Dict[str, str]) -> bool:
        """Validate SWIFT and IBAN"""
        async with aiohttp.ClientSession() as session:
            # Get account details
            iban = details.get('iban')
            account_number = details.get('account_number')
            
            # Perform SWIFT verification
            swift_valid, swift_message, swift_country = await self.swift_verifier.verify_swift_and_iban(
                session, details['swift_code'], details['bank_name'], iban or account_number
            )
            
            # Store SWIFT results
            self.validation_results.bank_country = swift_country
            LOGGER.info(f"swift_valid, {swift_valid}")

            # Record SWIFT verification result as warning if failed, or pass if successful
            if swift_valid:
                self.validation_results.passed.append("✅ *SWIFT Verification*: Valid")
            else:
                self.validation_results.warnings.append(f"⚠️ *SWIFT Verification Warning*:\n{swift_message}")

            # Determine country for IBAN validation (use bank_country from message if SWIFT fails)
            effective_country = swift_country or details.get('bank_country')
            LOGGER.info(f"effective country, {effective_country}")
            LOGGER.info(f"validation_rules, {self.validation_rules}")

            # Check if IBAN validation is needed (either provided or required by country)
            needs_iban_validation = (
                iban is not None or 
                (self.validation_rules.get('check_iban') and 
                effective_country and 
                IBANValidator.requires_iban(effective_country))
            )

            if needs_iban_validation:
                if not iban:  # IBAN is required but not provided
                    self.validation_results.failed.append(
                        f"❌ *IBAN Required*:\n"
                        f"• Country {effective_country} requires IBAN\n"
                        f"• Please provide a valid IBAN"
                    )
                    return False
                
                # Validate the IBAN
                iban_valid, iban_message = IBANValidator.validate_iban(iban)
                if iban_valid:
                    self.validation_results.passed.append("✅ *IBAN Verification*: Valid")
                else:
                    self.validation_results.failed.append(f"❌ *IBAN Verification*: {iban_message}")
                    return False

            return True

    async def _process_sheets(self, details: Dict[str, str]) -> bool:
        """Process spreadsheet operations"""
        try:
            internal_manager = self.sheets_managers['internal']
            hd_vr_manager = self.sheets_managers['hd_vr']
            hd_pay_manager = self.sheets_managers['hd_pay']
            
            # Calculate rate
            payout_company = details.get('payout_company', '').upper()
            rate = "0.994" if "CELES" in payout_company else "0.995"

            # Update internal sheet
            if not await internal_manager.add_order_details(details):
                LOGGER.info(f"fdetails {details}")
                self.validation_results.warnings.append("⚠️ *Database*: Failed to save order details")
            else:
                self.validation_results.passed.append("✅ *Database*: Order details saved")

            # Update VR sheet
            await self._update_vr_sheet(hd_vr_manager, details, rate)

            await self._update_hd_pay_sheet(hd_pay_manager, details)

            return True
        except Exception as e:
            self.validation_results.warnings.append(f"⚠️ *Sheet Processing*: {str(e)}")
            return False

    async def _update_vr_sheet(
        self,
        manager: GoogleSheetsManager,
        details: Dict[str, str],
        rate: str
    ):
        """Update VR sheet with order details"""
        updates = [
            ('D', details['amount']),
            ('E', details['currency']),
            ('I', rate)
        ]
        
        for column, value in updates:
            await manager.update_value_by_match(
                search_column='C',
                search_value=details['order_ref'],
                target_column=column,
                new_value=value,
                sheet_name='Dec Orders'
            )

    async def _update_hd_pay_sheet(
        self,
        manager: GoogleSheetsManager,
        details: Dict[str, str]
    ):
        """Update HD Pay sheet based on payout company"""
        payout_company = details.get('payout_company', '').upper()
        order_ref = details.get('order_ref', '')
        amount = details.get('amount', '')
        currency = details.get('currency', '')
        
        # Convert CNY to CNH if needed
        if currency == 'CNY':
            currency = 'CNH'
        
        try:
            service = manager.authenticate()
            
            if "CELES" in payout_company:
                sheet_name = 'Thai Tony Orders'
                sheet_range = f"'{sheet_name}'!C:C"  # Get all values in column C
            elif "EUR" in payout_company or "SENIBO" in payout_company:
                sheet_name = 'Water Orders'
                sheet_range = f"'{sheet_name}'!C:C"  # Get all values in column C
            else:
                # No matching sheet for this payout company
                return

            # Get all values in column C to find the last row
            result = service.spreadsheets().values().get(
                spreadsheetId=manager.SPREADSHEET_ID,
                range=sheet_range
            ).execute()
            
            values = result.get('values', [])
            next_row = len(values) + 1  # Add 1 to get the next empty row
            
            # Prepare row data based on sheet type
            if "CELES" in payout_company:
                update_range = f"'{sheet_name}'!C{next_row}:F{next_row}"
                row = [[
                    order_ref,  # Column C
                    "Order Sent", # Column D
                    amount,    # Column E
                    currency   # Column F
                ]]
            else:  # EUR or SENIBO
                update_range = f"'{sheet_name}'!C{next_row}:G{next_row}"
                row = [[
                    order_ref,     # Column C
                    "Order Sent",  # Column D
                    amount,        # Column E
                    currency,      # Column F
                    payout_company # Column G
                ]]
            
            # Update the specific row with values
            body = {'values': row}
            result = service.spreadsheets().values().update(
                spreadsheetId=manager.SPREADSHEET_ID,
                range=update_range,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            
            LOGGER.info(f"Updated HD Pay sheet {sheet_name} at row {next_row}")
            
        except Exception as e:
            LOGGER.error(f"Failed to update HD Pay sheet: {e}")

    async def _send_validation_message(self, context: ContextTypes.DEFAULT_TYPE):
        """Send validation message"""
        message = self._format_validation_message()
        await self._send_message(context, message)

    async def _send_format_error_message(self, context: ContextTypes.DEFAULT_TYPE):
        """Send format error message"""
        message = (
            "❌ *Invalid Order Format*\n\n"
            "Please ensure:\n"
            "• Order reference is present\n"
            "• Currency is specified\n"
            "• Amount is specified\n"
            "• Each field is on a new line\n"
            "• Each line contains a colon (:)"
        )
        await self._send_message(context, message)

    async def _send_success_message(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        details: Dict[str, str]
    ):
        """Send success message"""
        rate = "0.994" if "CELES" in details.get('payout_company', '').upper() else "0.995"
        message = self._format_success_message(details, rate)
        await self._send_message(context, message)

    def _format_validation_message(self) -> str:
        """Format validation message"""
        message = ["🚫 *VALIDATION CHECKS FAILED*\n"]
        
        if self.validation_results.failed:
            message.append(f"*Failed Checks ({len(self.validation_results.failed)})*:")
            message.extend(self.validation_results.failed)

        if self.validation_results.warnings:
            message.append(f"\n*Warnings({len(self.validation_results.warnings)})*:")
            message.extend(self.validation_results.warnings)
            
        if self.validation_results.passed:
            message.append(f"\n*Passed Checks ({len(self.validation_results.passed)})*:")
            message.extend(self.validation_results.passed)
            
        return "\n".join(message)

    def _format_success_message(self, details: Dict[str, str], rate: str) -> str:
        """Format success message"""
        return (
            "✅ *ALL VALIDATIONS PASSED*\n\n"
            f"*Order Details*:\n"
            f"• Reference: `{details['order_ref']}`\n"
            f"• Amount: {details['amount']} {details['currency']}\n"
            f"*Beneficiary Details*:\n"
            f"*Beneficiary Name*: `{details['beneficiary_name']}`\n"
            # f"{self.validation_results.swift_message}\n\n"
            f"*Validation Summary*:\n"
            f"{chr(10).join(self.validation_results.passed)}"
            + (f"\n\n*Warnings*:\n{chr(10).join(self.validation_results.warnings)}"
               if self.validation_results.warnings else "")
        )

    async def _send_message(self, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Send message through Telegram"""
        if not OUTPUT_SETTINGS.enable_verification_messages:
            return
            
        if OUTPUT_SETTINGS.verification_chat_id:
            try:
                await context.bot.send_message(
                    chat_id=OUTPUT_SETTINGS.verification_chat_id,
                    text=text,
                    message_thread_id=OUTPUT_SETTINGS.verification_topic_id,
                    parse_mode='Markdown'
                )
            except Exception as err:
                LOGGER.error(f"Failed to send verification message: {err}")