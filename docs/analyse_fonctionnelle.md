# MusicApp — analyse fonctionnelle (étape 1)

Ce document établit qui fait quoi, et avec quelles données, avant toute décision technique. Il transpose à MusicApp, application d'écoute de musique, les attendus de l'étape 1 du sujet : acteurs, cas d'usage, cas d'erreur, matrice des règles de gestion. Les écrans cités sont ceux du prototype Figma (`figma_link`, `docs/protofigma/`) ; les codes d'erreur sont ceux que l'API renvoie au client (`metier/app`).

## 1. Acteurs

| Acteur | Création du compte | Ce qu'il peut faire | Ce qu'il ne peut jamais faire |
|---|---|---|---|
| **Visiteur** | — | s'inscrire comme user ou comme artiste ; vérifier son email ; demander un nouveau mot de passe ; se connecter | consulter le catalogue |
| **User** (auditeur) | inscription publique, puis vérification de l'email | écouter les titres ; liker titres et albums ; rechercher ; créer et gérer **ses** playlists ; consulter l'accueil (titres à la une), les fiches titre, album et artiste ; modifier son profil | voir ou modifier les playlists des autres ; voir un album non publié ou un artiste non validé |
| **Artiste** | inscription distincte (nom d'artiste, bio), vérification de l'email, puis **validation par l'admin** | créer un album (cover, titres), renommer ou supprimer ses titres, publier ; consulter **ses** titres et albums ; modifier sa bio | se connecter avant d'être validé ; agir sur la musique d'un autre artiste ; écouter, liker ou rechercher le catalogue |
| **Admin** | créé par script (`create_admin.py`), jamais par le site | valider ou refuser (avec motif) les comptes artistes ; composer la playlist « à la une » | supprimer la playlist à la une |

Le rôle est vérifié **côté serveur sur chaque route** (`require_role`), et non seulement par le menu affiché : un user qui appelle une route artiste reçoit `403 FORBIDDEN`.

## 2. Cas d'usage

Forme homogène : acteur, déclencheur, enchaînement nominal, cas d'erreur.

| # | Cas d'usage | Acteur | Déclencheur | Enchaînement nominal | Cas d'erreur |
|---|---|---|---|---|---|
| CU1 | S'inscrire | Visiteur | *Sign up* (ou *Sign up as artist*) | saisie du username, de l'email et du mot de passe (et, pour un artiste, du nom d'artiste et de la bio) → compte créé, non vérifié → email de vérification | username ou email déjà pris (`409`) ; mot de passe de moins de 8 caractères, username hors 3 à 50 caractères (`422`) |
| CU2 | Vérifier son email | Visiteur | lien reçu par email | token valable 24 h, à usage unique → compte vérifié | lien expiré ou déjà utilisé (`400 INVALID_TOKEN`) → renvoi possible, au plus 1 par minute (`429`) |
| CU3 | Se connecter | User, artiste, admin | écran *Connexion* | username **ou** email + mot de passe → session (JWT de 15 min, renouvelé pendant 7 jours) → accueil du rôle | identifiant inconnu ou mot de passe erroné (`401 INVALID_CREDENTIALS`, même message dans les deux cas) ; email non vérifié (`403 EMAIL_NOT_VERIFIED` → écran *Compte non vérifié*) ; artiste en attente (`403 ARTIST_PENDING`) ; artiste refusé (`403 ARTIST_REJECTED`, avec le motif) |
| CU4 | Écouter un titre | User | clic sur un titre | contrôle des droits par l'API, puis envoi du fichier par Nginx (`206`, lecture par plages) ; une écoute est comptée après min(30 s, durée − 1 s) | titre non publié ou artiste non validé (`404`) ; session expirée (`401`) |
| CU5 | Consulter ses likes | User | onglet *Likes* (ou *Albums*) | liste de ses titres (ou albums) likés, du plus récent au plus ancien | aucun like → « No track found » / « No album found » |
| CU6 | Liker / ne plus liker | User | cœur d'un titre ou d'un album | like enregistré une seule fois ; un second like ne change rien | contenu invisible (`404`) |
| CU7 | Rechercher | User | onglet *Search* | résultats groupés Songs / Album / Artists, 10 par section (Elasticsearch) | aucun résultat → « No track found », « No album found », « No artist found » |
| CU8 | Gérer ses playlists | User | onglet *Playlist* | créer (nom, cover facultative), ajouter et retirer des titres, renommer, supprimer ; nombre de titres et durée totale affichés | aucune playlist → « No playlist found » ; playlist d'un autre user → `404` (son existence n'est pas révélée) |
| CU9 | Publier un album | Artiste | *New album* | un seul brouillon à la fois : cover + titre, envoi des pistes MP3 une par une, renommage, puis *Upload* → album publié, date de sortie fixée, indexation | brouillon déjà en cours (`409 DRAFT_EXISTS`) ; pas de cover (`400 COVER_REQUIRED`) ; aucune piste (`400 NO_TRACKS`) ; fichier non MP3 (`400 INVALID_AUDIO`) ; plus de 50 Mo (`413`) |
| CU10 | Consulter sa musique | Artiste | *my tracks* / *my albums* | ses seuls titres et albums publiés | aucun album → « No album yet. » ; aucun titre → « No track found » |
| CU11 | Valider un artiste | Admin | espace *Artists* | liste des comptes en attente → valider, ou refuser avec motif → email envoyé à l'artiste | aucune demande → « No artist waiting for validation » ; compte déjà traité (`409 ALREADY_REVIEWED`) |
| CU12 | Composer la playlist à la une | Admin | espace *Featured* | ajouter ou retirer des titres ; l'accueil des users est mis à jour (cache vidé) | suppression de la playlist à la une refusée (`409 FEATURED_PLAYLIST`) |
| CU13 | Modifier son profil | Tous rôles | *Profile* | username ; mot de passe (ancien + nouveau + confirmation) ; bio (artiste) | ancien mot de passe faux (`400 WRONG_PASSWORD`) ; username déjà pris (`409`) ; *Log out* ferme la session |

## 3. Cas d'erreur

Le sujet impose de lister explicitement les cas d'erreur, et de décider dès l'analyse du message affiché quand il n'y a rien à montrer. Correspondance avec ceux du sujet :

| Cas du sujet (consultation de notes) | Équivalent MusicApp | Réponse de l'API | Ce que voit l'utilisateur |
|---|---|---|---|
| Identifiant inconnu | username ou email inconnu | `401 INVALID_CREDENTIALS` | « Wrong username or password » (même message que pour un mot de passe faux : l'existence d'un compte n'est pas révélée) |
| Mot de passe erroné | idem | `401 INVALID_CREDENTIALS` | idem |
| Compte en attente de validation | artiste non encore validé ; email non vérifié | `403 ARTIST_PENDING` ; `403 EMAIL_NOT_VERIFIED` | écran d'attente de validation ; écran *Compte non vérifié*, avec renvoi de l'email |
| — | artiste refusé | `403 ARTIST_REJECTED` | message avec le motif saisi par l'admin |
| Enseignant sans cours | artiste sans album publié | `200`, liste vide | « No album yet. » |
| Étudiant sans note | user sans like, sans playlist | `200`, liste vide | « No track found », « No album found », « No playlist found » |
| Cours sans étudiant inscrit | album sans titre au moment de la publication | `400 NO_TRACKS` | publication refusée : « Add at least one track before uploading » |
| Accès aux notes d'un autre (paramètre modifié dans l'URL) | playlist d'un autre user (`/playlists/{id}`) ; titre d'un autre artiste (`/artist/tracks/{id}`) | `404` | « not found » : la ressource n'existe pas pour lui |
| Route d'un autre rôle | un user appelle `/admin/…` ou `/artist/…` | `403 FORBIDDEN` | « Access denied » |
| Session expirée | JWT de plus de 15 min | `401 TOKEN_EXPIRED` | renouvellement silencieux par le refresh token, sinon retour à la connexion |
| Abus | connexions répétées, renvois d'email | `429` (Nginx : 10 connexions par minute et par IP) | « Please wait a minute before asking again » |

Chaque liste prévoit trois états : chargement (« Loading… »), vide (messages ci-dessus) et erreur.

## 4. Règles de gestion

| Règle | Énoncé | Équivalent dans le sujet |
|---|---|---|
| **R1** | Un album appartient à un et un seul artiste ; un titre appartient à un et un seul album. | un cours est assuré par un seul enseignant |
| **R2** | Un artiste peut publier plusieurs albums, mais n'a qu'**un seul brouillon** à la fois. | un enseignant assure plusieurs cours |
| **R3** | Un user peut liker plusieurs titres et albums, et créer plusieurs playlists. | un étudiant a plusieurs notes |
| **R4** | Un like est unique pour une paire (user, titre) ou (user, album) ; un titre figure au plus une fois dans une playlist. | une note est unique par paire (étudiant, cours) |
| **R5** | Le username et l'email sont uniques dans tout le système ; on se connecte avec l'un ou l'autre. | le login est unique |
| **R6** | Un nouveau compte est non vérifié tant que l'email n'est pas confirmé ; un compte artiste est en plus **en attente** jusqu'à sa validation par l'admin. Un compte non vérifié, en attente ou refusé ne peut pas se connecter. | un nouveau compte est en attente de validation |
| **R7** | Un user ne voit que les albums **publiés** d'artistes **validés** ; un artiste ne voit que sa propre musique. | un étudiant ne voit que ses notes ; un enseignant, que ses cours |
| **R8** | Un album n'est publié qu'avec une cover et au moins un titre ; sa date de sortie est celle de la publication. | — |
| **R9** | Le compte admin et la playlist à la une sont créés par script ; la playlist à la une ne peut pas être supprimée. | — |

### Matrice : où chaque règle est garantie, et quels cas d'usage la mettent en jeu

| Règle | Base de données (`donnees/migrations`) | Couche métier (`metier/app`) | Cas d'usage |
|---|---|---|---|
| R1 | clés étrangères `albums.artist_id` et `tracks.album_id` non nulles | création et envoi filtrés par l'`artist_id` du compte connecté | CU9, CU10 |
| R2 | — | `DRAFT_EXISTS` si un brouillon existe déjà | CU9 |
| R3 | — | aucune limite | CU5, CU6, CU8 |
| R4 | clés primaires composées `track_likes (user_id, track_id)`, `album_likes (user_id, album_id)`, `playlist_tracks (playlist_id, track_id)` | un like déjà présent n'est pas ajouté une seconde fois | CU6, CU8 |
| R5 | `UNIQUE` sur `users.username` et `users.email` | `USERNAME_TAKEN` / `EMAIL_TAKEN` avant l'insertion | CU1, CU3, CU13 |
| R6 | `users.is_verified` faux par défaut ; `artists.status` = `pending` | refus à la connexion : `EMAIL_NOT_VERIFIED`, `ARTIST_PENDING`, `ARTIST_REJECTED` ; validation réservée à l'admin | CU1, CU2, CU3, CU11 |
| R7 | `albums.status`, `artists.status` | filtre « publié et validé » sur toutes les lectures du catalogue et sur l'écoute ; filtre par propriétaire pour l'artiste et les playlists | CU4, CU5, CU7, CU8, CU10 |
| R8 | `albums.release_date` vide tant que l'album est en brouillon | `COVER_REQUIRED`, `NO_TRACKS` à la publication | CU9 |
| R9 | `app_settings.featured_playlist_id` | `create_admin.py` ; `FEATURED_PLAYLIST` à la suppression | CU11, CU12 |

**Vérification de cohérence.** Aucun cas d'usage ne contredit une règle :
- l'inscription (CU1) crée toujours un compte non vérifié (R6) et refuse un doublon (R5) ;
- la connexion (CU3) applique R6 avant d'ouvrir une session ;
- les lectures (CU4 à CU8) passent toutes par le filtre de R7 ;
- la publication (CU9) applique R2 et R8 ;
- la composition de l'accueil (CU12) ne peut pas supprimer la playlist de R9.

Le seul point qui touche le contenu d'un autre acteur est la consultation d'une ressource par son identifiant dans l'URL (playlist, titre d'artiste). Elle est traitée côté serveur par R7, avec une réponse `404` qui ne révèle pas l'existence de la ressource.
