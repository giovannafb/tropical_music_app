# MusicApp — version VM (3 machines virtuelles VirtualBox)

Chaque couche tourne dans **sa propre machine virtuelle** Ubuntu Server 24.04, créée par VirtualBox (installé dans Ubuntu / WSL) :

| VM | Adresse privée | Couche | Contenu |
|---|---|---|---|
| `vm-presentation` | 192.168.56.11 | Présentation | Nginx + SPA (`client/`) |
| `vm-metier` | 192.168.56.12 | Métier | API ×3 (gunicorn, ports 8000-8002), worker, Mailpit |
| `vm-donnees` | 192.168.56.13 | Données | MySQL, Redis, Elasticsearch (1 nœud), partage NFS des fichiers audio / covers |

```
Windows / Ubuntu ── http://localhost:8081 ──► vm-presentation (Nginx)
                                                   │ HTTP, ports 8000-8002           NFS (lecture seule)
                                                   ▼                                        │
                                               vm-metier (API ×3, worker) ── MySQL 3306 ─┐   │
                                                                           ── Redis 6379 ─┼─► vm-donnees
                                                                           ── ES 9200 ────┤
                                                                           ── NFS 2049 ───┘
```

- Les commandes se lancent dans le **terminal Ubuntu** (dans PowerShell : `wsl`), depuis le dossier du projet :
  ```
  cd /mnt/c/Users/Utilisateur/Documents/VirtetCont
  ```
- Aucune commande `sudo` n'est nécessaire : tout est fait par `VBoxManage` et par SSH dans les VM.
- Cette version est **indépendante** des deux autres : ports, configuration (`avec-vm/.env`) et données différents.
- Mémoire : les 3 VM prennent 4,5 Go (réglable dans `avec-vm/.env`). WSL n'en a que 7,6 Go : **arrêter les autres versions** avant de lancer celle-ci.

## Première fois

1. Installation complète : téléchargements, création des 3 VM, installation de chaque couche, compte admin.
   Compter 10 à 20 minutes. Le fichier `avec-vm/.env` est créé avec des mots de passe aléatoires.
   ```
   bash avec-vm/installer.sh
   ```
2. Importer le jeu de données FMA. Retirer `--limit 500` pour importer les 8 000 titres :
   ```
   bash avec-vm/executer.sh -m app.scripts.seed_fma --metadata /fma/fma_metadata.zip --audio /fma/fma_small.zip --limit 500
   ```
   `/fma` est le dossier `donnees/fma` du projet, partagé par VirtualBox avec `vm-metier` en lecture seule.

Le compte **admin** est créé par l'installation. Son mot de passe est la valeur `ADMIN_PASSWORD` de `avec-vm/.env`.

## Au quotidien

| Action | Commande |
|---|---|
| Démarrer (données → métier → présentation) | `bash avec-vm/demarrer.sh` |
| Arrêter (présentation → métier → données, données conservées) | `bash avec-vm/arreter.sh` |
| État des VM, des services et de la séparation des couches | `bash avec-vm/etat.sh` |
| Envoyer le code modifié dans les VM | `bash avec-vm/deployer.sh` |
| Ouvrir un terminal dans une VM | `bash avec-vm/ssh.sh metier` |
| Journaux de l'API | `bash avec-vm/ssh.sh metier sudo journalctl -u 'musicapp-api@*' -f` |
| Reconstruire les index ES | `bash avec-vm/executer.sh -m app.scripts.reindex_es` |
| Tout supprimer, **données comprises** | `bash avec-vm/supprimer.sh` |

## Adresses

| URL | Service |
|---|---|
| http://localhost:8081 | Application (depuis Windows ou Ubuntu) |
| http://localhost:8081/api/docs | Documentation de l'API |
| http://localhost:8027 | Mailpit (emails de développement) |

Ces adresses passent par des **redirections de port** VirtualBox (carte NAT, sur 127.0.0.1 uniquement). Le site n'est pas ouvert sur `http://192.168.56.11` : l'API pose des cookies `Secure`, que les navigateurs n'acceptent en HTTP que sur `localhost`.

## Comment c'est construit

### Réseau (2 cartes par VM)

| Carte | Mode VirtualBox | Rôle |
|---|---|---|
| 1 | NAT | Accès à Internet (paquets) et redirections de port depuis `localhost` |
| 2 | Réseau privé hôte `vboxnet0` (192.168.56.0/24) | Communication entre les VM, et depuis WSL (192.168.56.1) |

- Adresses fixes, reconnues par l'adresse MAC de chaque carte (fixée par `installer.sh`).
- Les VM se trouvent par leur nom (`vm-donnees`…) grâce à `/etc/hosts` : c'était le rôle du DNS interne de Docker.
- Chaque service écoute sur l'**adresse privée**, pas sur `127.0.0.1` (sinon, les autres VM ne pourraient pas le joindre).

### Sécurité entre les couches

