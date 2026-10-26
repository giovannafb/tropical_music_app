# Série « controle-1 » : synthèse

Généré par `python3 charge/analyser.py rapport controle-1` à partir des fichiers bruts de ce dossier. Chaque chiffre ne porte que sur la fenêtre de mesure de son palier (montée exclue).

## Trois conteneurs (docker)

Configuration : `docker-configuration.txt` — cible http://localhost:80, montée 10 s, plateau 60 s, commit 6ac9106.

### Côté client

| Utilisateurs | Effectifs | Débit (req/s) | Réussies (req/s) | Parcours/s | Médiane (ms) | p90 (ms) | p95 (ms) | p99 (ms) | p95 1-Connexion (ms) | p95 2-Titres-likes (ms) | Erreurs 1-Connexion | Erreurs 2-Titres-likes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 1.0 | 1.0 | 0.5 | 8 | 68 | 71 | 107 | 74 | 7 | 0.0 % | 0.0 % |
| 10 | 10 | 9.8 | 9.8 | 4.9 | 52 | 71 | 75 | 93 | 82 | 8 | 0.0 % | 0.0 % |
| 25 | 25 | 23.9 | 23.9 | 12.0 | 30 | 95 | 115 | 160 | 136 | 13 | 0.0 % | 0.0 % |
| 50 | 50 | 45.8 | 45.8 | 22.9 | 60 | 225 | 326 | 549 | 439 | 32 | 0.0 % | 0.0 % |
| 100 | 100 | 55.1 | 55.1 | 27.7 | 544 | 1914 | 2254 | 2753 | 2470 | 218 | 0.0 % | 0.0 % |
| 150 | 150 | 52.9 | 52.9 | 26.4 | 1651 | 4019 | 4483 | 5236 | 4859 | 1383 | 0.0 % | 0.0 % |

### Côté serveur

Processeur moyen sur la fenêtre de mesure, en % d'un cœur (200 = deux cœurs pleins) ; « total » : utilisé / disponible ; « vue de l'hôte » : le processus de la VM dans WSL, virtualisation comprise.

| Utilisateurs | nginx | api | worker | mysql | redis | elasticsearch | kibana | mailpit | hôte (total) | JMeter |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 10 | 0 | 1 | 0 | 7 | 2 | 1 | 40 / 1200 | 1 |
| 10 | 1 | 83 | 0 | 1 | 0 | 5 | 2 | 0 | 134 / 1200 | 4 |
| 25 | 2 | 307 | 0 | 6 | 1 | 12 | 4 | 0 | 321 / 1200 | 7 |
| 50 | 3 | 643 | 0 | 7 | 1 | 10 | 6 | 0 | 710 / 1200 | 13 |
| 100 | 5 | 1104 | 0 | 16 | 1 | 13 | 6 | 0 | 1162 / 1200 | 17 |
| 150 | 5 | 1142 | 0 | 9 | 1 | 10 | 8 | 0 | 1168 / 1200 | 18 |

Mémoire moyenne, en Mo.

| Utilisateurs | nginx | api | worker | mysql | redis | elasticsearch | kibana | mailpit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 16 | 765 | 61 | 594 | 8 | 3444 | 628 | 21 |
| 10 | 16 | 771 | 61 | 595 | 8 | 3459 | 629 | 21 |
| 25 | 16 | 810 | 61 | 595 | 8 | 3455 | 629 | 21 |
| 50 | 16 | 915 | 61 | 595 | 8 | 3458 | 629 | 21 |
| 100 | 17 | 2712 | 61 | 600 | 8 | 3466 | 629 | 21 |
| 150 | 18 | 4757 | 61 | 611 | 8 | 3473 | 629 | 21 |

Base de données et incidents (« connexions max » : record depuis le démarrage de MySQL).

| Utilisateurs | Connexions MySQL (moy. / max) | Requêtes SQL/s | InnoDB lu (ko/s) | InnoDB écrit (ko/s) | Disque de la base, écrit (ko/s) | Événements |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 32 / 92 | 7 | 0 | 0 | 0 | retour_au_repos_s 10 |
| 10 | 32 / 92 | 33 | 0 | 0 | 0 | retour_au_repos_s 10 |
| 25 | 32 / 92 | 76 | 0 | 0 | 0 | retour_au_repos_s 10 |
| 50 | 32 / 92 | 141 | 0 | 0 | 0 | retour_au_repos_s 10 |
| 100 | 60 / 92 | 186 | 0 | 0 | 0 | retour_au_repos_s 10 |
| 150 | 87 / 92 | 168 | 0 | 0 | 0 | retour_au_repos_s 10 |

### Saturation

- Débit maximal soutenu (moins de 1 % d'erreurs) : **55.1 req/s** à 100 utilisateurs (p95 2254 ms).
- Point de saturation : **100 utilisateurs**.
- Ressource la plus chargée à ce palier : hôte : processeur à 97 % de ses 12 cœurs (api 1104 %, mysql 16 %, elasticsearch 13 % d’un cœur) — à confirmer avec les relevés ci-dessus avant de nommer le goulot d'étranglement.

## Graphiques

![Débit](debit.svg)

![Latence au 95e centile](latence-p95.svg)

![Taux d'erreur](erreurs.svg)
