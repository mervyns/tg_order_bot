from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime
from forwarder import LOGGER

class GoogleSheetsManager:
    def __init__(self, service_account_file: str, spreadsheet_id: str):
        self.SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        # Convert to Path object and resolve path
        service_account_path = Path(service_account_file)
        if not service_account_path.is_absolute():
            # If path is relative, assume it's relative to config directory
            config_dir = Path(__file__).parent.parent / "config"
            service_account_path = config_dir / service_account_path

        if not service_account_path.exists():
            raise FileNotFoundError(f"Service account file not found: {service_account_path}")

        self.SERVICE_ACCOUNT_FILE = str(service_account_path)
        self.SPREADSHEET_ID = spreadsheet_id

    def authenticate(self):
        creds = service_account.Credentials.from_service_account_file(
            self.SERVICE_ACCOUNT_FILE, scopes=self.SCOPES)
        return build('sheets', 'v4', credentials=creds)

    def format_range(self, sheet_name: str, column: str) -> str:
        """Format range string to handle spaces in sheet names"""
        # Enclose sheet names with spaces in single quotes
        if ' ' in sheet_name:
            return f"'{sheet_name}'!{column}:{column}"
        return f"{sheet_name}!{column}:{column}"

    def setup_headers(self):
        """Initialize the sheet with headers"""
        service = self.authenticate()
        
        headers = [[
            'Timestamp', 'Payout Company', 'Order Ref', 'Amount', 'Currency',
            'Beneficiary Name', 'Beneficiary Address', 'Beneficiary Country',
            'Account Number', 'SWIFT Code', 'Bank Name', 'Bank Address', 'Bank Country',
            'Purpose', 'Remark', 'SWIFT Verification Status'
        ]]
        
        try:
            # Update headers
            body = {'values': headers}
            service.spreadsheets().values().update(
                spreadsheetId=self.SPREADSHEET_ID,
                range='Sheet1!A1:P1',
                valueInputOption='RAW',
                body=body
            ).execute()
            
            # Format headers
            requests = [{
                'repeatCell': {
                    'range': {'sheetId': 0, 'startRowIndex': 0, 'endRowIndex': 1},
                    'cell': {
                        'userEnteredFormat': {
                            'backgroundColor': {'red': 0.8, 'green': 0.8, 'blue': 0.8},
                            'textFormat': {'bold': True}
                        }
                    },
                    'fields': 'userEnteredFormat(backgroundColor,textFormat)'
                }
            }, {
                'updateSheetProperties': {
                    'properties': {
                        'sheetId': 0,
                        'gridProperties': {'frozenRowCount': 1}
                    },
                    'fields': 'gridProperties.frozenRowCount'
                }
            }]
            
            service.spreadsheets().batchUpdate(
                spreadsheetId=self.SPREADSHEET_ID,
                body={'requests': requests}
            ).execute()
            
            LOGGER.info("Successfully set up sheet headers")
            return True
            
        except Exception as e:
            LOGGER.error(f"Failed to set up sheet headers: {e}")
            return False

    async def add_order_details(self, details: dict):
        """Add order details to the sheet"""
        service = self.authenticate()

        amount = details.get('amount', '')
        if isinstance(amount, str) and amount:
            try:
                # Remove commas and convert to float
                amount = float(amount.replace(',', ''))
            except ValueError:
                LOGGER.warning(f"Could not convert amount to number: {amount}")
        account_number = details.get('iban') or details.get('account_number')
        LOGGER.info(f"service {service}")
        # Prepare row data
        row = [[
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            details.get('payout_company', ''),
            details.get('order_ref', ''),
            amount,
            details.get('currency', ''),
            details.get('beneficiary_name', ''),
            details.get('beneficiary_address', ''),
            details.get('beneficiary_country', ''),
            account_number,
            details.get('swift_code', ''),
            details.get('bank_name', ''),
            details.get('bank_address', ''),
            details.get('bank_country', ''),
            details.get('purpose', ''),
            details.get('remark', '')
        ]]
        
        body = {'values': row}
        
        try:
            result = service.spreadsheets().values().append(
                spreadsheetId=self.SPREADSHEET_ID,
                range='Orders!A:P',
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            LOGGER.info(f"Added order details to sheet: {result.get('updates').get('updatedRows')} rows updated")
            return True
        except Exception as e:
            LOGGER.error(f"Failed to add order details to sheet: {e}")
            return False
        
    async def update_value_by_match(self, search_column: str, search_value: str, target_column: str, new_value: str, sheet_name: str = 'Sheet1') -> bool:
        """
        Find a value in a specific column and update the cell next to it.
        
        Args:
            search_column: Column letter to search in (e.g., 'A', 'B', etc.)
            search_value: Value to find in the search column
            target_column: Column letter where to write the new value
            new_value: Value to write in the target column
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            service = self.authenticate()
            search_range = self.format_range(sheet_name, search_column)
            
            # Get all values from the sheet
            result = service.spreadsheets().values().get(
                spreadsheetId=self.SPREADSHEET_ID,
                range=search_range
            ).execute()
            
            values = result.get('values', [])
            
            # Find the row number where the value exists
            row_number = None
            for i, row in enumerate(values, start=1):  # start=1 because sheet rows start at 1
                if row and row[0].strip() == search_value.strip():
                    row_number = i
                    break
            
            if row_number is None:
                LOGGER.warning(f"Value '{search_value}' not found in column {search_column}")
                return False
            
            # Update the cell in the target column
            range_name = f'{sheet_name}!{target_column}{row_number}'
            body = {
                'values': [[new_value]]
            }
            
            service.spreadsheets().values().update(
                spreadsheetId=self.SPREADSHEET_ID,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            
            LOGGER.info(f"Successfully updated value in {range_name}")
            return True
            
        except Exception as e:
            LOGGER.error(f"Failed to update value: {e}")
            return False