# Série « serie-1 » : synthèse

Généré par `python3 charge/analyser.py rapport serie-1` à partir des fichiers bruts de ce dossier. Chaque chiffre ne porte que sur la fenêtre de mesure de son palier (montée exclue).

## Trois machines virtuelles (vm)

Configuration : `vm-configuration.txt` — cible http://192.168.56.11:80, montée 10 s, plateau 60 s, commit 6ac9106.

### Côté client

| Utilisateurs | Effectifs | Débit (req/s) | Réussies (req/s) | Parcours/s | Médiane (ms) | p90 (ms) | p95 (ms) | p99 (ms) | p95 1-Connexion (ms) | p95 2-Titres-likes (ms) | Erreurs 1-Connexion | Erreurs 2-Titres-likes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 0.9 | 0.9 | 0.4 | 71 | 195 | 200 | 234 | 206 | 58 | 0.0 % | 0.0 % |
| 10 | 10 | 7.4 | 7.4 | 3.7 | 134 | 519 | 625 | 8039 | 718 | 79 | 0.0 % | 0.0 % |
| 25 | 25 | 10.7 | 8.0 | 3.8 | 1169 | 2799 | 3121 | 3747 | 3293 | 1987 | 33.2 % | 11.7 % |
| 50 | 50 | 24.4 | 1.7 | 0.4 | 2 | 3988 | 4629 | 5889 | 4733 | 3790 | 94.1 % | 77.2 % |
| 100 | 100 | 30.4 | 3.3 | 0.9 | 2 | 8409 | 11920 | 17895 | 11123 | 14602 | 91.4 % | 58.6 % |
| 150 | 150 | 32.3 | 4.2 | 1.9 | 4 | 6620 | 30031 | 31039 | 30031 | 30031 | 91.8 % | 35.8 % |

Principales causes d'erreur :

- 25 utilisateurs : 502 Connexion refusée : le code de retour n'est pas 200 (127)
- 25 utilisateurs : 502 Consultation refusée : le code de retour n'est pas 200 (30)
- 50 utilisateurs : 502 Connexion refusée : le code de retour n'est pas 200 (1285)
- 50 utilisateurs : 502 Consultation refusée : le code de retour n'est pas 200 (78)
- 100 utilisateurs : 502 Connexion refusée : le code de retour n'est pas 200 (1549)
- 100 utilisateurs : 502 Consultation refusée : le code de retour n'est pas 200 (75)
- 150 utilisateurs : 502 Connexion refusée : le code de retour n'est pas 200 (1467)
- 150 utilisateurs : Non HTTP response code: java.net.SocketTimeoutException Connexion refusée : le code de retour n'est pas 200 (131)
- 150 utilisateurs : 502 Consultation refusée : le code de retour n'est pas 200 (37)

### Côté serveur

Processeur moyen sur la fenêtre de mesure, en % d'un cœur (200 = deux cœurs pleins) ; « total » : utilisé / disponible ; « vue de l'hôte » : le processus de la VM dans WSL, virtualisation comprise.

| Utilisateurs | nginx | api | worker | mysql | redis | elasticsearch | mailpit | vm-donnees (total) | vm-metier (total) | vm-presentation (total) | vm-donnees vue de l'hôte | vm-metier vue de l'hôte | vm-presentation vue de l'hôte | hôte (total) | JMeter |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 15 | 1 | 2 | 1 | 3 | 0 | 6 / 200 | 16 / 200 | 1 / 100 | 22 | 22 | 11 | 62 / 1200 | 1 |
| 10 | 2 | 123 | 1 | 11 | 2 | 8 | 0 | 21 / 200 | 126 / 200 | 7 / 100 | 49 | 136 | 25 | 226 / 1200 | 4 |
| 25 | 2 | 222 | 1 | 7 | 1 | 4 | 0 | 15 / 200 | 199 / 200 | 5 / 100 | 34 | 204 | 17 | 274 / 1200 | 5 |
| 50 | 3 | 232 | 1 | 7 | 1 | 4 | 0 | 13 / 200 | 181 / 200 | 6 / 100 | 31 | 191 | 18 | 264 / 1200 | 7 |
| 100 | 3 | 217 | 1 | 7 | 1 | 4 | 0 | 13 / 200 | 177 / 200 | 6 / 100 | 31 | 183 | 19 | 259 / 1200 | 8 |
| 150 | 4 | 204 | 1 | 8 | 2 | 4 | 0 | 16 / 200 | 195 / 200 | 8 / 100 | 35 | 197 | 20 | 278 / 1200 | 8 |

Mémoire moyenne, en Mo.

