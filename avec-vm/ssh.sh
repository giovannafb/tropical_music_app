#!/usr/bin/env bash
# Ouvre un terminal dans une VM (utilisateur ubuntu, sudo sans mot de passe), ou y lance une commande.
#
#   bash avec-vm/ssh.sh metier
#   bash avec-vm/ssh.sh donnees sudo journalctl -u elasticsearch -e
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"
role="${1:-}"
[[ " ${ROLES[*]} " == *" $role "* ]] || erreur "indique la VM : presentation, metier ou donnees"
shift
vm_allumee "$role" || erreur "$(nom_vm "$role") est arrêtée : lance d'abord bash avec-vm/demarrer.sh"
if [ $# -eq 0 ]; then
  vm_ssh_tty "$role"
else
  vm_ssh_tty "$role" "$@"
fi
