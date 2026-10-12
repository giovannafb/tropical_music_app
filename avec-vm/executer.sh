#!/usr/bin/env bash
# Lance une commande Python de la couche métier DANS vm-metier (utilisateur musicapp, configuration de la VM).
#
#   bash avec-vm/executer.sh -m app.scripts.create_admin --username admin --email admin@example.com
#   bash avec-vm/executer.sh -m app.scripts.seed_fma --metadata /fma/fma_metadata.zip --audio /fma/fma_small.zip --limit 500
#   bash avec-vm/executer.sh -m app.scripts.reindex_es
#
# /fma est le dossier donnees/fma du projet, partagé en lecture seule avec vm-metier par VirtualBox.
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"
verifier_virtualbox
vm_allumee metier || erreur "vm-metier est arrêtée : lance d'abord bash avec-vm/demarrer.sh"
[ $# -gt 0 ] || erreur "indique la commande, par exemple : -m app.scripts.reindex_es"
vm_ssh_tty metier "sudo musicapp-python $(printf '%q ' "$@")"
