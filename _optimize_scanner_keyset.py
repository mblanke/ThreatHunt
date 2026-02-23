from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/services/scanner.py')
t=p.read_text(encoding='utf-8')
start=t.index('    async def _scan_datasets(')
end=t.index('    async def _scan_hunts', start)
new_func='''    async def _scan_datasets(
        self, patterns: dict, result: ScanResult, dataset_ids: list[str] | None
    ) -> None:
        """Scan dataset rows in batches using keyset pagination (no OFFSET)."""
        ds_q = select(Dataset.id, Dataset.name)
        if dataset_ids:
            ds_q = ds_q.where(Dataset.id.in_(dataset_ids))
        ds_result = await self.db.execute(ds_q)
        ds_map = {r[0]: r[1] for r in ds_result.fetchall()}

        if not ds_map:
            return

        import asyncio

        for ds_id, ds_name in ds_map.items():
            last_id = 0
            while True:
                rows_result = await self.db.execute(
                    select(DatasetRow)
                    .where(DatasetRow.dataset_id == ds_id)
                    .where(DatasetRow.id > last_id)
                    .order_by(DatasetRow.id)
                    .limit(BATCH_SIZE)
                )
                rows = rows_result.scalars().all()
                if not rows:
                    break

                for row in rows:
                    result.rows_scanned += 1
                    data = row.data or {}
                    for col_name, cell_value in data.items():
                        if cell_value is None:
                            continue
                        text = str(cell_value)
                        self._match_text(
                            text,
                            patterns,
                            "dataset_row",
                            row.id,
                            col_name,
                            result.hits,
                            row_index=row.row_index,
                            dataset_name=ds_name,
                        )

                last_id = rows[-1].id
                await asyncio.sleep(0)
                if len(rows) < BATCH_SIZE:
                    break

'''
out=t[:start]+new_func+t[end:]
p.write_text(out,encoding='utf-8')
print('optimized scanner _scan_datasets to keyset pagination')
