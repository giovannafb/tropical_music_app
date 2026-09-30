"""Reconstruit les index Elasticsearch depuis MySQL, puis bascule les alias (sans coupure).

Usage : python -m app.scripts.reindex_es
"""
from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.models import Album, Artist, Track
from app.repositories import search

BATCH = 500

SOURCES = {
    "tracks": ("track", lambda: select(Track.id).join(Album).join(Artist).where(
        Album.status == "published", Artist.status == "approved")),
    "albums": ("album", lambda: select(Album.id).join(Artist).where(
        Album.status == "published", Artist.status == "approved")),
    "artists": ("artist", lambda: select(Artist.id).where(Artist.status == "approved")),
}


def main() -> None:
    es = search.get_es()
    with get_sessionmaker()() as db:
        for alias, (entity, query) in SOURCES.items():
            new_index = search.create_index(es, alias)
            ids = list(db.scalars(query()))
            for start in range(0, len(ids), BATCH):
                operations = []
                for entity_id in ids[start:start + BATCH]:
                    operations += search.bulk_actions_for(db, entity, entity_id, "upsert", index=new_index)
                # Un document supprimé entre-temps produit un « delete » inutile dans un index neuf : on l'ignore
                search.bulk(es, [op for op in operations if "delete" not in op])
            es.indices.refresh(index=new_index)
            search.swap_alias(es, alias, new_index)
            print(f"{alias} : {len(ids)} document(s) -> {new_index}")


if __name__ == "__main__":
    main()
