# MusicApp — trois VM contre trois conteneurs : compte rendu (étape 14)

Même application, même découpage en trois couches, même jeu de données (import FMA de 500 titres, empreinte `7d7618aa71d1a0dd`), même poste, même séance (26 octobre 2026) et même protocole : trois exécutions, médiane retenue. Mesures détaillées et configuration : `avec-vm/mesures.md` et `avec-docker/mesures.md`. Le comportement sous charge (partie 4) est analysé à part, dans `charge/rapport/comparaison.md`.

## 1. De combien les chiffres diffèrent

| Grandeur | Trois VM | Trois conteneurs | Écart |
|---|---:|---:|---|
| Temps de démarrage complet | 109,1 s | 17,1 s | **6,4 fois plus court** en conteneurs |
| Mémoire consommée au repos (moteur Docker compté) | 3 621 Mo | 4 899 Mo | **+35 %** en conteneurs, mais pour une pile plus lourde ; à pile égale, environ 2,2 Go, soit **−40 %** (estimation) |
| Empreinte disque | 10 148 Mo | 6 654 Mo | **−34 %** en conteneurs |
| Latence applicative (10 consultations, médiane) | 26,5 ms | 6,3 ms | **4,2 fois plus faible** en conteneurs |
| Temps de mise en place, installation automatisée | 4 min 19 s | 2 min 36 s | **−40 %** ; hors préparation de VirtualBox sous WSL (environ 50 min de compilation de modules noyau) |
| Fichiers de déploiement | 1 211 lignes de scripts et de configuration (`avec-vm/`) | 190 lignes (`docker-compose.yml` et trois Dockerfile) | **6 fois moins** |
| Sous charge (partie 4) : débit maximal soutenu | 7,4 à 8,3 req/s | 53,5 à 55,2 req/s | facteur 7 |

Les deux piles ne sont pas strictement identiques, et deux lignes en dépendent. La version Docker fait tourner Elasticsearch sur **trois nœuds plus Kibana**, la version VM un seul nœud :
- **mémoire** : ces conteneurs en plus pèsent 2,7 Go au repos (3 253 Mo pour les trois nœuds, 543 Mo pour Kibana) ;
- **disque** : l'image de Kibana pèse 1,85 Go.

Le chiffre brut de mémoire est donc défavorable aux conteneurs, alors que le coût de l'isolation l'est aux VM.

## 2. Quelle propriété technique explique chaque écart

**Démarrage : un noyau à amorcer contre un processus à lancer.**
- Chaque VM amorce un système d'exploitation complet : micrologiciel, noyau, systemd, réseau, puis les services, et ce dans l'ordre des couches, une VM après l'autre (`demarrer.sh`).
- Un conteneur n'est qu'un processus isolé par des espaces de noms (*namespaces*) et des cgroups, sur le noyau déjà démarré de l'hôte. Le moteur lance les douze conteneurs en parallèle, et les dépendances de santé (`depends_on: condition: service_healthy`) remplacent l'attente séquentielle.
- Il reste 17 s, essentiellement l'attente de la sonde de santé de MySQL et des migrations Alembic.

**Mémoire : trois systèmes d'exploitation contre un seul noyau partagé.**
- À l'intérieur, les trois VM n'utilisent que 2,5 Go (1 404 + 932 + 175 Mo) ; vues de l'hôte, elles en occupent 3,6 Go. La différence, c'est la mémoire de trois noyaux, de trois caches de pages, de trois systemd, et du processus VirtualBox de chaque VM.
- Un conteneur ne paie que la mémoire de son processus. Le moteur (`dockerd`, `containerd`, inclus dans la mesure) se partage entre tous.
- À service égal, c'est le principal gain des conteneurs. La mesure brute le cache, parce que la pile Docker contient 2,7 Go de services en plus.

**Disque : des couches partagées contre des disques complets.**
- Chaque VM porte un disque Ubuntu entier (environ 3 Go chacun), où le système est dupliqué trois fois.
- Les images Docker sont faites de couches en lecture seule, partagées entre conteneurs : l'API, le worker et le service de migration utilisent la même image de 381 Mo.
- Seuls les volumes (702 Mo : MySQL, fichiers audio, Elasticsearch, Redis) sont propres au déploiement.

