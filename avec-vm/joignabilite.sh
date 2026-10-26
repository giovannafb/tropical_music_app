#!/usr/bin/env bash
# Étape 10 : matrice de joignabilité de la version VM, sous la forme demandée par le sujet (depuis l'hôte et
# depuis chaque VM, vers le proxy :80, l'API :8000 et la base :3306), suivie des adresses d'écoute de chaque
# service (ss -tlnp). Complète bash avec-vm/etat.sh, qui ne teste que les connexions entre VM.
# Le résultat (tableau Markdown et sorties de commandes) est écrit dans avec-vm/mesures/joignabilite.md.
#
#   bash avec-vm/joignabilite.sh
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"
verifier_virtualbox
charger_env > /dev/null
for role in "${ROLES[@]}"; do
  vm_allumee "$role" || erreur "$(nom_vm "$role") est arrêtée : bash avec-vm/demarrer.sh (une tentative doit échouer faute de route, pas faute de service)"
done
mkdir -p "$AVEC_VM/mesures"
sortie="$AVEC_VM/mesures/joignabilite.md"

# Connexion TCP depuis l'hôte (WSL) ou depuis une VM ; réussit si le port accepte la connexion en moins de 2 s
tcp() {
  local depuis="$1" adresse="$2" port="$3"
  if [ "$depuis" = hote ]; then
    timeout 3 bash -c "</dev/tcp/$adresse/$port" 2> /dev/null
  else
    vm_ssh "$depuis" "nc -z -w 2 $adresse $port" 2> /dev/null
  fi
}

# Une case : résultat mesuré, comparé à l'attendu du sujet
case_matrice() {
  local depuis="$1" adresse="$2" port="$3" attendu="$4" resultat
  if tcp "$depuis" "$adresse" "$port"; then resultat=oui; else resultat=non; fi
  if [ "$resultat" = "$attendu" ]; then printf '%s' "$resultat"; else printf '**%s** (attendu : %s)' "$resultat" "$attendu"; fi
}

P="${IP[presentation]}" M="${IP[metier]}" D="${IP[donnees]}"
etape "Matrice de joignabilité (TCP, depuis l'hôte et depuis chaque VM)"
{
  echo "# Version VM — matrice de joignabilité (étape 10)"
  echo
  echo "Relevée le $(date '+%d/%m/%Y à %H:%M') par \`bash avec-vm/joignabilite.sh\`, les trois VM démarrées et tous leurs services actifs"
  echo "(une tentative qui échoue échoue donc faute de route ou de règle, et non parce qu'un service est arrêté)."
  echo "Chaque case est une connexion TCP (\`nc -z -w 2\` depuis une VM, \`/dev/tcp\` depuis l'hôte) ; en gras, un écart à l'attendu du sujet."
  echo
  echo "| Depuis | vers proxy :80 ($P) | vers métier :$API_FIRST_PORT ($M) | vers base :3306 ($D) |"
  echo "|---|:---:|:---:|:---:|"
  echo "| **L'hôte** (WSL, $IP_HOTE) | $(case_matrice hote "$P" 80 oui) ; via 127.0.0.1:$SITE_PORT : $(case_matrice hote 127.0.0.1 "$SITE_PORT" oui) | $(case_matrice hote "$M" "$API_FIRST_PORT" non) | $(case_matrice hote "$D" 3306 non) |"
  echo "| **vm-presentation** | — | $(case_matrice presentation vm-metier "$API_FIRST_PORT" oui) | $(case_matrice presentation vm-donnees 3306 non) |"
  echo "| **vm-metier** | $(case_matrice metier vm-presentation 80 oui) | — | $(case_matrice metier vm-donnees 3306 oui) |"
  echo "| **vm-donnees** | $(case_matrice donnees vm-presentation 80 oui) | $(case_matrice donnees vm-metier "$API_FIRST_PORT" oui) | — |"
  echo
  echo "Autres services de vm-donnees, depuis l'hôte (doivent échouer) : Redis 6379 : $(case_matrice hote "$D" 6379 non) ; Elasticsearch 9200 : $(case_matrice hote "$D" 9200 non)."
  echo "Redirections de port de la carte NAT (sur 127.0.0.1 de l'hôte uniquement) : site $SITE_PORT → vm-presentation:80 ; Mailpit $MAILPIT_PORT → vm-metier:8025 : $(case_matrice hote 127.0.0.1 "$MAILPIT_PORT" oui)."
  echo
  echo "## Adresses d'écoute (\`ss -tlnp\`, ports de l'application)"
  for role in "${ROLES[@]}"; do
    echo
    echo "### $(nom_vm "$role") (${IP[$role]})"
    echo
    echo '```'
    vm_ssh "$role" "sudo ss -tlnp" | awk 'NR == 1 || /:(80|800[0-9]|3306|6379|9200|9300|2049|8025|1025) /' | sed -E 's/users:\(\("([^"]+)".*/\1/'
    echo '```'
  done
  echo
  echo "## Pare-feu (\`ufw status\`)"
  for role in "${ROLES[@]}"; do
    echo
    echo "### $(nom_vm "$role")"
    echo
    echo '```'
    vm_ssh "$role" "sudo ufw status" | grep -v '^$'
    echo '```'
  done
} > "$sortie"
sed -n '/^| Depuis/,/^$/p' "$sortie" | sed 's/^/    /'
ok "écrit dans $sortie"
