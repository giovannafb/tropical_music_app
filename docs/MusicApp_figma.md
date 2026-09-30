# MusicApp — Organisation du Figma & design tokens

Source : https://www.figma.com/design/zopP0JUXNwilGrHUaUfMvN/MusicApp
Lien vers un écran précis : `https://www.figma.com/design/zopP0JUXNwilGrHUaUfMvN/MusicApp?node-id=<node-id avec un tiret>`
(ex. node `11:9866` → `?node-id=11-9866`)

> **Comment ces données ont été obtenues**
> - **Structure** : lecture complète de la page « Écrans » (16 écrans, tous les calques, noms, positions, tailles).
> - **Couleurs** : relevées pixel par pixel sur les rendus Figma de 2 écrans (*User · Playlist* et *Artiste · New album*).
>   Les aplats sont exacts ; les dégradés sont reconstitués à partir de plusieurs points de mesure.
>   Les autres écrans n'ont pas pu être rendus (limite d'appels de l'offre Figma Starter).
> - La **barre de lecture**, ajoutée après cette lecture, **n'est pas décrite ici**.
> - Les valeurs marquées **≈** ou listées en section 7 sont à confirmer dans Figma (panneau *Design* à droite).

---

## 1. Organisation du fichier

Une seule page : **Écrans**. Toutes les frames font **1920 × 1080** (sauf mention).
Les écrans sont rangés en colonnes sur le canvas :

| Colonne (x) | Contenu |
|---|---|
| 0 et 1960 | Authentification (connexion, inscription, messages email) |
| 3968 | Espace **User** |
| 5955 | Espace **Artiste** |

---

## 2. Inventaire des écrans

### Authentification

| Node-id | Nom Figma | Route prévue | Contenu |
|---|---|---|---|
| `2:3` | 01 · Connexion | `#/login` | Carte 477×577 centrée : titre « Welcome ! », champs *Username* et *Password*, bouton *Log in*, lien vers l'inscription |
| `2:15` | 02 · Inscription | `#/register` | Carte 477×814 : *Username*, *Email adress*, *Password*, *Confirm password*, bouton *Sign in* (à renommer *Sign up*), lien *Log in* |
| `11:10966` | 03 · Compte non vérifié | `#/not-verified` | Bloc message 926×417 « Sorry ! Account not verified » + bouton *Back to login* |
| `26:13603` | 03 · Email de vérification | `#/verify-email` | Bloc message 926×417, lien « Not seeing the email ? send it again. », bouton *Done ? log in* |

### Espace User

| Node-id | Nom Figma | Route prévue | Contenu |
|---|---|---|---|
| `11:9866` | 10 · User · Accueil | `#/home` | En-tête de tableau *Title / Artist / Album / Length* + liste de titres |
| `12:11634` | 11 · User · Likes | `#/likes` | Même tableau + cœur « liké » sur chaque ligne |
| `12:12010` | 12 · User · Album | `#/albums` | En-tête *Title / Artist / Length* + lignes d'album (145 px) |
| `19:12433` | 12 · User · Search 1 | `#/search` | Barre de recherche 1417×87 avec l'invite « What's on your mind ? » |
| `24:12551` | 12 · User · Search 2 (1920×1523) | `#/search?q=` | Barre de recherche en haut, sections **Songs** (3 lignes), **Album** (2 lignes), **Artists** (2 lignes) |
| `29:644` | 12 · User · Playlist | `#/playlists` | Bouton « + New playlist » en haut à droite, lignes de playlist (cover, nom, nombre de titres, durée) |
| `30:840` | 12 · User · create playlist | `#/playlists/new` | Cover 349×349 (+ « Add playlist cover »), champ *Playlist name*, bloc « Add new tracks », liste de titres, bouton *Create* |
| `11:10193` | 13 · User · Aucun titre | (état vide) | Message « No track found » |
| `26:13253` | 14 · User · Profile | `#/profile` | *Change username* (crayon), champs *Password* / *New password* / *Confirm new password* / *Old password*, bouton *Confirm Password* |

### Espace Artiste

| Node-id | Nom Figma | Route prévue | Contenu |
|---|---|---|---|
| `11:10983` | 20 · Artiste · Accueil | `#/artist/tracks` | Tableau *Title / Artist / Album / Length* des titres de l'artiste |
| `25:12750` | 21 · Artiste · Album | `#/artist/albums` | En-tête *Title / Artist / Length* + lignes d'album |
| `26:12961` | 22 · Artiste · New album | `#/artist/new-album` | Cover (+ « Add album cover »), champ *Title*, bloc « Add new tracks », pistes avec crayon, bouton *Upload* |
| `26:13437` | 22 · Artiste · Profile (1920×1756) | `#/artist/profile` | Comme le profil User + bloc « Change your biography » (zone 1232×389 avec crayon) |

