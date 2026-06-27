import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.asset import Asset, AssetStatus
from app.models.schemas import AssetCreate, ImportResult

router = APIRouter()


@router.post("/import", response_model=ImportResult)
def import_assets(assets: List[dict], db: Session = Depends(get_db)):
    imported = 0
    updated = 0
    failed = 0
    errors = []

    for raw in assets:
        try:
            data = AssetCreate(**raw)
        except Exception as e:
            failed += 1
            errors.append({"record": raw, "reason": str(e)})
            continue

        try:
            existing = (
                db.query(Asset)
                .filter(Asset.type == data.type, Asset.value == data.value)
                .first()
            )
            now = datetime.now(timezone.utc)

            if existing:
                # Merge strategy: keep first_seen, update last_seen, union tags, merge metadata
                existing.last_seen = now
                existing.tags = list(set((existing.tags or []) + data.tags))
                existing.metadata_ = {**(existing.metadata_ or {}), **data.metadata}
                # Re-appearing stale asset goes back to active
                if existing.status == AssetStatus.stale:
                    existing.status = AssetStatus.active
                updated += 1
            else:
                asset_id = data.id or str(uuid.uuid4())
                new_asset = Asset(
                    id=asset_id,
                    type=data.type,
                    value=data.value,
                    status=data.status,
                    source=data.source,
                    tags=data.tags,
                    metadata_=data.metadata,
                    first_seen=now,
                    last_seen=now,
                )
                db.add(new_asset)
                imported += 1

            db.commit()

        except Exception as e:
            db.rollback()
            failed += 1
            errors.append({"record": raw, "reason": str(e)})

    return ImportResult(imported=imported, updated=updated, failed=failed, errors=errors)
