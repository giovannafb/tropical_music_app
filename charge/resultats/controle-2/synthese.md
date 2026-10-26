# Série « controle-2 » : synthèse

Généré par `python3 charge/analyser.py rapport controle-2` à partir des fichiers bruts de ce dossier. Chaque chiffre ne porte que sur la fenêtre de mesure de son palier (montée exclue).

## Trois conteneurs (docker)

Configuration : `docker-configuration.txt` — cible http://localhost:80, montée 10 s, plateau 60 s, commit 6ac9106.

### Côté client

| Utilisateurs | Effectifs | Débit (req/s) | Réussies (req/s) | Parcours/s | Médiane (ms) | p90 (ms) | p95 (ms) | p99 (ms) | p95 1-Connexion (ms) | p95 2-Titres-likes (ms) | Erreurs 1-Connexion | Erreurs 2-Titres-likes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 0.9 | 0.9 | 0.5 | 56 | 67 | 68 | 74 | 70 | 8 | 0.0 % | 0.0 % |
| 10 | 10 | 9.5 | 9.5 | 4.8 | 12 | 70 | 75 | 88 | 80 | 8 | 0.0 % | 0.0 % |
| 25 | 25 | 23.9 | 23.9 | 11.9 | 61 | 103 | 123 | 186 | 141 | 14 | 0.0 % | 0.0 % |
| 50 | 50 | 46.7 | 46.7 | 23.3 | 57 | 213 | 259 | 367 | 306 | 31 | 0.0 % | 0.0 % |
| 100 | 100 | 46.7 | 46.7 | 23.3 | 449 | 3392 | 4060 | 5286 | 4674 | 338 | 0.0 % | 0.0 % |
| 150 | 150 | 43.2 | 43.2 | 21.8 | 2149 | 5513 | 6116 | 7400 | 6725 | 2304 | 0.0 % | 0.0 % |

### Côté serveur

Processeur moyen sur la fenêtre de mesure, en % d'un cœur (200 = deux cœurs pleins) ; « total » : utilisé / disponible ; « vue de l'hôte » : le processus de la VM dans WSL, virtualisation comprise.

| Utilisateurs | nginx | api | worker | mysql | redis | elasticsearch | kibana | mailpit | hôte (total) | JMeter |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 10 | 0 | 1 | 0 | 4 | 2 | 0 | 41 / 1200 | 1 |
| 10 | 1 | 85 | 0 | 1 | 0 | 6 | 3 | 0 | 129 / 1200 | 4 |
| 25 | 2 | 273 | 0 | 4 | 1 | 7 | 4 | 2 | 340 / 1200 | 7 |
| 50 | 3 | 681 | 0 | 7 | 1 | 8 | 7 | 2 | 715 / 1200 | 12 |
| 100 | 6 | 1209 | 1 | 16 | 2 | 17 | 10 | 3 | 1143 / 1200 | 17 |
| 150 | 6 | 1192 | 0 | 14 | 1 | 16 | 9 | 0 | 1141 / 1200 | 19 |

Mémoire moyenne, en Mo.

| Utilisateurs | nginx | api | worker | mysql | redis | elasticsearch | kibana | mailpit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 16 | 833 | 61 | 616 | 8 | 3475 | 630 | 21 |
| 10 | 16 | 821 | 61 | 617 | 8 | 3477 | 630 | 21 |
| 25 | 16 | 887 | 61 | 618 | 8 | 3483 | 630 | 21 |
| 50 | 17 | 1043 | 61 | 617 | 8 | 3485 | 631 | 21 |
| 100 | 18 | 3074 | 61 | 621 | 8 | 3487 | 634 | 21 |
| 150 | 19 | 4811 | 61 | 633 | 8 | 3489 | 636 | 21 |

Base de données et incidents (« connexions max » : record depuis le démarrage de MySQL).

| Utilisateurs | Connexions MySQL (moy. / max) | Requêtes SQL/s | InnoDB lu (ko/s) | InnoDB écrit (ko/s) | Disque de la base, écrit (ko/s) | Événements |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 32 / 92 | 7 | 0 | 0 | 0 | retour_au_repos_s 11 |
| 10 | 32 / 92 | 33 | 0 | 0 | 0 | retour_au_repos_s 10 |
| 25 | 32 / 92 | 76 | 0 | 0 | 0 | retour_au_repos_s 10 |
| 50 | 32 / 92 | 144 | 0 | 0 | 0 | retour_au_repos_s 10 |
| 100 | 65 / 92 | 162 | 0 | 0 | 0 | retour_au_repos_s 10 |
| 150 | 89 / 92 | 138 | 0 | 0 | 0 | retour_au_repos_s 10 |

### Saturation

- Débit maximal soutenu (moins de 1 % d'erreurs) : **46.7 req/s** à 50 utilisateurs (p95 259 ms).
- Point de saturation : **50 utilisateurs**.
- Ressource la plus chargée à ce palier : hôte : processeur à 60 % de ses 12 cœurs (api 681 %, elasticsearch 8 %, mysql 7 % d’un cœur) — à confirmer avec les relevés ci-dessus avant de nommer le goulot d'étranglement.

## Graphiques

![Débit](debit.svg)

![Latence au 95e centile](latence-p95.svg)

![Taux d'erreur](erreurs.svg)
