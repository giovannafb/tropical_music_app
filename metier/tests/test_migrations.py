"""Vérifie que la migration Alembic (couche données) et les modèles (couche métier) décrivent le même schéma."""
import os
import subprocess
import sys
import tempfile

from sqlalchemy import create_engine, inspect

from app.models import Base

DONNEES = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "donnees"))


def test_migration_matches_models():
    with tempfile.TemporaryDirectory() as tmp:
        url = f"sqlite:///{os.path.join(tmp, 'schema.db')}"
        env = {**os.environ, "DATABASE_URL": url}
        cmd = [sys.executable, "-m", "alembic", "-c", os.path.join(DONNEES, "alembic.ini"), "upgrade", "head"]
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

        engine = create_engine(url)
        insp = inspect(engine)
        migrated = {t: {c["name"] for c in insp.get_columns(t)} for t in insp.get_table_names() if t != "alembic_version"}
        modeled = {t.name: {c.name for c in t.columns} for t in Base.metadata.sorted_tables}
        assert migrated == modeled

        # Mêmes clés étrangères
        for table in modeled:
            fks_db = {(tuple(fk["constrained_columns"]), fk["referred_table"]) for fk in insp.get_foreign_keys(table)}
            fks_model = {
                (tuple(c.name for c in fk.columns), fk.referred_table.name)
                for fk in Base.metadata.tables[table].foreign_key_constraints
            }
            assert fks_db == fks_model, table
        engine.dispose()