- **Pare-feu `ufw`** dans chaque VM : tout est refusé en entrée, sauf :

  | VM | Autorisé |
  |---|---|
  | `vm-presentation` | port 80 (redirection de port, et depuis WSL) |
  | `vm-metier` | ports de l'API depuis `vm-presentation` ; Mailpit (8025) par la redirection de port |
  | `vm-donnees` | MySQL, Redis, Elasticsearch et NFS depuis `vm-metier` ; NFS depuis `vm-presentation` |

  SSH (port 22) est accepté depuis WSL uniquement.
- **Comptes par adresse** : le compte MySQL est `musicapp@192.168.56.12`, il est inutilisable ailleurs. Redis exige un mot de passe (`REDIS_PASSWORD`).
- `bash avec-vm/etat.sh` **prouve la séparation**. Par exemple, `vm-presentation` ne peut pas joindre MySQL, alors que `vm-metier` le peut.

### Fichiers audio et covers (NFS)

L'API **écrit** les fichiers (upload, import FMA) ; Nginx les **lit** et les envoie (`X-Accel-Redirect`, covers). Ce sont deux VM différentes. Le dossier se trouve donc sur `vm-donnees` (`/srv/musicapp/media`) et est partagé en NFS :
- monté en lecture-écriture sur `vm-metier` ;
- monté en **lecture seule** sur `vm-presentation`.

Dans les 3 versions, c'est le même volume `media` : Docker le monte en `:ro` pour Nginx.
- Ce montage crée un flux présentation → données, limité à la lecture de fichiers : à justifier dans le rapport.
- NFS vérifie les droits par **numéro d'utilisateur** : l'utilisateur `musicapp` a l'UID 2000 sur toutes les VM.

### Démarrage des services (systemd)

Docker Compose disparaît. Dans chaque VM, **systemd** démarre les services avec la machine et les relance s'ils s'arrêtent (`Restart=`).

Sur `vm-metier` :

| Service | Commande |
|---|---|
| API (une instance par port) | `musicapp-api@8000`, `@8001`, `@8002` : remplace `--scale api=3` |
| Worker | `musicapp-worker` |
| Emails | `mailpit` |

Sur `vm-donnees` : `mysql`, `redis-server`, `elasticsearch`, `nfs-server`.

Sur `vm-presentation` : `nginx`.

`depends_on` ne fonctionne pas d'une machine à l'autre : `demarrer.sh` démarre donc les VM dans l'ordre des couches. Si une VM démarre trop tôt, ses services réessaient seuls. Les montages NFS se font à la première utilisation (`automount`).

### Premier démarrage (cloud-init)

Les VM sont créées à partir de l'**image cloud officielle d'Ubuntu Server 24.04**, sans installation manuelle. Au premier démarrage, **cloud-init** lit sa configuration sur un petit serveur web lancé par `installer.sh` : utilisateur `ubuntu`, clé SSH, adresses IP. L'adresse de ce serveur est dans le numéro de série (DMI) de la VM. Ensuite, cloud-init est désactivé.

## Fichiers

| Fichier | Rôle |
|---|---|
| `installer.sh`, `demarrer.sh`, `arreter.sh`, `etat.sh`, `deployer.sh`, `executer.sh`, `ssh.sh`, `supprimer.sh` | Commandes, lancées dans Ubuntu (WSL) |
| `commun.sh` | Réglages communs : adresses, ports, fonctions VirtualBox et SSH |
| `vm/donnees.sh`, `vm/metier.sh`, `vm/presentation.sh` | Installation de chaque couche, exécutée **dans** sa VM (en root) |
| `vm/fichiers/` | Services systemd, modèle Nginx, commande `musicapp-python` |
| `.env.example` | Modèle de `avec-vm/.env` (non versionné) |

Hors du projet :

| Emplacement | Contenu |
|---|---|
| `~/.musicapp-vm/` | Téléchargements, clé SSH, configuration cloud-init |
| `~/VirtualBox VMs/MusicApp/` | Disques des VM |

Dans les VM :

| Emplacement | Contenu |
|---|---|
| `/opt/musicapp` | Code et environnement Python (`vm-metier`) |
| `/etc/musicapp` | Configuration (`vm-metier`) |
| `/var/www/musicapp` | Client (`vm-presentation`) |
| `/srv/musicapp/media` | Fichiers audio et covers (`vm-donnees`) |

## En cas de problème

- `bash avec-vm/etat.sh` indique ce qui ne tourne pas.
- Journaux d'un service :
  ```
  bash avec-vm/ssh.sh donnees sudo journalctl -u elasticsearch -e
  ```
- Une VM ne démarre pas : son journal de démarrage est dans `~/VirtualBox VMs/MusicApp/<vm>/console.log`. Tu peux aussi ouvrir VirtualBox (`virtualbox &`) et te connecter à la console avec l'utilisateur `ubuntu` et le mot de passe `VM_PASSWORD` de `avec-vm/.env`.
- Après une mise à jour du noyau de WSL, VirtualBox ne démarre plus : il faut recompiler son module (`sudo /sbin/vboxconfig`, après avoir préparé les sources du nouveau noyau).
