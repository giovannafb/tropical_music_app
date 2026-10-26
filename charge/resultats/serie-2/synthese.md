# Série « serie-2 » : synthèse

Généré par `python3 charge/analyser.py rapport serie-2` à partir des fichiers bruts de ce dossier. Chaque chiffre ne porte que sur la fenêtre de mesure de son palier (montée exclue).

## Trois machines virtuelles (vm)

Configuration : `vm-configuration.txt` — cible http://192.168.56.11:80, montée 10 s, plateau 60 s, commit 6ac9106.

### Côté client

| Utilisateurs | Effectifs | Débit (req/s) | Réussies (req/s) | Parcours/s | Médiane (ms) | p90 (ms) | p95 (ms) | p99 (ms) | p95 1-Connexion (ms) | p95 2-Titres-likes (ms) | Erreurs 1-Connexion | Erreurs 2-Titres-likes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 0.9 | 0.9 | 0.5 | 41 | 170 | 182 | 209 | 196 | 38 | 0.0 % | 0.0 % |
| 10 | 10 | 8.3 | 8.3 | 4.2 | 121 | 531 | 689 | 797 | 770 | 83 | 0.0 % | 0.0 % |
| 25 | 25 | 9.9 | 9.5 | 4.7 | 1563 | 2856 | 3310 | 4204 | 3662 | 1695 | 8.9 % | 0.0 % |
| 50 | 50 | 25.9 | 2.5 | 0.5 | 2 | 4851 | 5749 | 6659 | 5799 | 5140 | 91.7 % | 76.7 % |
| 100 | 100 | 37.3 | 2.3 | 0.3 | 2 | 5667 | 7115 | 11904 | 7115 | 6696 | 94.5 % | 84.4 % |
| 150 | 150 | 43.1 | 1.8 | 0.4 | 3 | 5140 | 10011 | 18115 | 10010 | 11308 | 96.7 % | 78.2 % |

Principales causes d'erreur :

- 25 utilisateurs : 502 Connexion refusée : le code de retour n'est pas 200 (28)
- 50 utilisateurs : 502 Connexion refusée : le code de retour n'est pas 200 (1318)
- 50 utilisateurs : 502 Consultation refusée : le code de retour n'est pas 200 (89)
- 100 utilisateurs : 502 Connexion refusée : le code de retour n'est pas 200 (1958)
- 100 utilisateurs : 502 Consultation refusée : le code de retour n'est pas 200 (108)
- 100 utilisateurs : Non HTTP response code: org.apache.http.conn.ConnectTimeoutException Connexion refusée : le code de retour n'est pas 200 (28)
- 150 utilisateurs : 502 Connexion refusée : le code de retour n'est pas 200 (2341)
- 150 utilisateurs : 502 Consultation refusée : le code de retour n'est pas 200 (79)
- 150 utilisateurs : Non HTTP response code: org.apache.http.conn.ConnectTimeoutException Connexion refusée : le code de retour n'est pas 200 (50)

### Côté serveur

Processeur moyen sur la fenêtre de mesure, en % d'un cœur (200 = deux cœurs pleins) ; « total » : utilisé / disponible ; « vue de l'hôte » : le processus de la VM dans WSL, virtualisation comprise.

| Utilisateurs | nginx | api | worker | mysql | redis | elasticsearch | mailpit | vm-donnees (total) | vm-metier (total) | vm-presentation (total) | vm-donnees vue de l'hôte | vm-metier vue de l'hôte | vm-presentation vue de l'hôte | hôte (total) | JMeter |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 15 | 1 | 2 | 1 | 3 | 0 | 6 / 200 | 14 / 200 | 1 / 100 | 22 | 21 | 11 | 62 / 1200 | 1 |
| 10 | 2 | 118 | 0 | 6 | 1 | 3 | 0 | 12 / 200 | 120 / 200 | 4 / 100 | 29 | 128 | 15 | 188 / 1200 | 4 |
| 25 | 2 | 201 | 1 | 8 | 1 | 3 | 0 | 14 / 200 | 200 / 200 | 5 / 100 | 33 | 204 | 16 | 274 / 1200 | 4 |
| 50 | 3 | 192 | 1 | 7 | 1 | 3 | 0 | 13 / 200 | 174 / 200 | 6 / 100 | 31 | 184 | 18 | 257 / 1200 | 7 |
| 100 | 4 | 203 | 1 | 7 | 1 | 3 | 0 | 13 / 200 | 193 / 200 | 8 / 100 | 32 | 202 | 20 | 280 / 1200 | 8 |
| 150 | 5 | 205 | 1 | 8 | 2 | 4 | 0 | 16 / 200 | 196 / 200 | 10 / 100 | 35 | 204 | 23 | 288 / 1200 | 9 |

