# MusicApp — version Docker : vérification et mesures (étape 14)

Relevés du 26 octobre 2026, sur le même poste et dans la même séance que la version VM (`avec-vm/mesures.md`), avec le même protocole. Le compte rendu comparatif est dans [`../docs/comparaison.md`](../docs/comparaison.md).

| Livrable de l'étape 14 | Où le trouver | Commande |
|---|---|---|
| Matrice de joignabilité remplie | partie 1 ; détail (ports publiés, réseaux) dans [`mesures/joignabilite.md`](mesures/joignabilite.md) | `bash avec-docker/joignabilite.sh` |
| Tableau comparatif chiffré | partie 2, et [`../docs/comparaison.md`](../docs/comparaison.md) ; brut dans [`../charge/resultats/repos/docker.txt`](../charge/resultats/repos/docker.txt) | `bash charge/repos.sh docker` |
| Taille des images | [`mesures/images.txt`](mesures/images.txt) | `docker image ls` |
| Compte rendu de deux pages | [`../docs/comparaison.md`](../docs/comparaison.md) | — |

## 1. Matrice de joignabilité

Tous les conteneurs en marche. Depuis un conteneur, chaque service est appelé par son nom (DNS interne de Docker).

| Depuis | vers proxy :80 | vers métier :8000 | vers base :3306 |
|---|:---:|:---:|:---:|
| **L'hôte** (ports publiés) | oui | non | non |
| **conteneur nginx** (proxy) | — | oui | **oui** (attendu : non) |
| **conteneur api** (métier) | oui | — | oui |
| **conteneur mysql** (données) | **oui** (attendu : non) | oui | — |

**Deux cases « doit échouer » réussissent.** Le sujet demande deux réseaux : le proxy et le métier sur le premier, le métier et la base sur le second. Or `docker-compose.yml` n'en déclare aucun. Les douze conteneurs partagent donc le réseau par défaut `musicapp_default`, et le proxy joint la base. C'est précisément le cas que le sujet annonce plus strict qu'en VM, et c'est le seul point où cette version est **moins** isolée que la version VM, où le pare-feu bloque ce flux.

Les deux autres interdits de l'étape 14 :
- **« Aucun port n'est publié en dehors de celui du proxy »** : non respecté. Kibana (5601) et Mailpit (8025) sont publiés sur toutes les interfaces de l'hôte (`0.0.0.0`), en plus de Nginx (80). MySQL, Redis, Elasticsearch et l'API ne le sont pas.
- **« Le client ne s'adresse jamais au service métier directement »** : respecté. Le client n'appelle que `/api/…` sur le proxy.

Le moteur Docker tourne ici dans Ubuntu (WSL), et non dans Docker Desktop. L'hôte a donc une route vers le pont Docker, et il joint les conteneurs **par leur adresse** (`172.18.0.x`), publiés ou non. Avec Docker Desktop, ces adresses ne seraient pas joignables depuis Windows.

La correction tient en quelques lignes, sans toucher au code :
- déclarer deux réseaux (`frontal` : nginx, api ; `interne` : api, worker, mysql, redis, Elasticsearch) ;
- ne publier Kibana et Mailpit que sur `127.0.0.1`, ou pas du tout.

## 2. Mesures, dans les mêmes conditions qu'à l'étape 10

Protocole identique à la version VM : trois exécutions, médiane retenue (`bash charge/repos.sh docker`). La mémoire est mesurée dans la VM de WSL 2, qui héberge le moteur Docker : **le moteur est compté**, puisque la mesure à vide est faite conteneurs arrêtés, mémoire de `dockerd` et `containerd` retirée.

| Grandeur | Comment elle est relevée | Exécutions | **Médiane** | Trois VM (étape 10) |
|---|---|---|---|---|
| **Temps de démarrage** | des conteneurs arrêtés au parcours connexion + consultation des likes réussi à travers le proxy | 12,8 ; 18,5 ; 17,1 s | **17,1 s** | 109,1 s |
| **Mémoire consommée** | mémoire utilisée de la VM de WSL 2 au repos depuis 60 s, moins la même mesure conteneurs arrêtés et hors moteur (1 371 Mo) | 4 899 ; 4 879 ; 4 911 Mo | **4 899 Mo** | 3 621 Mo |
| **Empreinte disque** | images du projet et volumes | — | **6 654 Mo** (5 952 Mo d'images, 702 Mo de volumes) | 10 148 Mo |
| **Latence applicative** | dix appels à `GET /api/me/likes/tracks`, session ouverte, au repos, médiane des dix | 6,3 ; 7,3 ; 5,7 ms | **6,3 ms** | 26,5 ms |
| **Temps de mise en place** | de la création de `avec-docker/.env` (17 h 30 min 42 s) à la création du compte admin (17 h 33 min 18 s) : construction des images, téléchargement des images de base, démarrage | — | **2 min 36 s** | 4 min 19 s |

**La mémoire est plus élevée qu'en VM, parce que la pile n'est pas la même.** Mémoire par conteneur, relevée par `docker stats` au palier d'un utilisateur de `charge/resultats/serie-1/` :

| Service | Conteneurs | Mémoire |
|---|---|---:|
| Elasticsearch | 3 nœuds (1 seul en VM) | 3 253 Mo |
| API | 3 instances | 881 Mo |
| MySQL | 1 | 635 Mo |
| Kibana | 1 (absent en VM) | 543 Mo |
| worker, Nginx, Mailpit, Redis | 4 | 97 Mo |

Les deux nœuds Elasticsearch supplémentaires et Kibana pèsent à eux seuls environ 2,7 Go. Sans eux, la version Docker consommerait environ 2,2 Go au repos, contre 3,6 Go pour les trois VM. C'est une **estimation**, obtenue en retirant ces conteneurs du total mesuré.

De même pour le disque : l'image de Kibana pèse 1,85 Go, et elle est absente de la version VM.

Conditions : le poste servait aussi à d'autres tâches pendant cette mesure. La charge moyenne de l'hôte était de 2,5 à 3,1, contre 0,6 à 0,9 pendant la mesure des VM. Les temps de démarrage et la latence de Docker sont donc plutôt défavorisés.

## 3. Configuration qui a produit ces chiffres

| Élément | Valeur |
|---|---|
| Poste | identique à l'étape 10 (`avec-vm/mesures.md`) |
| Moteur | Docker Engine (docker-ce) installé dans Ubuntu (WSL 2), et non Docker Desktop |
| Conteneurs | nginx 1.27-alpine, api ×3 et worker (python:3.12-slim), MySQL 8.4, Redis 7, Elasticsearch 8.15.3 ×3 (512 Mo de tas chacun), Kibana 8.15.3, Mailpit |
| Limites | aucune limite de processeur ni de mémoire sur les conteneurs |
| Jeu de données | import FMA `--limit 500` ; empreinte du catalogue `7d7618aa71d1a0dd`, identique à la version VM |
