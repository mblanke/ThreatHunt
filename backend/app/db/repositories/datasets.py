"""Dataset repository — CRUD operations for datasets and their rows."""

import logging
from typing import Sequence

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Dataset, DatasetRow

logger = logging.getLogger(__name__)


class DatasetRepository:
    """Typed CRUD for Dataset and DatasetRow models."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Dataset CRUD ──────────────────────────────────────────────────

    async def create_dataset(self, **kwargs) -> Dataset:
        ds = Dataset(**kwargs)
        self.session.add(ds)
        await self.session.flush()
        return ds

    async def get_dataset(self, dataset_id: str) -> Dataset | None:
        result = await self.session.execute(
            select(Dataset).where(Dataset.id == dataset_id)
        )
        return result.scalar_one_or_none()

    async def list_datasets(
        self,
        hunt_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Dataset]:
        stmt = select(Dataset).order_by(Dataset.created_at.desc())
        if hunt_id:
            stmt = stmt.where(Dataset.hunt_id == hunt_id)
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_datasets(self, hunt_id: str | None = None) -> int:
        stmt = select(func.count(Dataset.id))
        if hunt_id:
            stmt = stmt.where(Dataset.hunt_id == hunt_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def delete_dataset(self, dataset_id: str) -> bool:
        ds = await self.get_dataset(dataset_id)
        if not ds:
            return False
        await self.session.delete(ds)
        await self.session.flush()
        return True

    # ── Row CRUD ──────────────────────────────────────────────────────

    async def bulk_insert_rows(
        self,
        dataset_id: str,
        rows: list[dict],
        normalized_rows: list[dict] | None = None,
        batch_size: int = 500,
    ) -> int:
        """Insert rows in batches. Returns count inserted."""
        count = 0
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            norm_batch = normalized_rows[i : i + batch_size] if normalized_rows else [None] * len(batch)
            objects = [
                DatasetRow(
                    dataset_id=dataset_id,
                    row_index=i + j,
                    data=row,
                    normalized_data=norm,
                )
                for j, (row, norm) in enumerate(zip(batch, norm_batch))
            ]
            self.session.add_all(objects)
            await self.session.flush()
            count += len(objects)
        return count

    async def get_rows(
        self,
        dataset_id: str,
        limit: int = 1000,
        offset: int = 0,
    ) -> Sequence[DatasetRow]:
        stmt = (
            select(DatasetRow)
            .where(DatasetRow.dataset_id == dataset_id)
            .order_by(DatasetRow.row_index)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_rows(self, dataset_id: str) -> int:
        stmt = select(func.count(DatasetRow.id)).where(
            DatasetRow.dataset_id == dataset_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_row_by_index(
        self, dataset_id: str, row_index: int
    ) -> DatasetRow | None:
        stmt = select(DatasetRow).where(
            DatasetRow.dataset_id == dataset_id,
            DatasetRow.row_index == row_index,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_rows(self, dataset_id: str) -> int:
        result = await self.session.execute(
            delete(DatasetRow).where(DatasetRow.dataset_id == dataset_id)
        )
        return result.rowcount  # type: ignore[return-value]
