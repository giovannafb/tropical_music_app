# MusicApp — Mise en place de l'application 3 tiers

Point de départ : le prototype Figma **MusicApp** (écrans User, Artiste, connexion/inscription, barre de lecture).
Ce document liste **quoi utiliser** et **comment faire**. Il ne fixe pas d'ordre de réalisation.

---

## 1. Périmètre fonctionnel (prototype + décisions)

### Rôles
| Rôle | Création du compte | Accès |
|---|---|---|
| **User** | Inscription publique + vérification email | Accueil, Likes, Albums, Search, Playlist, Profile, lecteur |
| **Artist** | Page d'inscription **distincte** (username, email, mot de passe, **nom d'artiste**, **bio**) + vérification email + **validation par l'admin** | Uniquement **sa propre musique** : my tracks, my albums, New album (upload), Profile (username, mot de passe, bio). N'écoute pas / ne like pas la musique des autres |
| **Admin** | Créé par script uniquement, jamais via le site | Valider / refuser les artistes, gérer la playlist « à la une » |

### Fonctions côté User
- **Accueil** : titres « à la une » = contenu d'une playlist précise gérée par le compte admin.
- **Likes** : titres likés (cœur sur chaque ligne).
- **Albums** : albums **likés** (un bouton like doit exister sur le pop-up album).
- **Search** : recherche Elasticsearch, résultats groupés *Songs / Album / Artists*.
- **Playlist** : liste des playlists (nombre de titres, durée totale), création avec cover + nom + ajout de titres.
- **Profile** : changer username, changer mot de passe (ancien / nouveau / confirmation).
- **Icône œil** : pop-up détail du titre (titre, artiste, album, durée, date de sortie, écoutes, likes).
- **Pop-ups** : artiste (nom + bio), album, playlist.
- **Barre de lecture** présente sur tous les écrans.

### Fonctions côté Artist
- Créer un album : cover, titre, upload de plusieurs pistes, renommage des pistes (crayon), bouton **Upload** = publication.
- Consulter ses titres et ses albums.
- **Pas de genre** dans l'application.
- **Date de sortie** = date de publication de l'album (clic sur Upload), pas de champ à saisir.

---

## 2. Architecture

```
┌──────────────────────────────┐
│  PRÉSENTATION                │  HTML / CSS / JavaScript (SPA)
└──────────────┬───────────────┘
               │ HTTPS : REST/JSON + flux audio
┌──────────────▼───────────────┐
│  NGINX                       │  fichiers statiques, reverse proxy,
│                              │  répartition de charge, envoi des fichiers audio
└──────┬───────────────┬───────┘
┌──────▼─────┐  ┌──────▼─────┐
│ API Python │  │ API Python │  … N instances sans état
└──┬───┬───┬─┘  └──┬───┬───┬─┘
   │   │   └───────┼───┼───┴──► Redis (cache, compteurs, limitation de débit)
   │   └───────────┼───┴──────► Cluster Elasticsearch (3 nœuds)
   └───────────────┴──────────► MySQL (source de vérité)
                                + stockage fichiers (audio, covers) : disque ou MinIO
Worker Python (indexation ES, envoi d'emails, flush des compteurs)
```

Règles de base :
- **MySQL est la source de vérité**, Elasticsearch n'est qu'une copie pour la recherche.
- **Les fichiers audio ne sont jamais stockés dans MySQL**, seulement leur chemin.
- **L'API ne garde aucun état en mémoire** (JWT, cache dans Redis), sinon impossible de la dupliquer.

---

## 3. Outils

