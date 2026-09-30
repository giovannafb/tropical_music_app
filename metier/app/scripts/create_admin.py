"""Crée le compte admin et la playlist « à la une » (jamais via le site).

Usage :
    python -m app.scripts.create_admin --username admin --email admin@example.com
Le mot de passe est lu dans la variable ADMIN_PASSWORD, sinon demandé au clavier.
"""
import argparse
import getpass
import os
import sys

from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.core.security import hash_password
from app.models import FEATURED_PLAYLIST_KEY, AppSetting, Playlist, User

FEATURED_NAME = "Featured"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()

    with get_sessionmaker()() as db:
        admin = db.scalar(select(User).where(User.username == args.username))
        if admin and admin.role != "admin":
            sys.exit(f"« {args.username} » existe déjà et n'est pas admin.")
        if admin:
            print(f"Le compte admin « {admin.username} » existe déjà.")
        else:
            password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Mot de passe admin : ")
            if len(password) < 8:
                sys.exit("Le mot de passe doit contenir au moins 8 caractères.")
            admin = User(
                username=args.username, email=args.email.lower(),
                password_hash=hash_password(password), role="admin", is_verified=True,
            )
            db.add(admin)
            db.flush()
            print(f"Compte admin « {admin.username} » créé.")

        if db.get(AppSetting, FEATURED_PLAYLIST_KEY):
            print("La playlist à la une existe déjà.")
        else:
            playlist = Playlist(user_id=admin.id, name=FEATURED_NAME)
            db.add(playlist)
            db.flush()
            db.add(AppSetting(key=FEATURED_PLAYLIST_KEY, value=str(playlist.id)))
            print(f"Playlist à la une « {FEATURED_NAME} » créée (id {playlist.id}).")
        db.commit()


if __name__ == "__main__":
    main()