| Utilisateurs | nginx | api | worker | mysql | redis | elasticsearch | mailpit | vm-donnees (total) | vm-metier (total) | vm-presentation (total) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 4 | 525 | 61 | 173 | 7 | 981 | 26 | 1404 | 932 | 175 |
| 10 | 4 | 588 | 61 | 199 | 7 | 982 | 26 | 1421 | 1041 | 176 |
| 25 | 4 | 779 | 57 | 218 | 7 | 982 | 7 | 1444 | 1079 | 176 |
| 50 | 4 | 1057 | 56 | 224 | 7 | 982 | 7 | 1440 | 1129 | 176 |
| 100 | 5 | 788 | 56 | 227 | 7 | 982 | 7 | 1452 | 1038 | 177 |
| 150 | 6 | 944 | 57 | 229 | 7 | 982 | 7 | 1444 | 1203 | 179 |

Base de données et incidents (« connexions max » : record depuis le démarrage de MySQL).

| Utilisateurs | Connexions MySQL (moy. / max) | Requêtes SQL/s | InnoDB lu (ko/s) | InnoDB écrit (ko/s) | Disque de la base, écrit (ko/s) | Événements |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 8 / 8 | 6 | 0 | 4 | 24 | retour_au_repos_s 10 |
| 10 | 14 / 15 | 25 | 0 | 1 | 48 | retour_au_repos_s 10 |
| 25 | 20 / 35 | 37 | 0 | 0 | 47 | workers_relances 9, erreurs_nginx 178, vm-metier_tues_memoire 6, retour_au_repos_s 11 |
| 50 | 20 / 43 | 32 | 0 | 0 | 34 | workers_relances 25, erreurs_nginx 1549, vm-metier_tues_memoire 16, retour_au_repos_s 10 |
| 100 | 20 / 43 | 28 | 0 | 0 | 18 | workers_relances 19, erreurs_nginx 2033, vm-metier_tues_memoire 12, retour_au_repos_s 11 |
| 150 | 26 / 56 | 39 | 0 | 0 | 23 | workers_relances 21, erreurs_nginx 1755, vm-metier_tues_memoire 13, retour_au_repos_s 10 |

### Saturation

