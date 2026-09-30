# MusicApp — version sans Docker

Les mêmes couches que la version Docker (`client/`, `metier/`, `donnees/`) tournent directement dans **Ubuntu (WSL)** :

| Composant | Ici | Version Docker |
|---|---|---|
| Nginx | paquet Ubuntu, port **8080** | conteneur, port 80 |
| API | gunicorn, 3 instances (ports 8000 à 8002) | 3 conteneurs |
| Worker | processus Python | conteneur |
| MySQL | paquet Ubuntu (MySQL 8.0) | conteneur (MySQL 8.4) |
| Redis | paquet Ubuntu | conteneur |
| Elasticsearch | **1 nœud** (8.15.3, répliques à 0) | 3 nœuds (répliques à 2) |
| Mailpit | binaire, interface sur le port **8026** | conteneur, port 8025 |
| Kibana | — | conteneur |

- Les ports sont différents de ceux de la version Docker : les deux versions ne se gênent jamais.
- Chaque version a **ses propres données** : sa base, ses comptes et ses fichiers audio. L'admin et l'import FMA sont donc à refaire dans chaque version.
- La mémoire ne suffit pas pour faire tourner les deux versions en même temps : arrêter l'une avant de lancer l'autre.

Les logiciels sont installés hors du projet : dans `~/.musicapp` (Elasticsearch, Mailpit, environnement Python, journaux) et `/var/lib/musicapp/media` (fichiers audio et covers).

## Ouvrir un terminal Ubuntu dans le projet

Toutes les commandes `bash …` ci-dessous se lancent dans ce terminal. Depuis PowerShell :
```
wsl
```
puis :
```
cd /mnt/c/Users/Utilisateur/Documents/VirtetCont
```

## Première fois

1. Configuration : copier l'exemple, puis remplacer les valeurs `change-me` (avec `nano`, ou le Bloc-notes de Windows) :
   ```
   cp sans-docker/.env.example sans-docker/.env
   ```
2. Installation. Le mot de passe **sudo** d'Ubuntu est demandé ; environ 1 Go est téléchargé :
   ```
   bash sans-docker/installer.sh
   ```
3. Démarrage :
   ```
   bash sans-docker/demarrer.sh
   ```
4. Créer le compte admin et la playlist à la une. Le mot de passe est lu dans `ADMIN_PASSWORD` :
   ```
   bash sans-docker/executer.sh -m app.scripts.create_admin --username admin --email admin@example.com
   ```
5. Importer le jeu de données FMA. Retirer `--limit 500` pour importer les 8 000 titres :
   ```
   bash sans-docker/executer.sh -m app.scripts.seed_fma --metadata ../donnees/fma/fma_metadata.zip --audio ../donnees/fma/fma_small.zip --limit 500
   ```

## Au quotidien

| Action | Commande |
|---|---|
| Démarrer | `bash sans-docker/demarrer.sh` |
| Arrêter (les données sont conservées) | `bash sans-docker/arreter.sh` |
| État | `bash sans-docker/etat.sh` |
| Journaux | `ls ~/.musicapp/logs` puis `tail -f ~/.musicapp/logs/worker.log` |
| Reconstruire les index ES | `bash sans-docker/executer.sh -m app.scripts.reindex_es` |

Le nombre d'instances d'API se règle avec `API_INSTANCES` dans `sans-docker/.env`, puis `arreter.sh` et `demarrer.sh`.

## Adresses

| URL | Service |
|---|---|
| http://localhost:8080 | Application |
| http://localhost:8080/api/docs | Documentation de l'API |
| http://localhost:8026 | Mailpit (emails de développement) |
