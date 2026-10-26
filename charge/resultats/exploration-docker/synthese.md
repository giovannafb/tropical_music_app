# Série « controle-1 » : synthèse

Généré par `python3 charge/analyser.py rapport controle-1` à partir des fichiers bruts de ce dossier. Chaque chiffre ne porte que sur la fenêtre de mesure de son palier (montée exclue).

## Trois conteneurs (docker)

Configuration : `docker-configuration.txt` — cible http://localhost:80, montée 30 s, plateau 90 s, commit 6ac9106.

### Côté client

| Utilisateurs | Effectifs | Débit (req/s) | Réussies (req/s) | Parcours/s | Médiane (ms) | p90 (ms) | p95 (ms) | p99 (ms) | p95 1-Connexion (ms) | p95 2-Titres-likes (ms) | Erreurs 1-Connexion | Erreurs 2-Titres-likes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 0.9 | 0.9 | 0.5 | 61 | 73 | 77 | 101 | 80 | 8 | 0.0 % | 0.0 % |
| 5 | 5 | 4.9 | 4.9 | 2.4 | 59 | 84 | 99 | 142 | 116 | 14 | 0.0 % | 0.0 % |
| 10 | 10 | 9.3 | 9.3 | 4.7 | 64 | 186 | 243 | 459 | 330 | 25 | 0.0 % | 0.0 % |
| 25 | 25 | 24.0 | 24.0 | 12.0 | 62 | 118 | 151 | 236 | 182 | 17 | 0.0 % | 0.0 % |
| 50 | 50 | 45.9 | 45.9 | 22.9 | 65 | 266 | 358 | 641 | 460 | 40 | 0.0 % | 0.0 % |
| 100 | 100 | 49.2 | 49.2 | 24.7 | 540 | 2584 | 3126 | 4267 | 3646 | 346 | 0.0 % | 0.0 % |
| 150 | 150 | 52.4 | 52.4 | 26.3 | 1638 | 3998 | 4436 | 5273 | 4852 | 1368 | 0.0 % | 0.0 % |
| 200 | 200 | 53.6 | 53.6 | 26.8 | 2661 | 5479 | 6109 | 7490 | 6590 | 3385 | 0.0 % | 0.0 % |
| 300 | 300 | 57.5 | 51.4 | 25.5 | 1208 | 30013 | 30030 | 30033 | 30031 | 30028 | 14.2 % | 6.6 % |
| 400 | 400 | 37.8 | 25.6 | 11.5 | 121 | 30030 | 30031 | 30032 | 30031 | 30030 | 38.5 % | 22.4 % |

Principales causes d'erreur :

- 300 utilisateurs : Non HTTP response code: java.net.SocketTimeoutException Connexion refusée : le code de retour n'est pas 200 (385)
- 300 utilisateurs : Non HTTP response code: java.net.SocketTimeoutException Consultation refusée : le code de retour n'est pas 200 (162)
- 400 utilisateurs : Non HTTP response code: java.net.SocketTimeoutException Connexion refusée : le code de retour n'est pas 200 (797)
- 400 utilisateurs : Non HTTP response code: java.net.SocketTimeoutException Consultation refusée : le code de retour n'est pas 200 (298)

### Côté serveur

Processeur moyen sur la fenêtre de mesure, en % d'un cœur (200 = deux cœurs pleins) ; « total » : utilisé / disponible ; « vue de l'hôte » : le processus de la VM dans WSL, virtualisation comprise.

