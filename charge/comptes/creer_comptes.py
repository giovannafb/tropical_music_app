"""Comptes de test de la campagne de charge (partie 4) : crée ou réinitialise les comptes « user »
du fichier de comptes, déjà vérifiés, chacun avec ses titres likés.

Le résultat ne dépend que du catalogue : avec le même import FMA, les deux déploiements obtiennent
les mêmes comptes et les mêmes likes, et chaque campagne repart du même état (anciens comptes de test
supprimés avec leurs likes, playlists et sessions Redis). Un compte témoin <prefixe>000, sans aucun
like, sert au test du test (charge/valider.sh).

Exécuté DANS la couche métier, lu sur l'entrée standard (voir charge/commun.sh, reinitialiser_comptes) :
    python - --nombre 100 --prefixe charge --domaine charge.invalid --mot-de-passe … --likes 20
"""
import argparse
import hashlib
import random
import sys

from sqlalchemy import delete, select

from app.core.db import get_sessionmaker
from app.core.redis_client import get_redis
from app.core.security import hash_password
from app.models import Album, Artist, Track, TrackLike, User
from app.repositories.catalog import VISIBLE
from app.services.sessions import revoke_all

GRAINE = 2026   # tirage des likes : identique d'une exécution et d'un déploiement à l'autre


def catalogue(db) -> list[tuple]:
    """Titres visibles d'un user, dans un ordre qui ne dépend pas des identifiants de la base."""
    rows = db.execute(
        select(Track.id, Artist.name, Album.title, Track.position, Track.title)
        .join(Album, Track.album_id == Album.id)
        .join(Artist, Album.artist_id == Artist.id)
        .where(VISIBLE)
    ).all()
    return sorted(rows, key=lambda r: (r[1], r[2], r[3], r[4], r[0]))


def empreinte(lignes) -> str:
    h = hashlib.sha256()
    for ligne in lignes:
        h.update("|".join(str(v) for v in ligne).encode())
        h.update(b"\n")
    return h.hexdigest()[:16]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--nombre", type=int, required=True)
    parser.add_argument("--prefixe", required=True)
    parser.add_argument("--domaine", required=True)
    parser.add_argument("--mot-de-passe", required=True)
    parser.add_argument("--likes", type=int, required=True)
    args = parser.parse_args()
    if len(args.mot_de_passe) < 8:
        sys.exit("Le mot de passe doit contenir au moins 8 caractères.")

    noms = [f"{args.prefixe}{i:03d}" for i in range(0, args.nombre + 1)]   # 000 : compte témoin sans like
    r = get_redis()
    with get_sessionmaker()() as db:
        titres = catalogue(db)
        if len(titres) < args.likes:
            sys.exit(f"Catalogue trop petit : {len(titres)} titres visibles, {args.likes} likes demandés par compte.")
        print(f"Catalogue : {len(titres)} titres visibles, empreinte {empreinte(t[1:] for t in titres)}")

        # Un nom d'utilisateur de test déjà pris par un vrai compte : on s'arrête plutôt que de le toucher
        pris = db.scalars(select(User.username).where(
            User.username.in_(noms), User.email.not_like(f"%@{args.domaine}"))).all()
        if pris:
            sys.exit(f"Noms déjà utilisés par d'autres comptes : {', '.join(pris)}")

        anciens = db.scalars(select(User.id).where(User.email.like(f"%@{args.domaine}"))).all()
        for user_id in anciens:
            revoke_all(r, user_id)
        db.execute(delete(User).where(User.email.like(f"%@{args.domaine}")))   # likes, playlists… en cascade

        password_hash = hash_password(args.mot_de_passe)   # même coût argon2 que les vrais comptes
        users = [User(username=nom, email=f"{nom}@{args.domaine}", password_hash=password_hash,
                      role="user", is_verified=True) for nom in noms]
        db.add_all(users)
        db.flush()

        tirage = random.Random(GRAINE)
        likes = []
        for user in users[1:]:
            for t in tirage.sample(titres, args.likes):
                db.add(TrackLike(user_id=user.id, track_id=t[0]))
                likes.append((user.username, *t[1:]))
        db.commit()

    print(f"Comptes : {len(anciens)} supprimés, {len(users)} créés "
          f"({noms[1]} … {noms[-1]} avec {args.likes} titres likés chacun, {noms[0]} sans like)")
    print(f"Likes : {len(likes)}, empreinte {empreinte(likes)}")


if __name__ == "__main__":
    main()