**Latence : trois machines virtuelles contre un pont dans le même noyau.**
- En VM, une consultation traverse deux fois le réseau virtuel de VirtualBox (proxy vers métier, métier vers base), avec des cartes virtio émulées, et chaque saut repasse par l'hyperviseur.
- En conteneurs, les paquets restent dans le même noyau, sur un pont virtuel, sans changement de contexte vers un hyperviseur.
- À cela s'ajoute le coût de la virtualisation du processeur, mesuré en partie 4 : 100 % d'un cœur dans une VM coûte 135 % sur l'hôte.

**Sous charge : surtout les ressources attribuées, et le mode de défaillance.**
- Les VM ont des ressources fixées (2 cœurs, 1,5 Go pour le métier), alors que les conteneurs n'ont aucune limite et prennent tout l'hôte.
- Le hachage argon2 des connexions sature la VM métier dès 10 utilisateurs ; le noyau y tue alors les workers faute de mémoire, d'où des erreurs 502.
- Ce n'est pas d'abord la technique d'isolation qui fait l'écart, mais l'allocation.

**Mise en place et procédure : une description contre une suite d'actions.**
- La version VM décrit *comment* faire : 1 211 lignes pour créer les machines, les adresser, ouvrir le pare-feu et écrire les unités systemd.
- La version Docker décrit *ce qui doit exister* : 190 lignes. Le moteur fournit le DNS interne (les services se trouvent par leur nom), le redémarrage, les dépendances de santé, et l'isolation réseau par défaut.

## 3. Ce que le déploiement en conteneurs a perdu par rapport aux machines virtuelles

- **Une frontière d'isolation matérielle.** Les conteneurs partagent le noyau de l'hôte. Une faille du noyau, ou un conteneur lancé avec des privilèges excessifs, atteint tous les autres et l'hôte lui-même. Entre deux VM, la frontière est l'hyperviseur, avec un noyau par machine. L'isolation des conteneurs est logicielle (espaces de noms, cgroups) : plus fine, donc plus rapide, mais plus fragile.
- **Le choix du système d'exploitation.** Tous les conteneurs utilisent le noyau Linux de l'hôte. Les VM pouvaient faire tourner n'importe quel système, et chacune garde son propre noyau, ses mises à jour et ses réglages, par exemple `vm.max_map_count` pour Elasticsearch, réglé dans la VM elle-même. En conteneurs, il faut le régler sur l'hôte, pour tous.
- **Des ressources garanties et cloisonnées.** Une VM reçoit des cœurs et une mémoire qui sont à elle. Sans limite déclarée, un conteneur peut prendre tout l'hôte : c'est ce qui a permis aux conteneurs de tenir sept fois plus de charge en partie 4. Mais un service emballé priverait aussi tous les autres. À l'inverse, la limite stricte des VM a fait tuer les workers faute de mémoire, sans déborder sur les autres couches.
- **Ici, une partie de l'isolation réseau.** Le réglage par défaut des conteneurs est plus fermé (rien n'est joignable sans publication), mais cette composition ne déclare qu'un seul réseau. **Le proxy joint la base**, ce que le pare-feu interdisait en VM. Deux ports d'outils (Kibana 5601, Mailpit 8025) sont publiés en plus du proxy. Ce ne sont pas des pertes inhérentes aux conteneurs : deux réseaux et deux lignes `ports:` en moins les corrigeraient. Mais en l'état, la version Docker est la moins isolée des deux (`avec-docker/mesures/joignabilite.md`).
- **Une partie de la visibilité.** En VM, chaque couche a sa machine, son `journalctl`, son `ss -tlnp` et son pare-feu, que l'on inspecte comme un serveur. En conteneurs, le diagnostic passe par le moteur (`docker compose logs`, `docker exec`), et les images minimales n'ont pas toujours les outils habituels : `nc`, `ss` ou `ps` peuvent manquer.

**Conclusion.** À service égal, les conteneurs démarrent environ six fois plus vite et sont nettement plus légers : environ −40 % de mémoire (estimation) et −34 % de disque. Ils répondent quatre fois plus vite, et se décrivent en six fois moins de lignes. Ils l'obtiennent en renonçant à la frontière matérielle de l'hyperviseur et au cloisonnement garanti des ressources. Dans ce dépôt, ils sont aussi, faute d'un second réseau, moins bien isolés que les VM.
