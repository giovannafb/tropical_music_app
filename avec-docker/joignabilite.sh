#!/usr/bin/env bash
# Étape 14 : matrice de joignabilité de la version Docker, sous la forme demandée par le sujet (depuis l'hôte et
# depuis chaque conteneur, vers le proxy :80, l'API :8000 et la base :3306), suivie des réseaux et des ports
# publiés. Mêmes cases que la version VM (bash avec-vm/joignabilite.sh).
# Le résultat (tableau Markdown et sorties de commandes) est écrit dans avec-docker/mesures/joignabilite.md.
#
# À lancer depuis Ubuntu (WSL), la stack démarrée (docker compose up -d --scale api=3) :
#   bash avec-docker/joignabilite.sh
set -euo pipefail
ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ICI"
docker compose ps --status running --format '{{.Service}}' | grep -qx mysql || { echo "ERREUR : la stack n'est pas démarrée" >&2; exit 1; }
mkdir -p mesures
sortie="$ICI/mesures/joignabilite.md"

# Connexion TCP depuis l'hôte ou depuis un conteneur (chaque image a son outil : nc, python ou bash)
tcp() {
  local depuis="$1" hote="$2" port="$3"
  case "$depuis" in
    hote) timeout 3 bash -c "</dev/tcp/$hote/$port" 2> /dev/null ;;
    nginx) docker compose exec -T nginx nc -z -w 2 "$hote" "$port" > /dev/null 2>&1 ;;
    api) docker compose exec -T api python -c "import socket; socket.create_connection(('$hote', $port), 2)" > /dev/null 2>&1 ;;
    mysql) docker compose exec -T mysql timeout 3 bash -c "</dev/tcp/$hote/$port" > /dev/null 2>&1 ;;
  esac
}

case_matrice() {
  local depuis="$1" hote="$2" port="$3" attendu="$4" resultat
  if tcp "$depuis" "$hote" "$port"; then resultat=oui; else resultat=non; fi
  if [ "$resultat" = "$attendu" ]; then printf '%s' "$resultat"; else printf '**%s** (attendu : %s)' "$resultat" "$attendu"; fi
}

ip_de() { docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' "musicapp-$1-1" | awk '{print $1}'; }
API_IP="$(ip_de api)"
MYSQL_IP="$(ip_de mysql)"

echo "==> Matrice de joignabilité (TCP, depuis l'hôte et depuis chaque conteneur)"
{
  echo "# Version Docker — matrice de joignabilité (étape 14)"
  echo
  echo "Relevée le $(date '+%d/%m/%Y à %H:%M') par \`bash avec-docker/joignabilite.sh\`, tous les conteneurs en marche"
  echo "(une tentative qui échoue échoue donc faute de route, et non parce qu'un service est arrêté)."
  echo "Depuis un conteneur, chaque service est appelé par son nom (DNS interne de Docker) ; en gras, un écart à l'attendu du sujet."
  echo
  echo "| Depuis | vers proxy :80 | vers métier :8000 | vers base :3306 |"
  echo "|---|:---:|:---:|:---:|"
  echo "| **L'hôte** (ports publiés, 127.0.0.1) | $(case_matrice hote 127.0.0.1 80 oui) | $(case_matrice hote 127.0.0.1 8000 non) | $(case_matrice hote 127.0.0.1 3306 non) |"
  echo "| **conteneur nginx** (proxy) | — | $(case_matrice nginx api 8000 oui) | $(case_matrice nginx mysql 3306 non) |"
  echo "| **conteneur api** (métier) | $(case_matrice api nginx 80 oui) | — | $(case_matrice api mysql 3306 oui) |"
  echo "| **conteneur mysql** (données) | $(case_matrice mysql nginx 80 non) | $(case_matrice mysql api 8000 oui) | — |"
  echo
  echo "Depuis l'hôte, par l'adresse du conteneur sur le pont Docker (le moteur tourne ici dans Ubuntu, qui a une route vers ce pont ;"
  echo "avec Docker Desktop, ces adresses ne sont pas joignables depuis Windows) : api $API_IP:8000 : $(case_matrice hote "$API_IP" 8000 non) ; mysql $MYSQL_IP:3306 : $(case_matrice hote "$MYSQL_IP" 3306 non)."
  echo
  echo "## Ports publiés (\`docker compose ps\`)"
  echo
  echo '```'
  docker compose ps --format '{{.Name}}\t{{.Ports}}' | sort | awk -F'\t' '{printf "%-24s %s\n", $1, ($2 == "" ? "(aucun)" : $2)}'
  echo '```'
  echo
  echo "## Réseaux du projet (\`docker network inspect\`)"
  echo
  echo '```'
  for reseau in $(docker network ls --filter label=com.docker.compose.project=musicapp --format '{{.Name}}'); do
    echo "$reseau : $(docker network inspect -f '{{range .Containers}}{{.Name}} {{end}}' "$reseau" | tr ' ' '\n' | sed 's/^musicapp-//' | sort | tr '\n' ' ')"
  done
  echo '```'
} > "$sortie"
sed -n '/^| Depuis/,/^$/p' "$sortie" | sed 's/^/    /'
echo "    écrit dans $sortie"