### Écrans à ajouter (absents du Figma)
Barre de lecture (ajoutée depuis), pop-ups détail titre / album / artiste / playlist, inscription artiste,
compte artiste en attente, espace admin, mot de passe oublié, ajout à une playlist.

---

## 3. Structure commune (layout)

### Sidebar — 427 px de large (≈ 22,2 % de 1920), toute la hauteur

| Élément | Position (y) | Hauteur |
|---|---|---|
| Header : avatar 79×77 + « Gusteau - User/Artist » | 0 | 104 |
| Élément de navigation | à partir de 104, empilés | 82 chacun |
| *Profile* (collé en bas) | 998 | 82 |

**Ordre de navigation User** : Home → Likes → Albums → Search → Playlist … Profile (en bas)
**Ordre de navigation Artiste** : my tracks → my albums → New album … Profile (en bas)

L'élément actif a un fond plus sombre (`--color-nav-item-active`).

### Zone principale — 1493 px (x = 427 → 1920)

- En-tête de tableau à y = 51, hauteur 30.
- **Colonnes du tableau de titres** (à partir du bord gauche de la zone principale) :

| Colonne | x absolu | % de la zone principale |
|---|---|---|
| Title | 591 | 11 % |
| Artist | 924 | 33,3 % |
| Album | 1388 | 64,4 % |
| Length | 1698 | 85,1 % |

  Sur les écrans album (3 colonnes) : Title 591, Artist ≈ 1098–1134, Length ≈ 1698–1743.

---

## 4. Composants

| Composant (node-id) | Taille | Utilisation |
|---|---|---|
| Ligne de titre — `Component 1` (`7:9441`) | 1493 × 89 | Accueil, Likes, Search (Songs), titres artiste |
| Ligne d'album — `Component 1` (`19:12392`) | 1493 × 145 | Albums, Search (Album), albums artiste |
| Ligne de playlist — `Component 16` (`30:767`) | 1493 × 139 | Liste des playlists |
| Ligne d'artiste — `Component 8` (`24:12663`) | 1493 × 139 | Search (Artists) |
| Ligne de piste en édition — `Component 10` (`26:13196`) | 939 × 89 | New album, create playlist |
| Cover placeholder — `Building blocks/Multi-ratio items/1:1` | 349 × 349 | Ajout de cover (placeholder issu du kit Material 3) |
| Avatar — `Generic avatar` | 79 × 77 | Header de sidebar |

Éléments cachés présents dans les lignes de piste : durée « 2:20 », icône œil (détail), icône *run* (lecture), cœur.

### Autres dimensions utiles

| Élément | Taille |
|---|---|
| Carte connexion / inscription | 477 × 577 / 477 × 814 |
| Champ de formulaire (auth) | 408 × 67, libellé au-dessus (hauteur 42) |
| Bouton principal (auth) | 229 × 73 |
| Bouton large (messages) | 533 × 71 |
| Bouton *Create* / *Upload* | 366 × 104 |
| Champ de titre (playlist / album) | 793 × 94 |
| Barre de recherche | 1417 × 87 |
| Champ du profil | 1232 × 90 |
| Bloc message | 926 × 417 |
| Icônes de navigation | 36 à 46 px |
| Icône « + » grand format | 101 px (bloc « Add new tracks »), 60–64 px ailleurs |

---

## 5. Icônes

