#!/usr/bin/env bash
# Arrête proprement les 3 VM, dans l'ordre inverse du démarrage (présentation, métier, données).
# Les données sont conservées (disques des VM).
#
#   bash avec-vm/arreter.sh
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"
verifier_virtualbox

for ((n = ${#ROLES[@]} - 1; n >= 0; n--)); do
  role="${ROLES[$n]}"
  nom="$(nom_vm "$role")"
  vm_existe "$role" || continue
  if ! vm_allumee "$role"; then
    ok "$nom déjà arrêtée"
    continue
  fi
  # Bouton d'arrêt ACPI : le système invité s'arrête proprement (services, disques)
  vbox controlvm "$nom" acpipowerbutton
  for ((i = 0; i < 90; i++)); do vm_allumee "$role" || break; sleep 1; done
  if vm_allumee "$role"; then
    vbox controlvm "$nom" poweroff > /dev/null 2>&1 || true
    ok "$nom arrêtée (forcée après 90 s)"
  else
    ok "$nom arrêtée"
  fi
done
