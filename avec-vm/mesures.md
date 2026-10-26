# MusicApp — version VM : vérification et mesures de référence (étape 10)

Relevés du 26 octobre 2026, sur le poste décrit plus bas, avec les scripts du dépôt. Tout est rejouable :

| Livrable de l'étape 10 | Où le trouver | Commande |
|---|---|---|
| Matrice de joignabilité remplie | partie 1 ci-dessous ; détail dans [`mesures/joignabilite.md`](mesures/joignabilite.md) | `bash avec-vm/joignabilite.sh` |
| Sorties de commandes qui l'attestent | [`mesures/joignabilite.md`](mesures/joignabilite.md) : `ss -tlnp` et `ufw status` de chaque VM | idem |
| Tableau des mesures de référence | partie 2 ; brut dans [`../charge/resultats/repos/vm.txt`](../charge/resultats/repos/vm.txt) | `bash charge/repos.sh vm` |
| Les trois machines au format OVA | hors du dépôt (trop volumineux pour git) : `~/MusicApp-OVA/vm-presentation.ova`, `vm-metier.ova`, `vm-donnees.ova`, et `SHA256SUMS` | `VBoxManage export <vm> -o <vm>.ova --ovf20` |
| Configuration des machines | [`mesures/virtualbox-vms.txt`](mesures/virtualbox-vms.txt) : mémoire, processeurs, cartes réseau, redirections | `VBoxManage showvminfo` |

## 1. Matrice de joignabilité

