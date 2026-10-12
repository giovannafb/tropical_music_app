#!/usr/bin/env bash
# Démarre les 3 VM dans l'ordre des couches (données, puis métier, puis présentation) et attend que chacune soit prête.
#
#   bash avec-vm/demarrer.sh
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"
verifier_virtualbox
charger_env
for role in "${ROLES[@]}"; do
  vm_existe "$role" || erreur "$(nom_vm "$role") n'existe pas : lance d'abord bash avec-vm/installer.sh"
done
verifier_memoire

# Ce qui prouve qu'une couche est prête, vérifié depuis la VM elle-même
pret() {
  case "$1" in
    donnees) vm_ssh donnees "systemctl is-active -q mysql redis-server nfs-server && curl -fs -o /dev/null 'http://127.0.0.1:9200/_cluster/health?wait_for_status=yellow&timeout=1s'" ;;
    metier) vm_ssh metier "curl -fs -o /dev/null http://${IP[metier]}:$API_FIRST_PORT/api/health" ;;
    presentation) curl -fs -o /dev/null "http://127.0.0.1:$SITE_PORT/api/health" ;;
  esac
}

for role in "${ROLES[@]}"; do
  nom="$(nom_vm "$role")"
  etape "$nom (${IP[$role]})"
  if vm_allumee "$role"; then
    ok "déjà démarrée"
  else
    preparer_vm "$role"
    vbox startvm "$nom" --type headless > /dev/null
    ok "démarrée (${RAM[$role]} Mo, ${CPU[$role]} CPU)"
  fi
  attendre_ssh "$role" 180 || erreur "$nom ne répond pas en SSH (journal : $DOSSIER_VMS/$nom/console.log)"
  for ((i = 0; i < 180; i += 3)); do pret "$role" 2> /dev/null && break; sleep 3; done
  pret "$role" 2> /dev/null || erreur "la couche $role ne répond pas : bash avec-vm/etat.sh"
  ok "prête"
done

etape "MusicApp (VM) est démarrée"
echo "    Application : http://localhost:$SITE_PORT"
echo "    API (docs)  : http://localhost:$SITE_PORT/api/docs"
echo "    Emails      : http://localhost:$MAILPIT_PORT"
echo "    Arrêt       : bash avec-vm/arreter.sh"
