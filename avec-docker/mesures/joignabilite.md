# Version Docker — matrice de joignabilité (étape 14)

Relevée le 26/10/2026 à 21:53 par `bash avec-docker/joignabilite.sh`, tous les conteneurs en marche
(une tentative qui échoue échoue donc faute de route, et non parce qu'un service est arrêté).
Depuis un conteneur, chaque service est appelé par son nom (DNS interne de Docker) ; en gras, un écart à l'attendu du sujet.

| Depuis | vers proxy :80 | vers métier :8000 | vers base :3306 |
|---|:---:|:---:|:---:|
| **L'hôte** (ports publiés, 127.0.0.1) | oui | non | non |
| **conteneur nginx** (proxy) | — | oui | **oui** (attendu : non) |
| **conteneur api** (métier) | oui | — | oui |
| **conteneur mysql** (données) | **oui** (attendu : non) | oui | — |

Depuis l'hôte, par l'adresse du conteneur sur le pont Docker (le moteur tourne ici dans Ubuntu, qui a une route vers ce pont ;
avec Docker Desktop, ces adresses ne sont pas joignables depuis Windows) : api 172.18.0.10:8000 : **oui** (attendu : non) ; mysql 172.18.0.5:3306 : **oui** (attendu : non).

## Ports publiés (`docker compose ps`)

```
musicapp-api-1           8000/tcp
musicapp-api-2           8000/tcp
musicapp-api-3           8000/tcp
musicapp-es01-1          9200/tcp, 9300/tcp
musicapp-es02-1          9200/tcp, 9300/tcp
musicapp-es03-1          9200/tcp, 9300/tcp
musicapp-kibana-1        0.0.0.0:5601->5601/tcp, [::]:5601->5601/tcp
musicapp-mailpit-1       1025/tcp, 1110/tcp, 0.0.0.0:8025->8025/tcp, [::]:8025->8025/tcp
musicapp-mysql-1         3306/tcp, 33060/tcp
musicapp-nginx-1         0.0.0.0:80->80/tcp, [::]:80->80/tcp
musicapp-redis-1         6379/tcp
musicapp-worker-1        8000/tcp
```

## Réseaux du projet (`docker network inspect`)

```
musicapp_default :  api-1 api-2 api-3 es01-1 es02-1 es03-1 kibana-1 mailpit-1 mysql-1 nginx-1 redis-1 worker-1 
```
