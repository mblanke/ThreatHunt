from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/api/routes/datasets.py')
t=p.read_text(encoding='utf-8')
if 'from app.services.scanner import keyword_scan_cache' not in t:
    t=t.replace('from app.services.host_inventory import inventory_cache','from app.services.host_inventory import inventory_cache\nfrom app.services.scanner import keyword_scan_cache')
old='''@router.delete(
    "/{dataset_id}",
    summary="Delete a dataset",
)
async def delete_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
):
    repo = DatasetRepository(db)
    deleted = await repo.delete_dataset(dataset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return {"message": "Dataset deleted", "id": dataset_id}
'''
new='''@router.delete(
    "/{dataset_id}",
    summary="Delete a dataset",
)
async def delete_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
):
    repo = DatasetRepository(db)
    deleted = await repo.delete_dataset(dataset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Dataset not found")
    keyword_scan_cache.invalidate_dataset(dataset_id)
    return {"message": "Dataset deleted", "id": dataset_id}
'''
if old not in t:
    raise SystemExit('delete block not found')
t=t.replace(old,new)
p.write_text(t,encoding='utf-8')
print('updated datasets.py')
