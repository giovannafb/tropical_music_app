#!/usr/bin/env bash
# Affiche l'état de chaque composant de la version sans Docker.
#
#   bash sans-docker/etat.sh
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"

ligne() { printf '  %-22s %s\n' "$1" "$2"; }
marche() { printf '\033[32mdémarré\033[0m'; }
arret() { printf '\033[31marrêté\033[0m'; }

etape "Version sans Docker"
for service in mysql redis-server nginx; do
  if systemctl is-active --quiet "$service"; then ligne "$service" "$(marche)"; else ligne "$service" "$(arret)"; fi
done
if curl -fs -o /dev/null "$ES_URL"; then
  ligne "elasticsearch" "$(marche) ($(curl -fs "$ES_URL/_cluster/health?filter_path=status" | tr -d '{}"'))"
else
  ligne "elasticsearch" "$(arret)"
fi
shopt -s nullglob
apis=("$RUN"/api-*.pid)
[ ${#apis[@]} -eq 0 ] && ligne "api" "$(arret)"
for fichier in "${apis[@]}"; do
  port="${fichier##*/api-}"
  if pid_actif "$fichier"; then ligne "api (port ${port%.pid})" "$(marche)"; else ligne "api (port ${port%.pid})" "$(arret)"; fi
done
if pid_actif "$RUN/worker.pid"; then ligne "worker" "$(marche)"; else ligne "worker" "$(arret)"; fi
if pid_actif "$RUN/mailpit.pid"; then ligne "mailpit" "$(marche)"; else ligne "mailpit" "$(arret)"; fi
if curl -fs -o /dev/null "http://127.0.0.1:$SITE_PORT/api/health"; then
  ligne "site" "$(marche) → http://localhost:$SITE_PORT"
else
  ligne "site" "$(arret)"
fi