| Besoin | Outil |
|---|---|
| Client | HTML5, CSS3 (Flexbox/Grid), JavaScript modules ES, `<audio>`, `<dialog>` |
| Serveur web / répartiteur | **Nginx** |
| API | **Python 3.12+**, **FastAPI**, `uvicorn` + `gunicorn` |
| Validation des données | Pydantic (inclus avec FastAPI) |
| Accès MySQL | **SQLAlchemy 2** + **Alembic** (migrations), pilote `asyncmy` ou `PyMySQL` |
| Base de données | **MySQL 8** (`utf8mb4`) |
| Recherche | **Elasticsearch 8** + client Python `elasticsearch` |
| Cache / compteurs | **Redis** + `redis` (Python) |
| Mots de passe | `argon2-cffi` |
| Tokens | `pyjwt` |
| Upload | `python-multipart` |
| Métadonnées audio | `mutagen` (durée, format) |
| Images | `Pillow` (redimensionner les covers) |
| Emails | `aiosmtplib` ou `fastapi-mail` ; **Mailpit** en développement |
| Stockage fichiers | volume disque ou **MinIO** (compatible S3) |
| Conteneurs | **Docker Desktop + WSL2**, `docker compose` |
| Tests de charge | **Locust** |
| Supervision | **Kibana** (livré avec ES) ; optionnel : Prometheus + Grafana |
| Tests | `pytest` + `httpx` |
| Données de test | **FMA dataset** (`fma_small`) : musique libre de droits + métadonnées |

---

## 4. Couche présentation (HTML / CSS / JS)

### Single Page Application
- Une seule page `index.html`. Les vues sont injectées par JavaScript, **sinon la musique s'arrête à chaque changement de page**.
- Routage par hash : `#/home`, `#/likes`, `#/albums`, `#/search`, `#/playlists`, `#/profile`, `#/artist/tracks`, `#/artist/albums`, `#/artist/new-album`, `#/admin/artists`…
- Deux « coques » distinctes selon le rôle : sidebar User et sidebar Artist, comme dans le prototype.

### Organisation des fichiers
```
frontend/
  index.html
  css/        variables.css (couleurs du Figma), layout.css, components.css
  js/
    api.js        → fetch centralisé (base URL, gestion 401/403, JSON)
    router.js     → routage par hash, garde selon le rôle
    player.js     → lecteur audio et file de lecture
    auth.js
    views/        → une vue par écran Figma
    components/   → trackRow.js, albumRow.js, dialog.js, emptyState.js
```

### Lecteur (barre de lecture)
- Un **seul** élément `<audio>` global, créé une fois, jamais détruit.
- File de lecture **liée au contexte** : lancer un titre depuis une playlist, un album ou l'accueil met toute la liste dans la file, et « suivant »/« précédent » suivent cette liste.
- Contrôles : lecture/pause, suivant/précédent, barre de progression (`currentTime`/`duration`), volume, aléatoire, répétition.
- **Media Session API** (`navigator.mediaSession`) pour les touches multimédia du clavier et l'écran de verrouillage.
- Compter une écoute : après **30 s** de lecture, appeler `POST /tracks/{id}/play` une seule fois par lecture.

### Pop-ups
- Élément natif **`<dialog>`** + `showModal()` : fond grisé, fermeture avec Échap, accessibilité.
- Chaque pop-up **modifie l'URL** (`#/album/12`, `#/artist/4`, `#/playlist/7`, `#/track/33`). Le bouton « retour » ferme le pop-up, et un lien vers un album peut être partagé.

### Recherche
- **Debounce de 300 ms** sur la saisie avant d'appeler l'API.
- Annuler la requête précédente avec `AbortController` quand l'utilisateur tape encore.

### Upload (côté artiste)
- `fetch()` ne donne pas la progression d'un envoi : utiliser **`XMLHttpRequest`** + `xhr.upload.onprogress` pour la barre de progression.
- Envoyer **une piste par requête**, pas tout l'album d'un coup.

