# Série « etalonnage » : synthèse

Généré par `python3 charge/analyser.py rapport etalonnage` à partir des fichiers bruts de ce dossier. Chaque chiffre ne porte que sur la fenêtre de mesure de son palier (montée exclue).

## Trois machines virtuelles (vm)

Configuration : `vm-configuration.txt` — cible http://192.168.56.11:80, montée 10 s, plateau 60 s, commit 6ac9106.

### Côté client

| Utilisateurs | Effectifs | Débit (req/s) | Réussies (req/s) | Parcours/s | Médiane (ms) | p90 (ms) | p95 (ms) | p99 (ms) | p95 Ressource-statique (ms) | Erreurs Ressource-statique |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 10 | 4597.3 | 4597.3 | 4597.3 | 2 | 3 | 3 | 5 | 3 | 0.0 % |
| 50 | 50 | 4472.8 | 4472.8 | 4472.8 | 11 | 14 | 15 | 21 | 15 | 0.0 % |
| 100 | 100 | 4364.9 | 4364.9 | 4364.9 | 22 | 28 | 32 | 47 | 32 | 0.0 % |
| 200 | 200 | 3566.1 | 3566.1 | 3566.1 | 55 | 69 | 74 | 87 | 74 | 0.0 % |

### Côté serveur

Processeur moyen sur la fenêtre de mesure, en % d'un cœur (200 = deux cœurs pleins) ; « total » : utilisé / disponible ; « vue de l'hôte » : le processus de la VM dans WSL, virtualisation comprise.

| Utilisateurs | nginx | api | worker | mysql | redis | elasticsearch | mailpit | vm-donnees (total) | vm-metier (total) | vm-presentation (total) | vm-donnees vue de l'hôte | vm-metier vue de l'hôte | vm-presentation vue de l'hôte | hôte (total) | JMeter |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 99 | 10 | 3 | 6 | 3 | 8 | 0 | 18 / 200 | 15 / 200 | 100 / 100 | 32 | 28 | 135 | 262 / 1200 | 46 |
| 50 | 100 | 11 | 3 | 6 | 3 | 8 | 0 | 18 / 200 | 18 / 200 | 100 / 100 | 33 | 32 | 136 | 275 / 1200 | 52 |
| 100 | 100 | 12 | 4 | 7 | 3 | 11 | 0 | 22 / 200 | 20 / 200 | 100 / 100 | 38 | 34 | 135 | 286 / 1200 | 52 |
| 200 | 100 | 12 | 3 | 7 | 3 | 9 | 0 | 19 / 200 | 18 / 200 | 100 / 100 | 34 | 34 | 136 | 269 / 1200 | 45 |

Mémoire moyenne, en Mo.

| Utilisateurs | nginx | api | worker | mysql | redis | elasticsearch | mailpit | vm-donnees (total) | vm-metier (total) | vm-presentation (total) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 3 | 530 | 66 | 141 | 4 | 954 | 6 | 1446 | 966 | 192 |
| 50 | 4 | 530 | 66 | 141 | 4 | 954 | 6 | 1455 | 959 | 185 |
| 100 | 6 | 530 | 66 | 141 | 4 | 954 | 6 | 1457 | 947 | 181 |
| 200 | 7 | 530 | 66 | 141 | 4 | 954 | 6 | 1454 | 946 | 182 |

Base de données et incidents (« connexions max » : record depuis le démarrage de MySQL).

| Utilisateurs | Connexions MySQL (moy. / max) | Requêtes SQL/s | InnoDB lu (ko/s) | InnoDB écrit (ko/s) | Disque de la base, écrit (ko/s) | Événements |
|---|---:|---:|---:|---:|---:|---:|
| 10 | 7 / 7 | 4 | 0 | 62 | 154 | aucun |
| 50 | 7 / 7 | 4 | 0 | 0 | 17 | aucun |
| 100 | 7 / 7 | 3 | 0 | 0 | 45 | aucun |
| 200 | 7 / 7 | 3 | 0 | 0 | 5 | aucun |

### Saturation