Les trois VM démarrées, tous leurs services actifs : une tentative qui échoue échoue faute de route ou de règle, et non parce qu'un service est arrêté. Chaque case est une connexion TCP (`nc -z -w 2` depuis une VM, `/dev/tcp` depuis l'hôte). La base est MySQL (port 3306, et non 5432 : l'application utilise MySQL).

| Depuis | vers proxy :80 (192.168.56.11) | vers métier :8000 (192.168.56.12) | vers base :3306 (192.168.56.13) |
|---|:---:|:---:|:---:|
| **L'hôte** (WSL, 192.168.56.1) | oui ; via 127.0.0.1:8081 : oui | non | non |
| **vm-presentation** | — | oui | non |
| **vm-metier** | non (sujet : oui) | — | oui |
| **vm-donnees** | non (sujet : oui) | non (sujet : oui) | — |

Également refusés depuis l'hôte : Redis (6379) et Elasticsearch (9200) de `vm-donnees`.

**Les trois cases « doit échouer » échouent**, comme demandé :
- l'hôte ne joint ni l'API ni la base ;
- le proxy ne joint pas la base.

Elles échouent pour les deux raisons que le sujet attend :
- **chaque service écoute sur l'adresse privée de sa VM**, et non sur `0.0.0.0`. Par exemple, MySQL écoute sur `192.168.56.13:3306` et les trois instances d'API sur `192.168.56.12:8000-8002` (`ss -tlnp`) ;
- **le pare-feu `ufw` de chaque VM refuse tout en entrée**, sauf la couche voisine (`ufw status`). MySQL, par exemple, n'est autorisé que depuis 192.168.56.12.

Trois cases diffèrent de la matrice du sujet, toujours dans le sens de la fermeture :
- `vm-metier` et `vm-donnees` ne joignent pas le proxy : le pare-feu de `vm-presentation` n'accepte le port 80 que depuis la redirection NAT et depuis l'hôte ;
- `vm-donnees` ne joint pas l'API : rien, dans l'application, n'exige ces flux.

C'est un choix assumé du déploiement, plus strict que la topologie demandée.

### Écarts à la topologie du sujet, à justifier

Le sujet retient un **réseau interne** VirtualBox, et une carte **NAT sur le seul proxy**. Ce déploiement est différent (`mesures/virtualbox-vms.txt`) :
- **les trois VM ont une carte NAT** (accès à Internet pour les paquets, redirections de port) ;
- **le réseau entre les VM est un réseau privé hôte** (`vboxnet0`), joignable depuis l'hôte.

Le sujet prévient qu'avec un réseau privé hôte, « l'hôte joint la base ». Ici ce n'est pas le cas, mais c'est grâce au pare-feu de chaque VM, et non à la topologie : l'isolation repose sur une règle logicielle, pas sur l'absence de route. Deux points à mentionner au compte rendu :
- la carte NAT de `vm-metier` publie aussi Mailpit (127.0.0.1:8027, interface des emails de développement) ;
- une règle `ufw` oubliée suffirait à ouvrir la base à l'hôte, ce qu'un réseau interne aurait rendu impossible.

## 2. Mesures de référence

Protocole : trois exécutions, médiane retenue (`bash charge/repos.sh vm`). Le même protocole est rejoué sur les conteneurs à l'étape 14 (`avec-docker/mesures.md`).

| Grandeur | Comment elle est relevée | Exécutions | **Médiane** |
|---|---|---|---|
| **Temps de démarrage** | des trois VM éteintes au parcours connexion + consultation des likes réussi à travers le proxy | 99,7 s ; 111,7 s ; 109,1 s | **109,1 s** |
| **Mémoire consommée** | côté hôte : mémoire utilisée de la VM de WSL 2, où tourne VirtualBox, les trois VM au repos depuis 60 s, moins la même mesure VM éteintes (1 465 Mo) | 3 597 ; 3 621 ; 3 656 Mo | **3 621 Mo** |
| **Empreinte disque** | taille cumulée des disques des trois VM (`~/VirtualBox VMs/MusicApp`) | — | **10 148 Mo** |
| **Latence applicative** | dix appels à une route de consultation (`GET /api/me/likes/tracks`, session ouverte), au repos, médiane des dix | 21,7 ; 52,2 ; 26,5 ms | **26,5 ms** |
| **Temps de mise en place** | installation automatisée (`bash avec-vm/installer.sh`), de la création de `avec-vm/.env` (17 h 53 min 32 s) à la création du compte admin, sa dernière étape (17 h 57 min 51 s) | — | **4 min 19 s** |

Lecture :
- **La mémoire** est attribuée aux VM : 512 + 1 536 + 2 560 = 4 608 Mo au maximum. Au repos, elles en occupent déjà 3,6 Go, soit le coût de trois systèmes d'exploitation complets, en plus de l'application.
- **Le temps de mise en place** ne compte que l'installation automatisée, téléchargements déjà en cache : image Ubuntu, Elasticsearch et Mailpit, environ 1,2 Go. Il ne compte pas la préparation de VirtualBox sous WSL, qui a demandé de compiler ses modules pour le noyau de WSL, environ 50 minutes en séance.
- **La latence** varie d'une exécution à l'autre (de 22 à 52 ms) : le poste servait aussi à d'autres tâches. La charge moyenne de l'hôte est consignée à chaque exécution (0,64 à 0,89).

## 3. Configuration qui a produit ces chiffres

| Élément | Valeur |
|---|---|
| Poste | AMD Ryzen 5 7500F (6 cœurs, 12 fils), Windows + WSL 2 (Ubuntu 24.04, noyau 6.6.87.2-microsoft-standard-WSL2), 15,4 Go pour WSL |
| Hyperviseur | VirtualBox 7.1.18, installé dans Ubuntu (WSL) |
| VM | Ubuntu Server 24.04 (image cloud) ; présentation 1 CPU / 512 Mo, métier 2 CPU / 1 536 Mo, données 2 CPU / 2 560 Mo |
| Application | 3 instances d'API × 2 workers gunicorn ; MySQL 8.0, Redis, Elasticsearch 8.15.3 (1 nœud) sur `vm-donnees` |
| Jeu de données | import FMA `--limit 500` (500 titres) ; empreinte du catalogue `7d7618aa71d1a0dd` |
| Snapshots | aucun : le livrable de l'étape 7 (snapshot initial nommé) n'est pas fourni |