Les calques portent les noms **Iconify** (`collection:icône`). On peut donc utiliser exactement les mêmes icônes
(export SVG depuis https://icon-sets.iconify.design ou script Iconify).

| Usage | Icône |
|---|---|
| Home | `akar-icons:home-alt1` |
| Likes / like | `icon-park-outline:like` |
| Albums / my albums | `akar-icons:music-album-fill` |
| Search | `akar-icons:search` |
| Playlist | `bxs:playlist` |
| Profile | `gg:profile` |
| my tracks | `akar-icons:music-note` |
| New album / New playlist / ajouter | `akar-icons:circle-plus-fill` |
| Modifier (crayon) | `fa6-solid:pen` |
| Détail d'un titre (œil) | `basil:eye-solid` |
| Lecture | `codicon:run-compact` |

---

## 6. Couleurs

### Relevé

| Token | Valeur | Où |
|---|---|---|
| Primaire | `#45939A` | Header de sidebar, bouton *Upload* |
| Fond principal (dégradé vertical) | `#8CF7F9` → `#FFFFFF` | Zone principale de tous les écrans (linéaire, vérifié en 12 points) |
| Fond de sidebar (dégradé vertical) | ≈ `#BAFBFB` → `#FFFFFF` | Zone vide de la sidebar |
| Élément de navigation | `#BEEBEC` (entre `#B2DDDE` et `#C8EBEC` selon la position) | Home, Likes, Albums… |
| Élément de navigation actif | `#ACC1C2` (≈ `#A6C1C1` côté artiste) | Onglet sélectionné |
| Bordure entre éléments de navigation | `#88AAAA` | Séparateurs de sidebar |
| Élément *Profile* (bas) | `#EBEEEE` | Bas de sidebar |
| Fond des listes (dégradé vertical) | `#7DBABB` → `#BDBDBD` | Liste des playlists |
| Séparateur de lignes | `#638B8B` | Entre deux lignes de playlist |
| Ligne neutre | `#D9D9D9` | Pistes dans New album / create playlist |
| Bloc neutre | `#CCCCCC` | Bloc « Add new tracks » |
| Fond de champ | `#ECFEFE` | Champ *Title* / *Playlist name* |
| Placeholder cover | `#ECE6F0` (formes `#C9C3CD`) | Cover vide |
| Fond avatar | `#75CECF` | Avatar générique |
| Texte principal / icônes | `#000000` | Titres, libellés, icônes |
| Texte secondaire | ≈ `#273838` | « 12 tracks », « 22 min 34 » |
| Texte sur primaire | `#FFFFFF` | « Gusteau - User » dans le header |

### Variables CSS

```css
:root {
  /* Marque */
  --color-primary: #45939A;
  --color-on-primary: #FFFFFF;          /* texte du header de sidebar */

  /* Fonds */
  --gradient-main: linear-gradient(180deg, #8CF7F9 0%, #FFFFFF 100%);
  --gradient-sidebar: linear-gradient(180deg, #BAFBFB 0%, #FFFFFF 100%);   /* ≈ */
  --gradient-list: linear-gradient(180deg, #7DBABB 0%, #BDBDBD 100%);

  /* Navigation */
  --color-nav-item: #BEEBEC;
  --color-nav-item-active: #ACC1C2;
  --color-nav-border: #88AAAA;
  --color-nav-bottom: #EBEEEE;

  /* Listes et blocs */
  --color-row-separator: #638B8B;
  --color-row-neutral: #D9D9D9;
  --color-block-neutral: #CCCCCC;

  /* Formulaires */
  --color-input-bg: #ECFEFE;

  /* Placeholders */
  --color-placeholder-bg: #ECE6F0;
  --color-placeholder-shape: #C9C3CD;
  --color-avatar-bg: #75CECF;

  /* Texte */
  --color-text: #000000;
  --color-text-secondary: #273838;      /* ≈ */
  --color-icon: #000000;

  /* Dimensions (base 1920 × 1080) */
  --sidebar-width: 427px;
  --sidebar-header-height: 104px;
  --nav-item-height: 82px;
  --row-track-height: 89px;
  --row-album-height: 145px;
  --row-playlist-height: 139px;
}
```

---

## 7. À relever dans Figma (non mesuré)

- **Police(s)** : la police des rendus est une **serif** (nom exact, graisses et tailles à relever).
- Couleurs des écrans non rendus :
  - carte et boutons de connexion / inscription ;
  - blocs de message (compte non vérifié, email de vérification) ;
  - barre de recherche ;
  - cœur « liké » ;
  - page profil ;
  - barre de lecture.
- **Rayons d'arrondi** (cartes, boutons, champs) et **opacités** éventuelles (les éléments de navigation semblent semi-transparents : leur teinte varie avec le dégradé en dessous).
- Présence éventuelle de **styles ou variables Figma** (non accessible pendant l'analyse).

---

## 8. Incohérences repérées dans le fichier

- Numérotation en double : « 03 » (×2), « 12 » (Album, Search 1, Search 2, Playlist, create playlist), « 22 » (New album, Profile artiste).
- Calques *Search* et *Playlist* de la sidebar nommés tous deux **« Nav / Explorer »**.
- Un texte « What's on your mind ? » est placé par erreur **dans le calque de l'icône playlist** (écrans Search 1, Playlist, create playlist).
- Libellés mélangés anglais / français : « my tracks » / « Mes titres », « my albums » / « Mes albums » (écran 21).
- L'écran **21 · Artiste · Album** n'a pas l'élément de navigation *New album*.
- Le bouton de l'écran d'inscription s'appelle *Sign in* (à renommer *Sign up*).
- Le profil affiche un champ *Password* avec icône œil : **ne pas l'implémenter** (le mot de passe actuel est haché et ne peut pas être affiché).
