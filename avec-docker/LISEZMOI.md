# MusicApp — version Docker

Toute la stack du doc tourne dans des conteneurs : Nginx, API ×N, worker, MySQL, Redis, Elasticsearch ×3, Kibana et Mailpit.
Les commandes se lancent dans **PowerShell**, depuis ce dossier :

```
cd C:\Users\Utilisateur\Documents\VirtetCont\avec-docker
```

## Première fois

1. Réglage Elasticsearch (à refaire après chaque redémarrage de Windows ou de WSL) :
   ```
   wsl -d docker-desktop sysctl -w vm.max_map_count=262144
   ```
2. Configuration : copier `.env.example` en `.env`, puis remplacer toutes les valeurs `change-me` :
   ```
   copy .env.example .env
   ```
3. Construire et lancer la stack (3 instances d'API) :
   ```
   docker compose up -d --build --scale api=3
   ```
   Le service `migrate` applique les migrations Alembic de `donnees/` avant le démarrage de l'API.
4. Créer le compte admin et la playlist à la une (jamais via le site). Le mot de passe est lu dans `ADMIN_PASSWORD` :
   ```
   docker compose run --rm api python -m app.scripts.create_admin --username admin --email admin@example.com
   ```
5. Importer le jeu de données FMA (artistes validés, albums publiés). Retirer `--limit 500` pour importer les 8 000 titres :
   ```
   docker compose run --rm -v ../donnees/fma:/fma:ro api python -m app.scripts.seed_fma --metadata /fma/fma_metadata.zip --audio /fma/fma_small.zip --limit 500
   ```

## Au quotidien

| Action | Commande |
|---|---|
| Démarrer | `docker compose up -d --scale api=3` |
| Arrêter (les données sont conservées) | `docker compose stop` |
| État | `docker compose ps` |
| Journaux | `docker compose logs -f api worker` |
| Reconstruire les index ES | `docker compose run --rm api python -m app.scripts.reindex_es` |
| Tout supprimer, **données comprises** | `docker compose down -v` |

## Adresses

| URL | Service |
|---|---|
| http://localhost | Application |
| http://localhost/api/docs | Documentation de l'API |
| http://localhost:8025 | Mailpit (emails de développement) |
| http://localhost:5601 | Kibana |
