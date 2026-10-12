#!/usr/bin/env bash
# Supprime les 3 VM et leurs disques : base, comptes, fichiers audio… tout est perdu.
# Les téléchargements (~/.musicapp-vm/cache) sont gardés : installer.sh recrée les VM sans retélécharger.
#
#   bash avec-vm/supprimer.sh
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"
verifier_virtualbox
echo "Les VM vm-presentation, vm-metier et vm-donnees vont être supprimées, avec toutes leurs données."
read -r -p "Taper SUPPRIMER pour confirmer : " reponse
[ "$reponse" = "SUPPRIMER" ] || { echo "Annulé."; exit 0; }
for role in "${ROLES[@]}"; do
  nom="$(nom_vm "$role")"
  if vm_existe "$role"; then
    vm_allumee "$role" && { vbox controlvm "$nom" poweroff > /dev/null 2>&1 || true; sleep 2; }
    vbox unregistervm "$nom" --delete > /dev/null
    ok "$nom supprimée"
  fi
  rm -f "$LOCAL/$nom.initialisee"
  rm -rf "$SEMENCES/$nom"
done
