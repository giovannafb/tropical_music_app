"""Table outbox : écrite dans la même transaction que la modification MySQL.
Le worker la lit et propage les changements vers Elasticsearch."""
from sqlalchemy.orm import Session

from app.models import SearchOutbox


def add(db: Session, entity: str, entity_id: int, action: str = "upsert") -> None:
    db.add(SearchOutbox(entity=entity, entity_id=entity_id, action=action))


def add_many(db: Session, entity: str, ids, action: str = "upsert") -> None:
    for entity_id in ids:
        add(db, entity, entity_id, action)