Mémoire moyenne, en Mo.

| Utilisateurs | nginx | api | worker | mysql | redis | elasticsearch | mailpit | vm-donnees (total) | vm-metier (total) | vm-presentation (total) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 4 | 547 | 58 | 232 | 7 | 983 | 19 | 1470 | 944 | 176 |
| 10 | 4 | 595 | 58 | 233 | 7 | 983 | 19 | 1459 | 1027 | 176 |
| 25 | 4 | 940 | 57 | 233 | 7 | 983 | 7 | 1471 | 1275 | 175 |
| 50 | 4 | 829 | 57 | 233 | 7 | 983 | 8 | 1454 | 1038 | 177 |
| 100 | 5 | 901 | 57 | 233 | 7 | 983 | 8 | 1453 | 1101 | 176 |
| 150 | 6 | 736 | 58 | 233 | 7 | 983 | 8 | 1455 | 979 | 179 |

Base de données et incidents (« connexions max » : record depuis le démarrage de MySQL).

| Utilisateurs | Connexions MySQL (moy. / max) | Requêtes SQL/s | InnoDB lu (ko/s) | InnoDB écrit (ko/s) | Disque de la base, écrit (ko/s) | Événements |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 19 / 56 | 6 | 0 | 15 | 67 | retour_au_repos_s 10 |
| 10 | 25 / 56 | 29 | 0 | 0 | 46 | retour_au_repos_s 11 |
| 25 | 24 / 56 | 39 | 0 | 0 | 49 | workers_relances 7, erreurs_nginx 38, vm-metier_tues_memoire 5, retour_au_repos_s 10 |
| 50 | 20 / 56 | 27 | 0 | 2 | 49 | workers_relances 21, erreurs_nginx 1591, vm-metier_tues_memoire 15, retour_au_repos_s 11 |
| 100 | 19 / 56 | 37 | 0 | 0 | 21 | workers_relances 21, erreurs_nginx 2397, vm-metier_tues_memoire 18, retour_au_repos_s 11 |
| 150 | 19 / 56 | 30 | 0 | 0 | 17 | workers_relances 24, erreurs_nginx 2681, vm-metier_tues_memoire 17, retour_au_repos_s 11 |

### Saturation

