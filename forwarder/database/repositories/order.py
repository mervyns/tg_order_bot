from typing import Optional, List, Dict
from sqlalchemy import select
from ..models import Order
from .base import BaseRepository
from forwarder.utils.number import parse_float

class OrderRepository(BaseRepository):
    async def create_order(self, details: Dict[str, str], validation_messages: str) -> Order:
        # Get payout company with default empty string
        payout_company = details.get('payout_company', '')
        
        # Calculate rate based on payout company
        rate = 0.994 if payout_company and "CELES" in payout_company.upper() else 0.995
        
        return await self.create(
            Order,
            order_ref=details['order_ref'],
            swift_code=details['swift_code'],
            bank_name=details['bank_name'],
            bank_country=details.get('bank_country'),
            account_number=details['account_number'] or details['iban'],
            beneficiary_name=details['beneficiary_name'],
            currency=details['currency'],
            amount=parse_float(details['amount']),
            agent_code="HD",
            client_code="VR",
            payout_company=payout_company,
            rate=rate,
            validation_messages=validation_messages
        )

    async def get_order_by_ref(self, order_ref: str) -> Optional[Order]:
        result = await self.session.execute(
            select(Order).where(Order.order_ref == order_ref)
        )
        return result.scalar_one_or_none()

    async def get_pending_orders(self) -> List[Order]:
        result = await self.session.execute(
            select(Order).where(Order.status == 'pending')
        )
        return result.scalars().all()

    async def update_order_status(self, order_ref: str, status: str) -> bool:
        order = await self.get_order_by_ref(order_ref)
        if order:
            await self.update(order, status=status)
            return True
        return False