| Utilisateurs | nginx | api | worker | mysql | redis | elasticsearch | kibana | mailpit | hôte (total) | JMeter |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 10 | 0 | 1 | 0 | 7 | 2 | 0 | 46 / 1200 | 1 |
| 5 | 0 | 42 | 0 | 1 | 1 | 5 | 4 | 1 | 95 / 1200 | 2 |
| 10 | 1 | 163 | 0 | 3 | 1 | 15 | 6 | 0 | 216 / 1200 | 6 |
| 25 | 2 | 284 | 0 | 3 | 1 | 5 | 4 | 0 | 358 / 1200 | 6 |
| 50 | 4 | 718 | 0 | 8 | 1 | 9 | 7 | 0 | 780 / 1200 | 11 |
| 100 | 5 | 1116 | 1 | 13 | 2 | 21 | 8 | 4 | 1147 / 1200 | 12 |
| 150 | 5 | 1110 | 0 | 9 | 1 | 8 | 7 | 0 | 1164 / 1200 | 17 |
| 200 | 5 | 1096 | 0 | 12 | 1 | 9 | 7 | 0 | 1161 / 1200 | 16 |
| 300 | 5 | 1035 | 0 | 9 | 1 | 9 | 7 | 0 | 1081 / 1200 | 16 |
| 400 | 3 | 426 | 0 | 4 | 1 | 8 | 5 | 0 | 485 / 1200 | 8 |

Mémoire moyenne, en Mo.

| Utilisateurs | nginx | api | worker | mysql | redis | elasticsearch | kibana | mailpit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 17 | 570 | 61 | 476 | 7 | 3320 | 579 | 11 |
| 5 | 17 | 596 | 61 | 480 | 7 | 3335 | 582 | 11 |
| 10 | 17 | 603 | 61 | 500 | 7 | 3347 | 583 | 11 |
| 25 | 17 | 633 | 61 | 525 | 8 | 3351 | 585 | 11 |
| 50 | 17 | 786 | 61 | 538 | 8 | 3361 | 586 | 11 |
| 100 | 16 | 2775 | 61 | 574 | 8 | 3303 | 542 | 11 |
| 150 | 17 | 4618 | 62 | 592 | 8 | 3243 | 535 | 11 |
| 200 | 18 | 4778 | 62 | 606 | 9 | 3242 | 536 | 11 |
| 300 | 20 | 2782 | 62 | 615 | 10 | 3241 | 536 | 11 |
| 400 | 21 | 1033 | 62 | 620 | 10 | 3242 | 536 | 11 |

Base de données et incidents (« connexions max » : record depuis le démarrage de MySQL).

| Utilisateurs | Connexions MySQL (moy. / max) | Requêtes SQL/s | InnoDB lu (ko/s) | InnoDB écrit (ko/s) | Disque de la base, écrit (ko/s) | Événements |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 7 / 7 | 7 | 0 | 0 | 0 | aucun |
| 5 | 10 / 10 | 19 | 0 | 0 | 0 | aucun |
| 10 | 13 / 15 | 32 | 0 | 0 | 0 | aucun |
| 25 | 17 / 18 | 76 | 0 | 0 | 0 | aucun |
| 50 | 30 / 32 | 142 | 0 | 0 | 0 | aucun |
| 100 | 64 / 92 | 173 | 0 | 0 | 0 | aucun |
| 150 | 88 / 92 | 167 | 0 | 0 | 0 | aucun |
| 200 | 89 / 92 | 169 | 0 | 0 | 0 | aucun |
| 300 | 75 / 93 | 172 | 0 | 0 | 0 | aucun |
| 400 | 63 / 93 | 85 | 0 | 0 | 0 | aucun |

### Saturation

- Débit maximal soutenu (moins de 1 % d'erreurs) : **53.6 req/s** à 200 utilisateurs (p95 6109 ms).
- Point de saturation : **50 utilisateurs**.
- Ressource la plus chargée à ce palier : hôte : processeur à 65 % de ses 12 cœurs (api 718 %, elasticsearch 9 %, mysql 8 % d’un cœur) — à confirmer avec les relevés ci-dessus avant de nommer le goulot d'étranglement.

## Graphiques

![Débit](debit.svg)

![Latence au 95e centile](latence-p95.svg)

![Taux d'erreur](erreurs.svg)