- Débit maximal soutenu (moins de 1 % d'erreurs) : **8.3 req/s** à 10 utilisateurs (p95 689 ms).
- Point de saturation : **10 utilisateurs**.
- Ressource la plus chargée à ce palier : vm-metier : processeur à 60 % de ses 2 cœurs (api 118 %, mysql 6 %, elasticsearch 3 % d’un cœur) — à confirmer avec les relevés ci-dessus avant de nommer le goulot d'étranglement.

## Trois conteneurs (docker)

Configuration : `docker-configuration.txt` — cible http://localhost:80, montée 10 s, plateau 60 s, commit 6ac9106.

### Côté client

| Utilisateurs | Effectifs | Débit (req/s) | Réussies (req/s) | Parcours/s | Médiane (ms) | p90 (ms) | p95 (ms) | p99 (ms) | p95 1-Connexion (ms) | p95 2-Titres-likes (ms) | Erreurs 1-Connexion | Erreurs 2-Titres-likes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 0.9 | 0.9 | 0.5 | 7 | 67 | 71 | 114 | 91 | 7 | 0.0 % | 0.0 % |
| 10 | 10 | 9.8 | 9.8 | 4.9 | 54 | 72 | 83 | 109 | 94 | 9 | 0.0 % | 0.0 % |
| 25 | 25 | 23.6 | 23.6 | 11.9 | 34 | 92 | 108 | 154 | 126 | 11 | 0.0 % | 0.0 % |
| 50 | 50 | 45.8 | 45.8 | 23.0 | 60 | 251 | 335 | 503 | 428 | 36 | 0.0 % | 0.0 % |
| 100 | 100 | 55.2 | 55.2 | 27.6 | 622 | 1958 | 2247 | 2728 | 2462 | 235 | 0.0 % | 0.0 % |
| 150 | 150 | 53.1 | 53.1 | 26.7 | 1561 | 3960 | 4520 | 5483 | 5022 | 1418 | 0.0 % | 0.0 % |

### Côté serveur

Processeur moyen sur la fenêtre de mesure, en % d'un cœur (200 = deux cœurs pleins) ; « total » : utilisé / disponible ; « vue de l'hôte » : le processus de la VM dans WSL, virtualisation comprise.

| Utilisateurs | nginx | api | worker | mysql | redis | elasticsearch | kibana | mailpit | hôte (total) | JMeter |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 12 | 0 | 1 | 0 | 11 | 3 | 0 | 48 / 1200 | 1 |
| 10 | 1 | 89 | 0 | 1 | 0 | 11 | 3 | 0 | 143 / 1200 | 4 |
| 25 | 2 | 241 | 0 | 6 | 1 | 14 | 4 | 0 | 317 / 1200 | 7 |
| 50 | 4 | 667 | 0 | 7 | 1 | 9 | 6 | 1 | 727 / 1200 | 13 |
| 100 | 5 | 1117 | 0 | 11 | 2 | 8 | 7 | 1 | 1160 / 1200 | 19 |
| 150 | 4 | 1103 | 0 | 14 | 1 | 15 | 6 | 2 | 1164 / 1200 | 18 |

Mémoire moyenne, en Mo.

| Utilisateurs | nginx | api | worker | mysql | redis | elasticsearch | kibana | mailpit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 16 | 561 | 61 | 477 | 6 | 3371 | 609 | 20 |
| 10 | 16 | 606 | 61 | 482 | 6 | 3407 | 603 | 21 |
| 25 | 16 | 605 | 61 | 516 | 6 | 3415 | 605 | 20 |
| 50 | 16 | 798 | 61 | 534 | 8 | 3418 | 614 | 20 |
| 100 | 17 | 2740 | 61 | 564 | 8 | 3424 | 625 | 21 |
| 150 | 18 | 4575 | 61 | 587 | 8 | 3433 | 626 | 21 |

Base de données et incidents (« connexions max » : record depuis le démarrage de MySQL).

| Utilisateurs | Connexions MySQL (moy. / max) | Requêtes SQL/s | InnoDB lu (ko/s) | InnoDB écrit (ko/s) | Disque de la base, écrit (ko/s) | Événements |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 8 / 8 | 7 | 0 | 2 | 4 | retour_au_repos_s 10 |
| 10 | 10 / 11 | 34 | 0 | 0 | 0 | retour_au_repos_s 10 |
| 25 | 15 / 17 | 75 | 0 | 0 | 0 | retour_au_repos_s 10 |
| 50 | 27 / 31 | 142 | 0 | 0 | 0 | retour_au_repos_s 10 |
| 100 | 60 / 73 | 184 | 0 | 0 | 0 | retour_au_repos_s 10 |
| 150 | 87 / 92 | 174 | 0 | 0 | 0 | retour_au_repos_s 10 |

### Saturation

- Débit maximal soutenu (moins de 1 % d'erreurs) : **55.2 req/s** à 100 utilisateurs (p95 2247 ms).
- Point de saturation : **100 utilisateurs**.
- Ressource la plus chargée à ce palier : hôte : processeur à 97 % de ses 12 cœurs (api 1117 %, mysql 11 %, elasticsearch 8 % d’un cœur) — à confirmer avec les relevés ci-dessus avant de nommer le goulot d'étranglement.

## Tableau de synthèse

| Grandeur | Trois machines virtuelles | Trois conteneurs |
|---|---|---|
| Débit maximal soutenu | 8.3 req/s (10 utilisateurs) | 55.2 req/s (100 utilisateurs) |
| Charge au point de saturation | 10 utilisateurs | 100 utilisateurs |
| Latence au 95e centile, à charge égale (10 utilisateurs) | 689 ms | 83 ms |
| Goulot d'étranglement identifié | à nommer (indice : vm-metier : processeur à 60 % de ses 2 cœurs (api 118 %, mysql 6 %, elasticsearch 3 % d’un cœur)) | à nommer (indice : hôte : processeur à 97 % de ses 12 cœurs (api 1117 %, mysql 11 %, elasticsearch 8 % d’un cœur)) |
| Temps de démarrage complet | étape 10 | étape 14 |
| Mémoire consommée au repos | étape 10 | étape 14 |

Latence au 95e centile à chaque palier commun :

| Utilisateurs | 3 VM (ms) | 3 conteneurs (ms) | Conteneurs par rapport aux VM |
|---|---:|---:|---:|
| 1 | 182 | 71 | -61 % |
| 10 | 689 | 83 | -88 % |
| 25 | 3310 | 108 | -97 % |
| 50 | 5749 | 335 | -94 % |
| 100 | 7115 | 2247 | -68 % |
| 150 | 10011 | 4520 | -55 % |

## Graphiques

![Débit](debit.svg)

![Latence au 95e centile](latence-p95.svg)

![Taux d'erreur](erreurs.svg)
