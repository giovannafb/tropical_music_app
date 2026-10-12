#!/usr/bin/env bash
# Affiche l'état de chaque VM et de ses services, puis vérifie la séparation des couches :
# qui peut joindre qui sur le réseau privé.
#
#   bash avec-vm/etat.sh
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"
verifier_virtualbox
charger_env > /dev/null

# Alignement en caractères (printf compte les octets : « é » ou « → » en valent plusieurs)
ligne() { printf '  %s%*s %s\n' "$1" $((32 - ${#1})) '' "$2"; }
vert() { printf '\033[32m%s\033[0m' "$1"; }
rouge() { printf '\033[31m%s\033[0m' "$1"; }

declare -A SERVICES=(
  [donnees]="mysql redis-server elasticsearch nfs-server"
  [metier]="musicapp-worker mailpit $(for ((i = 0; i < API_INSTANCES; i++)); do printf 'musicapp-api@%s ' $((API_FIRST_PORT + i)); done)"
  [presentation]="nginx"
)

for role in "${ROLES[@]}"; do
  nom="$(nom_vm "$role")"
  etape "$nom (${IP[$role]})"
  if ! vm_existe "$role"; then ligne "VM" "$(rouge "absente (bash avec-vm/installer.sh)")"; continue; fi
  if ! vm_allumee "$role"; then ligne "VM" "$(rouge "arrêtée")"; continue; fi
  ligne "VM" "$(vert "démarrée")"
  for service in ${SERVICES[$role]}; do
    if vm_ssh "$role" systemctl is-active -q "$service" 2> /dev/null; then
      ligne "$service" "$(vert "actif")"
    else
      ligne "$service" "$(rouge "arrêté")"
    fi
  done
done

etape "Accès depuis Windows / Ubuntu"
if curl -fs -o /dev/null "http://127.0.0.1:$SITE_PORT/api/health"; then
  ligne "site" "$(vert "http://localhost:$SITE_PORT")"
else
  ligne "site" "$(rouge "ne répond pas")"
fi
if curl -fs -o /dev/null "http://127.0.0.1:$MAILPIT_PORT"; then
  ligne "emails (Mailpit)" "$(vert "http://localhost:$MAILPIT_PORT")"
else
  ligne "emails (Mailpit)" "$(rouge "ne répond pas")"
fi

# Séparation des couches : chaque test tente une connexion TCP depuis une VM vers le port d'une autre
etape "Séparation des couches (connexions TCP sur le réseau privé)"
teste() {
  local depuis="$1" vers="$2" port="$3" attendu="$4" libelle="$5" resultat
  if vm_allumee "$depuis" && vm_allumee "$vers"; then
    if vm_ssh "$depuis" "nc -z -w 2 $(nom_vm "$vers") $port" 2> /dev/null; then resultat=autorisé; else resultat=refusé; fi
    if [ "$resultat" = "$attendu" ]; then
      ligne "$libelle" "$(vert "$resultat") (attendu)"
    else
      ligne "$libelle" "$(rouge "$resultat") (attendu : $attendu)"
    fi
  fi
}
teste presentation metier "$API_FIRST_PORT" autorisé "présentation → API"
teste presentation donnees 3306 refusé "présentation → MySQL"
teste presentation donnees 6379 refusé "présentation → Redis"
teste presentation donnees 9200 refusé "présentation → Elasticsearch"
teste metier donnees 3306 autorisé "métier → MySQL"
teste metier donnees 6379 autorisé "métier → Redis"
teste metier donnees 9200 autorisé "métier → Elasticsearch"
teste donnees metier "$API_FIRST_PORT" refusé "données → API"
