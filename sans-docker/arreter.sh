#!/usr/bin/env bash
# Arrête la version sans Docker (libère la mémoire et les ports).
#
#   bash sans-docker/arreter.sh
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"

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

etape "Application"
shopt -s nullglob
for fichier in "$RUN"/api-*.pid; do
  port="${fichier##*/api-}"
  arreter_pid "$fichier" "API (port ${port%.pid})"
done
arreter_pid "$RUN/worker.pid" "worker"
arreter_pid "$RUN/mailpit.pid" "Mailpit"
arreter_pid "$RUN/elasticsearch.pid" "Elasticsearch"
rm -f "$RUN/base-prete"

etape "Services système : Nginx, Redis, MySQL (mot de passe sudo demandé)"
sudo systemctl stop nginx redis-server mysql
ok "arrêtés"
