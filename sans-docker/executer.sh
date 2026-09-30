#!/usr/bin/env bash
# Lance une commande Python de la couche métier avec la configuration de la version sans Docker.
#
#   bash sans-docker/executer.sh -m app.scripts.create_admin --username admin --email admin@example.com
#   bash sans-docker/executer.sh -m app.scripts.seed_fma --metadata ../donnees/fma/fma_metadata.zip --audio ../donnees/fma/fma_small.zip
#   bash sans-docker/executer.sh -m app.scripts.reindex_es
#
# La commande s'exécute depuis le dossier metier/.
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"
charger_env
[ -x "$VENV/bin/python" ] || erreur "lance d'abord bash sans-docker/installer.sh"
systemctl is-active --quiet mysql && [ -f "$RUN/base-prete" ] \
  || erreur "la base n'est pas prête : lance d'abord bash sans-docker/demarrer.sh (jusqu'au bout)"
cd "$PROJET/metier"
exec "$VENV/bin/python" "$@"