### Règles d'affichage
- Écrans Figma dessinés en 1920×1080 : reprendre les proportions en CSS **responsive** (Grid/Flex, unités relatives, media queries), sinon l'affichage casse sur un portable.
- **Jamais `innerHTML` avec des données venant de l'API** : utiliser `textContent` ou `createElement` (protection XSS).
- Prévoir pour chaque liste : état **chargement**, état **vide** (« No track found »), état **erreur**.
- Unifier les libellés du prototype (« my tracks » / « Mes titres ») et renommer le bouton d'inscription « Sign up ».

---

## 5. Couche métier (Python / FastAPI)

### Organisation
```
backend/app/
  main.py
  core/          config (variables d'environnement), sécurité (JWT, argon2), dépendances
  routers/       auth.py, tracks.py, albums.py, playlists.py, search.py,
                 me.py, artist.py, admin.py, stream.py
  services/      logique métier (publier un album, valider un artiste…)
  repositories/  requêtes MySQL / Elasticsearch
  models/        modèles SQLAlchemy
  schemas/       schémas Pydantic (entrées / sorties)
  workers/       indexation ES, envoi d'emails, flush des compteurs
  scripts/       create_admin.py, seed_fma.py, reindex_es.py
```

### Authentification
- Mots de passe hachés avec **argon2**. **Le mot de passe actuel ne peut jamais être affiché** : le champ « Password + œil » du profil doit disparaître. L'œil ne sert qu'à révéler ce qu'on est **en train de taper**.
- Connexion par **username ou email**.
- JWT court (≈15 min) + refresh token. Stockage recommandé : **cookie `HttpOnly`, `Secure`, `SameSite=Strict`** (l'API et le site sont servis par le même Nginx, donc même origine).
- Codes d'erreur explicites, que le client utilise pour rediriger vers le bon écran :
  - `EMAIL_NOT_VERIFIED` → écran « Account not verified »
  - `ARTIST_PENDING` → écran « compte en attente de validation »
  - `ARTIST_REJECTED` → message avec le motif du refus

### Contrôle des rôles
- Dépendance FastAPI `require_role("user" | "artist" | "admin")` sur **chaque** route.
- Un artiste n'accède qu'à **ses** albums et titres : chaque requête artiste filtre par `artist_id` lié au compte connecté.
- Un artiste n'a **pas** accès aux routes User (likes, playlists, recherche, catalogue).

### Endpoints

**Authentification**
```
POST /auth/register                 inscription user
POST /auth/register-artist          inscription artiste (+ nom d'artiste, bio)
POST /auth/login
POST /auth/logout
POST /auth/refresh
GET  /auth/verify?token=…
POST /auth/resend-verification
POST /auth/forgot-password
POST /auth/reset-password
```

**User**
```
GET    /home                         titres de la playlist à la une
GET    /tracks/{id}                  détail (pop-up œil)
PUT    /tracks/{id}/like   DELETE /tracks/{id}/like
GET    /me/likes/tracks
PUT    /albums/{id}/like   DELETE /albums/{id}/like
GET    /me/likes/albums               onglet Albums
GET    /albums/{id}                   pop-up album
GET    /artists/{id}                  pop-up artiste (nom, bio, albums)
GET    /search?q=…                    Songs / Albums / Artists
GET    /me/playlists
POST   /playlists                     multipart : nom + cover
GET    /playlists/{id}
PATCH  /playlists/{id}   DELETE /playlists/{id}
POST   /playlists/{id}/tracks   DELETE /playlists/{id}/tracks/{track_id}
POST   /tracks/{id}/play              compteur d'écoutes
GET    /stream/{track_id}             flux audio
```

**Profil (tous rôles)**
```
PATCH /me                  username
POST  /me/password         ancien + nouveau mot de passe
PATCH /me/artist           bio (artiste uniquement)
```

**Artist**
```
GET    /artist/me/tracks
GET    /artist/me/albums
POST   /artist/albums                  crée un album brouillon (titre, cover)
POST   /artist/albums/{id}/tracks      upload d'une piste
PATCH  /artist/tracks/{id}             renommer
DELETE /artist/tracks/{id}
POST   /artist/albums/{id}/publish     bouton « Upload »
DELETE /artist/albums/{id}
GET    /stream/{track_id}              uniquement ses propres titres
```

**Admin**
```
GET  /admin/artists?status=pending
POST /admin/artists/{id}/approve
POST /admin/artists/{id}/reject        avec motif
PUT  /admin/featured-playlist          désigne la playlist à la une
```

Documentation générée automatiquement par FastAPI sur `/docs`.

---

## 6. Couche données (MySQL)

### Schéma
```sql
users (
  id, username UNIQUE, email UNIQUE, password_hash,
  role ENUM('user','artist','admin'), is_verified BOOL, created_at
)
email_tokens (
  id, user_id, token_hash, purpose ENUM('verify','reset'),
  expires_at, used_at
)
artists (
  id, user_id UNIQUE, name, bio TEXT,
  status ENUM('pending','approved','rejected'),
  reviewed_by, reviewed_at, rejection_reason
)
albums (
  id, artist_id, title, cover_path,
  status ENUM('draft','published'), release_date NULL, created_at
)
tracks (
  id, album_id, title, position, duration_s, file_path,
  play_count, created_at
)
track_likes       (user_id, track_id, created_at)      PK (user_id, track_id)
album_likes       (user_id, album_id, created_at)      PK (user_id, album_id)
playlists         (id, user_id, name, cover_path, created_at)
playlist_tracks   (playlist_id, track_id, position, added_at)
app_settings      (`key` PK, value)                    ex. featured_playlist_id
listening_history (id, user_id, track_id, played_at)
search_outbox     (id, entity, entity_id, action, created_at, processed_at)
```

### Règles
- Encodage **`utf8mb4`** partout (accents, emojis).
- Index sur toutes les clés étrangères et sur `(user_id, played_at)`.
- `release_date` est rempli au moment de la publication.
- Nombre de titres et durée d'une playlist : `COUNT(*)` et `SUM(duration_s)`.
- Migrations uniquement via **Alembic**, jamais de modification manuelle du schéma.
- Le compte admin et la playlist à la une sont créés par script.

### Stockage des fichiers
- Audio et covers sur un volume (`/data/audio`, `/data/covers`) ou dans MinIO.
- Noms de fichiers générés (**UUID**), jamais le nom envoyé par l'utilisateur.

---

## 7. Streaming audio

- Le navigateur envoie des requêtes HTTP **`Range`** pour avancer dans un morceau. Le serveur doit répondre **`206 Partial Content`**.
- Méthode : l'API vérifie les droits, puis répond avec l'en-tête **`X-Accel-Redirect: /protected-audio/<fichier>`**. **Nginx envoie lui-même le fichier** et gère `Range`. Python ne transfère jamais les octets audio.
- Droits : un user écoute les titres **publiés** d'artistes **validés**, un artiste écoute uniquement **ses** titres.

---

## 8. Upload d'album (artiste)

- Nginx : **`client_max_body_size 200M;`** (par défaut 1 Mo, ce qui donne l'erreur 413).
- Vérifier côté serveur :
  - le type réel du fichier (lecture avec `mutagen`, pas seulement l'extension) ;
  - la taille maximale ;
  - la durée (extraite par `mutagen`, stockée dans `duration_s`).
- Cover : redimensionnée avec Pillow (ex. 600×600 et 128×128 pour les listes).
- L'album reste en **`draft`** tant que l'artiste n'a pas cliqué sur **Upload**. La publication met `status = published`, remplit `release_date` et déclenche l'indexation dans Elasticsearch.
- Optionnel : conversion en MP3 homogène avec `ffmpeg` dans le worker.

---

## 9. Moteur de recherche (Elasticsearch)

### Index
Trois index : **`tracks`**, **`albums`**, **`artists`**. Seuls les contenus publiés d'artistes validés y figurent. Chaque index est accédé via un **alias** pour pouvoir réindexer sans coupure.

### Mapping (exemple `tracks`)
```json
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 2,
    "analysis": {
      "analyzer": {
        "folding": { "tokenizer": "standard", "filter": ["lowercase", "asciifolding"] }
      }
    }
  },
  "mappings": {
    "properties": {
      "title":        { "type": "search_as_you_type", "analyzer": "folding" },
      "artist_name":  { "type": "search_as_you_type", "analyzer": "folding" },
      "album_title":  { "type": "text", "analyzer": "folding" },
      "duration_s":   { "type": "integer" },
      "play_count":   { "type": "integer" },
      "release_date": { "type": "date" }
    }
  }
}
```

### Requête
- `multi_match` de type `bool_prefix` sur `title`, `title._2gram`, `title._3gram`, `artist_name`…
- Pondération des champs : `title^3`, `artist_name^2`, `album_title`.
- `fuzziness: "AUTO"` pour les fautes de frappe.
- `function_score` sur `play_count` pour faire remonter les titres populaires.
- **`_msearch`** pour interroger les trois index en une seule requête (résultats Songs / Album / Artists).
- `asciifolding` : « beyonce » trouve « Beyoncé ». Une traduction (« Mauvaislapin » → « Bad Bunny ») nécessiterait une liste de synonymes écrite à la main.

### Synchronisation MySQL → Elasticsearch
- **Table outbox** : dans la même transaction que la modification MySQL, insérer une ligne dans `search_outbox`. Le worker lit cette table et indexe dans ES via l'API **`_bulk`**, puis marque la ligne comme traitée.
- Événements à propager : publication/suppression d'album, renommage de piste, validation d'artiste, changement de nom ou de bio d'artiste, mise à jour périodique de `play_count`.
- Script **`reindex_es.py`** : reconstruit un nouvel index depuis MySQL puis bascule l'alias.

---

## 10. Gestion de charge

### Elasticsearch
- **Cluster de 3 nœuds** (tous éligibles master) : quorum garanti, pas de *split-brain* si un nœud tombe.
- **Shards primaires** : 1 suffit pour ce volume. **Répliques** : chaque réplique peut répondre aux recherches, ce qui augmente le débit de lecture et assure la tolérance aux pannes.
- Le client Python reçoit la liste des 3 nœuds et répartit les requêtes lui-même.

### API
- Instances multiples derrière Nginx :
```nginx
upstream api {
    least_conn;
    server api1:8000;
    server api2:8000;
    server api3:8000;
}
server {
    client_max_body_size 200M;
    location /api/             { proxy_pass http://api; }
    location /protected-audio/ { internal; alias /data/audio/; }
    location /covers/          { alias /data/covers/; expires 30d; }
    location /                 { root /usr/share/nginx/html; try_files $uri /index.html; }
}
```
- `docker compose up --scale api=3`.
- Chaque instance : `gunicorn -k uvicorn.workers.UvicornWorker -w <nb_coeurs>`.

### Cache et protection (Redis)
- **Accueil / playlist à la une** : identique pour tous, mise en cache, cache vidé quand l'admin modifie la playlist.
- **Recherches fréquentes** : cache court (30–60 s).
- **Compteur d'écoutes** : `INCR` dans Redis, écrit en base par lot par le worker (pas d'`UPDATE` MySQL à chaque écoute).
- **Limitation de débit** : `limit_req` dans Nginx (recherche, login, renvoi d'email).
- Optionnel : réplication MySQL principal/réplique pour répartir les lectures.

### Mesure
- **Locust** : scénarios « rechercher », « écouter », « liker », « ouvrir une playlist ».
- Comparer latence p95 et requêtes/s : 1 vs 3 instances d'API, 0 vs 2 répliques ES, avec et sans cache Redis.

---

## 11. Emails

- Emails à envoyer : vérification d'adresse, réinitialisation du mot de passe, artiste validé, artiste refusé (avec motif).
- Tokens aléatoires (`secrets.token_urlsafe`), stockés **hachés** (SHA-256), expiration 24 h, usage unique.
- Renvoi limité (ex. 1 par minute).
- Développement : **Mailpit** dans Docker (interface web pour lire les emails, rien n'est réellement envoyé). Production : SMTP (Gmail avec mot de passe d'application, Brevo…).
- Envoi fait par le worker, pas pendant la requête HTTP.

---

## 12. Sécurité

- Requêtes SQL uniquement via l'ORM ou des requêtes paramétrées (injection SQL).
- Pas d'`innerHTML` avec des données utilisateur (XSS).
- Cookies `HttpOnly` + `SameSite=Strict` ; HTTPS en production.
- Vérification des rôles **côté serveur** sur chaque route (cacher un bouton côté client ne protège rien).
- Un artiste ne modifie que ses propres contenus ; un user ne modifie que ses propres playlists.
- Uploads : type réel vérifié, taille limitée, nom de fichier généré.
- Secrets (mots de passe BD, clé JWT, SMTP) dans un fichier `.env` **non versionné**.
- Aucun compte admin créable depuis le site.

---

## 13. Environnement Docker (Windows)

Services du `docker-compose.yml` : `nginx`, `api` (×N), `worker`, `mysql`, `redis`, `es01`, `es02`, `es03`, `kibana`, `mailpit`, optionnel `minio`.

Points spécifiques à Elasticsearch :
- Dans WSL : `wsl -d docker-desktop sysctl -w vm.max_map_count=262144`.
- Mémoire limitée par nœud : `ES_JAVA_OPTS=-Xms512m -Xmx512m` (prévoir 8 Go de RAM minimum pour 3 nœuds).
- Variables du cluster : `cluster.name`, `node.name`, `discovery.seed_hosts=es01,es02,es03`, `cluster.initial_master_nodes=es01,es02,es03`.
- ES 8 active la sécurité (TLS + mot de passe) par défaut. En développement : `xpack.security.enabled=false`, à justifier dans le rapport.
- Volumes nommés pour MySQL, ES et les fichiers audio (les données survivent au redémarrage des conteneurs).

---

## 14. Données de test

- **FMA dataset (`fma_small`)** : 8 000 extraits MP3 libres de droits + CSV de métadonnées (titres, artistes, albums).
- Script `seed_fma.py` : crée des comptes artistes **déjà validés**, leurs albums **publiés**, importe les fichiers, remplit MySQL puis déclenche l'indexation ES.
- Script `create_admin.py` : crée le compte admin et la playlist à la une.

---

## 15. Pièges à éviter

| Piège | Conséquence | Solution |
|---|---|---|
| Recharger la page à chaque navigation | La musique s'arrête | SPA avec un seul `<audio>` |
| Fichiers audio dans MySQL | Base énorme, lenteur | Fichiers sur disque/MinIO, chemin en base |
| Python qui envoie les fichiers audio | API saturée | `X-Accel-Redirect` + Nginx |
| Pas de support `Range` | Impossible d'avancer dans un morceau | Nginx gère `Range` |
| `client_max_body_size` par défaut | Upload refusé (413) | `200M` |
| Écrire dans ES directement sans outbox | MySQL et ES divergent | Table outbox + worker |
| Sessions en mémoire dans l'API | Impossible d'avoir plusieurs instances | JWT + Redis |
| `UPDATE play_count` à chaque écoute | Contention sur la base | Compteurs Redis + écriture par lot |
| Afficher le mot de passe actuel | Impossible (haché) | Ancien / nouveau / confirmation uniquement |
| Pop-ups sans URL | « Retour » quitte l'app | Hash dans l'URL par pop-up |
| Oubli de `asciifolding` | « beyonce » ne trouve pas « Beyoncé » | Analyseur `folding` |
| `vm.max_map_count` trop bas | ES ne démarre pas | Réglage dans WSL |
