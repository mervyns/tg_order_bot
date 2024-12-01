from sqlalchemy.ext.asyncio import AsyncSession
from typing import TypeVar, Type, Optional, List, Any, Dict
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from forwarder import LOGGER
import asyncio

T = TypeVar('T')

class BaseRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, model: Type[T], **kwargs) -> T:
        try:
            instance = model(**kwargs)
            self.session.add(instance)
            await asyncio.wait_for(self.session.commit(), timeout=10.0)  # 10 second timeout
            return instance
        except asyncio.TimeoutError:
            await self.session.rollback()
            LOGGER.error(f"Timeout while creating {model.__name__}")
            raise
        except SQLAlchemyError as e:
            await self.session.rollback()
            LOGGER.error(f"Database error while creating {model.__name__}: {str(e)}")
            raise

    async def get_by_id(self, model: Type[T], id: int) -> Optional[T]:
        try:
            result = await asyncio.wait_for(
                self.session.execute(select(model).where(model.id == id)),
                timeout=5.0  # 5 second timeout
            )
            return result.scalar_one_or_none()
        except (SQLAlchemyError, asyncio.TimeoutError) as e:
            LOGGER.error(f"Error getting {model.__name__} by id {id}: {str(e)}")
            raise

    async def get_all(self, model: Type[T]) -> List[T]:
        try:
            result = await asyncio.wait_for(
                self.session.execute(select(model)),
                timeout=10.0  # 10 second timeout
            )
            return result.scalars().all()
        except (SQLAlchemyError, asyncio.TimeoutError) as e:
            LOGGER.error(f"Error getting all {model.__name__}: {str(e)}")
            raise

    async def update(self, instance: T, **kwargs) -> T:
        try:
            for key, value in kwargs.items():
                setattr(instance, key, value)
            await asyncio.wait_for(self.session.commit(), timeout=10.0)  # 10 second timeout
            return instance
        except asyncio.TimeoutError:
            await self.session.rollback()
            LOGGER.error(f"Timeout while updating {type(instance).__name__}")
            raise
        except SQLAlchemyError as e:
            await self.session.rollback()
            LOGGER.error(f"Database error while updating {type(instance).__name__}: {str(e)}")
            raise

    async def delete(self, instance: T) -> None:
        try:
            await self.session.delete(instance)
            await asyncio.wait_for(self.session.commit(), timeout=10.0)  # 10 second timeout
        except asyncio.TimeoutError:
            await self.session.rollback()
            LOGGER.error(f"Timeout while deleting {type(instance).__name__}")
            raise
        except SQLAlchemyError as e:
            await self.session.rollback()
            LOGGER.error(f"Database error while deleting {type(instance).__name__}: {str(e)}")
            raise