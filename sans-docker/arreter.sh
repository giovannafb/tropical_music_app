#!/usr/bin/env bash
# Arrête la version distribuée (libère la mémoire et les ports).
#
#   bash sans-docker/arreter.sh [db|api|web]
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"

TARGET="${1:-}"
if [[ ! "$TARGET" =~ ^(db|api|web)$ ]]; then
  echo "Erreur: Définissez la cible de démarrage. Usage: $0 [db|api|web]"
  exit 1
fi

arreter_pid() {
  local fichier="$1" nom="$2" i
  if pid_actif "$fichier"; then
    kill "$(cat "$fichier")"
    for ((i = 0; i < 30; i++)); do pid_actif "$fichier" || break; sleep 1; done
    pid_actif "$fichier" && kill -9 "$(cat "$fichier")" 2>/dev/null
    ok "$nom arrêté"
  fi
  rm -f "$fichier"
}

if [ "$TARGET" == "db" ]; then
  etape "Arrêt de la Base de données"
  arreter_pid "$RUN/elasticsearch.pid" "Elasticsearch"
  sudo systemctl stop redis-server mysql
  ok "Services de données arrêtés"
fi

if [ "$TARGET" == "api" ]; then
  etape "Arrêt de l'Application"
  shopt -s nullglob
  for fichier in "$RUN"/api-*.pid; do
    port="${fichier##*/api-}"
    arreter_pid "$fichier" "API (port ${port%.pid})"
  done
  arreter_pid "$RUN/worker.pid" "worker"
  arreter_pid "$RUN/mailpit.pid" "Mailpit"
  rm -f "$RUN/base-prete"
  ok "Application arrêtée"
fi

if [ "$TARGET" == "web" ]; then
  etape "Arrêt du Serveur Web (Nginx)"
  sudo systemctl stop nginx
  ok "Nginx arrêté"
fi