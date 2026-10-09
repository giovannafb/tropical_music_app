#!/usr/bin/env bash
# Lance une commande Python de la couche métier avec la configuration de la version distribuée.
# ATTENTION : Ce script doit être exécuté UNIQUEMENT sur la machine API.
#
#   bash sans-docker/executer.sh -m app.scripts.create_admin --username admin --email admin@example.com
#   bash sans-docker/executer.sh -m app.scripts.seed_fma --metadata ../donnees/fma/fma_metadata.zip --audio ../donnees/fma/fma_small.zip
#   bash sans-docker/executer.sh -m app.scripts.reindex_es
#
# La commande s'exécute depuis le dossier metier/.
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"
charger_env

[ -x "$VENV/bin/python" ] || erreur "environnement Python introuvable : lance d'abord bash sans-docker/installer.sh api"

# La vérification locale de MySQL a été retirée car la base est sur une autre VM.
# On vérifie uniquement si demarrer.sh a préparé la base depuis l'API.
[ -f "$RUN/base-prete" ] \
  || erreur "l'API n'est pas prête : lance d'abord bash sans-docker/demarrer.sh api"

cd "$PROJET/metier"
exec "$VENV/bin/python" "$@"