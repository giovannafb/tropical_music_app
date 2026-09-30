# MusicApp — application 3 tiers

| Couche | Dossier | Contenu |
|---|---|---|
| Présentation | `client/` | SPA HTML / CSS / JS (modules ES, sans framework) + configuration **Nginx** (statiques, reverse proxy, répartition de charge, audio, covers) |
| Métier | `metier/` | API **FastAPI** (Python 3.12), worker (Elasticsearch, emails, compteurs), scripts, tests |
| Données | `donnees/` | Schéma **MySQL 8** (migrations **Alembic**), configuration utf8mb4, jeu de données FMA (`donnees/fma/`, non versionné) |

Le client n'a **aucun accès** à la base : il n'appelle que `/api/…`, et seule la couche métier parle à MySQL, Redis et Elasticsearch.

---

## Lancer l'application : deux versions

Le code (`client/`, `metier/`, `donnees/`) est commun ; seule la façon de faire tourner l'infrastructure change.

| | [`avec-docker/`](avec-docker/LISEZMOI.md) | [`sans-docker/`](sans-docker/LISEZMOI.md) |
|---|---|---|
| Principe | Toute la stack du doc dans des conteneurs | Services installés dans Ubuntu (WSL) |
| Lancement | `docker compose up -d --scale api=3` (PowerShell) | `bash sans-docker/demarrer.sh` (Ubuntu) |
| Application | http://localhost | http://localhost:8080 |
| Emails (Mailpit) | http://localhost:8025 | http://localhost:8026 |
| Elasticsearch | cluster de 3 nœuds, Kibana | 1 nœud, sans Kibana |
| Configuration | `avec-docker/.env` | `sans-docker/.env` |

- Les deux versions sont **indépendantes** : ports, configuration et données différents (base, comptes, fichiers audio).
- Il faut **arrêter l'une avant de lancer l'autre** : la mémoire ne suffit pas pour les deux.
  - Passer de Docker à sans Docker : `docker compose stop` (dans `avec-docker/`), puis `bash sans-docker/demarrer.sh`.
  - Passer de sans Docker à Docker : `bash sans-docker/arreter.sh`, puis `docker compose up -d --scale api=3`.
- Les mesures du doc qui comparent 0 et 2 répliques Elasticsearch se font avec la version Docker, la seule à avoir 3 nœuds.

---

## Tests

```
cd metier
pip install -r requirements-dev.txt
pytest
```
- 19 tests d'API (auth, rôles, artiste/admin, upload, catalogue, playlists, accueil, compteurs, streaming…). Ils tournent sans infrastructure : SQLite en mémoire, fakeredis et un faux Elasticsearch.
- `test_migrations.py` applique la migration Alembic de `donnees/` et vérifie qu'elle correspond exactement aux modèles de `metier/` (tables, colonnes, clés étrangères).
- Charge, sur une version démarrée : `locust -f tests/load/locustfile.py --host http://localhost`, ou `--host http://localhost:8080` pour la version sans Docker. Il faut les variables `LOCUST_LOGIN` et `LOCUST_PASSWORD` d'un compte user. Scénarios : rechercher, écouter, liker, ouvrir une playlist.

---

## Décisions validées (points non précisés par la doc)

- Interface entièrement en **anglais** ; police **Kaisei Tokumin**.
- Barre de lecture : le bouton ≡ ouvre un panneau (file de lecture, volume, aléatoire, répétition).
- Espace **admin** dédié : *Artists* (valider / refuser avec motif) et *Featured* (titres à la une).
- Playlists : « + » ouvre une recherche, le crayon devient « retirer », et *Add to playlist* figure dans le pop-up œil.
- Artiste : strictement le Figma (ni cœur, ni lecture, ni barre de lecture).
- *Log out* dans Profile ; liens *Sign up as artist* et *Forgot password ?* sous la carte de connexion.
- Un seul brouillon d'album, repris par *New album* ; *my albums* n'affiche que les albums publiés.
- *Edit* / *Delete* dans les pop-ups (playlist ; titre et album côté artiste), avec confirmation.
- Mot de passe de 8 caractères minimum, session de 7 jours (JWT 15 min), MP3 uniquement (50 Mo max), cover obligatoire pour un album et optionnelle pour une playlist, 10 résultats par section de recherche.

## Choix mineurs faits pendant le développement (à valider)

- Seuil d'écoute : **min(30 s, durée − 1 s)**. Les extraits FMA durent 30 s : sans ce seuil, aucune écoute du jeu de test ne serait comptée.
- Import FMA : la date de sortie reprend `album.date_released` de FMA (à défaut, la date de création de l'album, sinon le jour de l'import). Les albums FMA n'ont pas de cover : le placeholder du Figma s'affiche.
- Username : 3 à 50 caractères, sans « @ » (la connexion accepte le username **ou** l'email).
- Couleur d'erreur `#B3261E` (celle du kit Material 3 utilisé par le Figma), absente de la charte.
- Limites Nginx : recherche 10 req/s, connexion 10 req/min, renvoi d'email 3 req/min (par IP).
- Endpoints ajoutés à ceux du doc, nécessaires aux écrans : `GET /me`, `GET /artist/me/draft`, `PATCH /artist/albums/{id}` (brouillon), `GET /artist/tracks/{id}`, `GET /artist/albums/{id}`, `GET/POST/DELETE /admin/featured-playlist…`.
- Écran étroit (< 900 px) : sidebar en barre horizontale ; les colonnes Artist / Album sont masquées (visibles dans le pop-up œil).

## À savoir

- Stack Docker vérifiée le 28/09/2026 : migration appliquée (12 tables en utf8mb4), cluster Elasticsearch *green* sur 3 nœuds, index `tracks` / `albums` / `artists` créés par le worker, 3 instances d'API derrière Nginx.
- MySQL est construit depuis `donnees/Dockerfile`, pour que `musicapp.cnf` soit copié avec les bonnes permissions (monté depuis Windows, il était ignoré car modifiable par tous).
- Dans *New album*, une piste envoyée par erreur dans le brouillon ne peut pas être retirée depuis l'écran (le Figma ne prévoit que le crayon). L'API le permet (`DELETE /artist/tracks/{id}`).
- Elasticsearch tourne sans sécurité (`xpack.security.enabled=false`), en développement uniquement, à justifier dans le rapport.