- Débit maximal soutenu (moins de 1 % d'erreurs) : **7.4 req/s** à 10 utilisateurs (p95 625 ms).
- Point de saturation : **10 utilisateurs**.
- Ressource la plus chargée à ce palier : vm-metier : processeur à 63 % de ses 2 cœurs (api 123 %, mysql 11 %, elasticsearch 8 % d’un cœur) — à confirmer avec les relevés ci-dessus avant de nommer le goulot d'étranglement.

## Trois conteneurs (docker)

Configuration : `docker-configuration.txt` — cible http://localhost:80, montée 10 s, plateau 60 s, commit 6ac9106.

### Côté client

| Utilisateurs | Effectifs | Débit (req/s) | Réussies (req/s) | Parcours/s | Médiane (ms) | p90 (ms) | p95 (ms) | p99 (ms) | p95 1-Connexion (ms) | p95 2-Titres-likes (ms) | Erreurs 1-Connexion | Erreurs 2-Titres-likes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 1.0 | 1.0 | 0.5 | 8 | 76 | 78 | 131 | 84 | 8 | 0.0 % | 0.0 % |
| 10 | 10 | 9.6 | 9.6 | 4.8 | 13 | 76 | 84 | 111 | 88 | 10 | 0.0 % | 0.0 % |
| 25 | 25 | 23.7 | 23.7 | 11.8 | 56 | 93 | 107 | 140 | 128 | 12 | 0.0 % | 0.0 % |
| 50 | 50 | 45.7 | 45.7 | 22.9 | 62 | 232 | 309 | 397 | 362 | 35 | 0.0 % | 0.0 % |
| 100 | 100 | 53.5 | 53.5 | 26.8 | 608 | 2055 | 2303 | 2805 | 2529 | 210 | 0.0 % | 0.0 % |
| 150 | 150 | 52.1 | 52.1 | 26.0 | 1741 | 4211 | 4601 | 5256 | 4915 | 1533 | 0.0 % | 0.0 % |

### Côté serveur

Processeur moyen sur la fenêtre de mesure, en % d'un cœur (200 = deux cœurs pleins) ; « total » : utilisé / disponible ; « vue de l'hôte » : le processus de la VM dans WSL, virtualisation comprise.

| Utilisateurs | nginx | api | worker | mysql | redis | elasticsearch | kibana | mailpit | hôte (total) | JMeter |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 9 | 0 | 1 | 0 | 3 | 2 | 0 | 120 / 1200 | 1 |
| 10 | 1 | 106 | 0 | 2 | 0 | 8 | 3 | 0 | 141 / 1200 | 4 |
| 25 | 1 | 280 | 0 | 6 | 1 | 5 | 4 | 0 | 323 / 1200 | 7 |
| 50 | 4 | 714 | 0 | 7 | 1 | 5 | 6 | 0 | 741 / 1200 | 14 |
| 100 | 5 | 1087 | 0 | 14 | 1 | 10 | 7 | 0 | 1159 / 1200 | 18 |
| 150 | 5 | 1121 | 0 | 10 | 2 | 10 | 7 | 0 | 1170 / 1200 | 20 |

Mémoire moyenne, en Mo.

| Utilisateurs | nginx | api | worker | mysql | redis | elasticsearch | kibana | mailpit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 16 | 881 | 63 | 635 | 7 | 3253 | 543 | 11 |
| 10 | 17 | 879 | 63 | 636 | 7 | 3250 | 543 | 11 |
| 25 | 17 | 908 | 63 | 636 | 7 | 3249 | 544 | 12 |
| 50 | 17 | 1114 | 63 | 636 | 7 | 3250 | 544 | 11 |
| 100 | 18 | 3010 | 63 | 638 | 7 | 3251 | 544 | 11 |
| 150 | 18 | 4520 | 62 | 621 | 7 | 3247 | 540 | 11 |

Base de données et incidents (« connexions max » : record depuis le démarrage de MySQL).

| Utilisateurs | Connexions MySQL (moy. / max) | Requêtes SQL/s | InnoDB lu (ko/s) | InnoDB écrit (ko/s) | Disque de la base, écrit (ko/s) | Événements |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 32 / 93 | 7 | 0 | 0 | 0 | retour_au_repos_s 10 |
| 10 | 32 / 93 | 33 | 0 | 0 | 0 | retour_au_repos_s 10 |
| 25 | 32 / 93 | 75 | 0 | 0 | 0 | retour_au_repos_s 10 |
| 50 | 32 / 93 | 141 | 0 | 0 | 0 | retour_au_repos_s 10 |
| 100 | 62 / 93 | 178 | 0 | 0 | 0 | retour_au_repos_s 10 |
| 150 | 87 / 93 | 165 | 0 | 0 | 440 | retour_au_repos_s 10 |

### Saturation

- Débit maximal soutenu (moins de 1 % d'erreurs) : **53.5 req/s** à 100 utilisateurs (p95 2303 ms).
- Point de saturation : **100 utilisateurs**.
- Ressource la plus chargée à ce palier : hôte : processeur à 97 % de ses 12 cœurs (api 1087 %, mysql 14 %, elasticsearch 10 % d’un cœur) — à confirmer avec les relevés ci-dessus avant de nommer le goulot d'étranglement.

## Tableau de synthèse

| Grandeur | Trois machines virtuelles | Trois conteneurs |
|---|---|---|
| Débit maximal soutenu | 7.4 req/s (10 utilisateurs) | 53.5 req/s (100 utilisateurs) |
| Charge au point de saturation | 10 utilisateurs | 100 utilisateurs |
| Latence au 95e centile, à charge égale (10 utilisateurs) | 625 ms | 84 ms |
| Goulot d'étranglement identifié | à nommer (indice : vm-metier : processeur à 63 % de ses 2 cœurs (api 123 %, mysql 11 %, elasticsearch 8 % d’un cœur)) | à nommer (indice : hôte : processeur à 97 % de ses 12 cœurs (api 1087 %, mysql 14 %, elasticsearch 10 % d’un cœur)) |
| Temps de démarrage complet | 109.1 s (charge/resultats/repos/vm.txt) | 17.1 s (charge/resultats/repos/docker.txt) |
| Mémoire consommée au repos | 3621 Mo (charge/resultats/repos/vm.txt) | 4899 Mo (charge/resultats/repos/docker.txt) |

Latence au 95e centile à chaque palier commun :

| Utilisateurs | 3 VM (ms) | 3 conteneurs (ms) | Conteneurs par rapport aux VM |
|---|---:|---:|---:|
| 1 | 200 | 78 | -61 % |
| 10 | 625 | 84 | -87 % |
| 25 | 3121 | 107 | -97 % |
| 50 | 4629 | 309 | -93 % |
| 100 | 11920 | 2303 | -81 % |
| 150 | 30031 | 4601 | -85 % |

## Graphiques

![Débit](debit.svg)

![Latence au 95e centile](latence-p95.svg)

![Taux d'erreur](erreurs.svg)