- Débit maximal soutenu (moins de 1 % d'erreurs) : **4597.3 req/s** à 10 utilisateurs (p95 3 ms).
- Point de saturation : **10 utilisateurs**.
- Ressource la plus chargée à ce palier : vm-presentation : processeur à 100 % de ses 1 cœurs (nginx 99 %, api 10 %, elasticsearch 8 % d’un cœur) — à confirmer avec les relevés ci-dessus avant de nommer le goulot d'étranglement.

## Trois conteneurs (docker)

Configuration : `docker-configuration.txt` — cible http://localhost:80, montée 10 s, plateau 60 s, commit 6ac9106.

### Côté client

| Utilisateurs | Effectifs | Débit (req/s) | Réussies (req/s) | Parcours/s | Médiane (ms) | p90 (ms) | p95 (ms) | p99 (ms) | p95 Ressource-statique (ms) | Erreurs Ressource-statique |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 10 | 19639.8 | 19639.8 | 19639.8 | 0 | 1 | 1 | 1 | 1 | 0.0 % |
| 50 | 50 | 39313.0 | 39313.0 | 39313.0 | 1 | 2 | 3 | 4 | 3 | 0.0 % |
| 100 | 100 | 43152.9 | 43152.9 | 43152.9 | 2 | 4 | 6 | 9 | 6 | 0.0 % |
| 200 | 200 | 40191.5 | 40191.5 | 40191.5 | 3 | 10 | 13 | 20 | 13 | 0.0 % |

### Côté serveur

Processeur moyen sur la fenêtre de mesure, en % d'un cœur (200 = deux cœurs pleins) ; « total » : utilisé / disponible ; « vue de l'hôte » : le processus de la VM dans WSL, virtualisation comprise.

| Utilisateurs | nginx | api | worker | mysql | redis | elasticsearch | kibana | mailpit | hôte (total) | JMeter |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 172 | 1 | 0 | 1 | 0 | 22 | 5 | 1 | 719 / 1200 | 170 |
| 50 | 253 | 1 | 0 | 1 | 0 | 18 | 5 | 1 | 924 / 1200 | 313 |
| 100 | 283 | 1 | 0 | 3 | 0 | 7 | 4 | 0 | 983 / 1200 | 349 |
| 200 | 278 | 1 | 0 | 1 | 0 | 11 | 5 | 0 | 1017 / 1200 | 382 |

Mémoire moyenne, en Mo.

| Utilisateurs | nginx | api | worker | mysql | redis | elasticsearch | kibana | mailpit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 15 | 519 | 61 | 462 | 4 | 3307 | 605 | 9 |
| 50 | 15 | 518 | 61 | 462 | 4 | 3308 | 585 | 10 |
| 100 | 16 | 520 | 61 | 465 | 5 | 3318 | 583 | 10 |
| 200 | 17 | 520 | 61 | 465 | 6 | 3327 | 580 | 11 |

Base de données et incidents (« connexions max » : record depuis le démarrage de MySQL).

| Utilisateurs | Connexions MySQL (moy. / max) | Requêtes SQL/s | InnoDB lu (ko/s) | InnoDB écrit (ko/s) | Disque de la base, écrit (ko/s) | Événements |
|---|---:|---:|---:|---:|---:|---:|
| 10 | 2 / 2 | 4 | 0 | 1 | 2 | aucun |
| 50 | 2 / 2 | 4 | 0 | 0 | 0 | aucun |
| 100 | 2 / 2 | 4 | 0 | 17 | 36 | aucun |
| 200 | 2 / 2 | 4 | 0 | 0 | 0 | aucun |

### Saturation

- Débit maximal soutenu (moins de 1 % d'erreurs) : **43152.9 req/s** à 100 utilisateurs (p95 6 ms).
- Point de saturation : **50 utilisateurs**.
- Ressource la plus chargée à ce palier : hôte : processeur à 77 % de ses 12 cœurs (nginx 253 %, elasticsearch 18 %, kibana 5 % d’un cœur) — à confirmer avec les relevés ci-dessus avant de nommer le goulot d'étranglement.

## Tableau de synthèse

| Grandeur | Trois machines virtuelles | Trois conteneurs |
|---|---|---|
| Débit maximal soutenu | 4597.3 req/s (10 utilisateurs) | 43152.9 req/s (100 utilisateurs) |
| Charge au point de saturation | 10 utilisateurs | 50 utilisateurs |
| Latence au 95e centile, à charge égale (200 utilisateurs) | 74 ms | 13 ms |
| Goulot d'étranglement identifié | à nommer (indice : vm-presentation : processeur à 100 % de ses 1 cœurs (nginx 99 %, api 10 %, elasticsearch 8 % d’un cœur)) | à nommer (indice : hôte : processeur à 77 % de ses 12 cœurs (nginx 253 %, elasticsearch 18 %, kibana 5 % d’un cœur)) |
| Temps de démarrage complet | étape 10 | étape 14 |
| Mémoire consommée au repos | étape 10 | étape 14 |

Latence au 95e centile à chaque palier commun :

| Utilisateurs | 3 VM (ms) | 3 conteneurs (ms) | Conteneurs par rapport aux VM |
|---|---:|---:|---:|
| 10 | 3 | 1 | -67 % |
| 50 | 15 | 3 | -80 % |
| 100 | 32 | 6 | -81 % |
| 200 | 74 | 13 | -82 % |

## Graphiques

![Débit](debit.svg)

![Latence au 95e centile](latence-p95.svg)

![Taux d'erreur](erreurs.svg)
