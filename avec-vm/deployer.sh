#!/usr/bin/env bash
# Envoie le code modifié dans les VM, sans les recréer : metier/ et donnees/migrations vers vm-metier
# (migrations appliquées, API et worker redémarrés), client/ vers vm-presentation (Nginx rechargé).
#
#   bash avec-vm/deployer.sh                 # métier + présentation
#   bash avec-vm/deployer.sh presentation    # une seule couche (presentation, metier ou donnees)
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"
verifier_virtualbox
charger_env
roles=("$@")
[ ${#roles[@]} -gt 0 ] || roles=(metier presentation)
for role in "${roles[@]}"; do
  [[ " ${ROLES[*]} " == *" $role "* ]] || erreur "couche inconnue : $role (presentation, metier ou donnees)"
  vm_allumee "$role" || erreur "$(nom_vm "$role") est arrêtée : lance d'abord bash avec-vm/demarrer.sh"
done
# Toujours de bas en haut
for role in "${ROLES[@]}"; do
  if [[ " ${roles[*]} " == *" $role "* ]]; then provisionner "$role"; fi
done
etape "Déploiement terminé : http://localhost:$SITE_PORT"
