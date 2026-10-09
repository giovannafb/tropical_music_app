#!/usr/bin/env bash
# Affiche l'état de chaque composant de la version distribuée.
#
#   bash sans-docker/etat.sh [db|api|web]
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"
charger_env

TARGET="${1:-}"
if [[ ! "$TARGET" =~ ^(db|api|web)$ ]]; then
  echo "Erreur: Définissez la cible de démarrage. Usage: $0 [db|api|web]"
  exit 1
fi

ligne() { printf '  %-22s %s\n' "$1" "$2"; }
marche() { printf '\033[32mdémarré\033[0m'; }
arret() { printf '\033[31marrêté\033[0m'; }

etape "Version sans Docker : $TARGET"

if [ "$TARGET" == "db" ]; then
  for service in mysql redis-server; do
    if systemctl is-active --quiet "$service"; then ligne "$service" "$(marche)"; else ligne "$service" "$(arret)"; fi
  done
  
  if curl -fs -o /dev/null "$ES_URL"; then
    ligne "elasticsearch" "$(marche) ($(curl -fs "$ES_URL/_cluster/health?filter_path=status" | tr -d '{}"'))"
  else
    ligne "elasticsearch" "$(arret)"
  fi
fi

if [ "$TARGET" == "api" ]; then
  shopt -s nullglob
  apis=("$RUN"/api-*.pid)
  [ ${#apis[@]} -eq 0 ] && ligne "api" "$(arret)"
  for fichier in "${apis[@]}"; do
    port="${fichier##*/api-}"
    if pid_actif "$fichier"; then ligne "api (port ${port%.pid})" "$(marche)"; else ligne "api (port ${port%.pid})" "$(arret)"; fi
  done
  if pid_actif "$RUN/worker.pid"; then ligne "worker" "$(marche)"; else ligne "worker" "$(arret)"; fi
  if pid_actif "$RUN/mailpit.pid"; then ligne "mailpit" "$(marche)"; else ligne "mailpit" "$(arret)"; fi
fi

if [ "$TARGET" == "web" ]; then
  for service in nginx; do
    if systemctl is-active --quiet "$service"; then ligne "$service" "$(marche)"; else ligne "$service" "$(arret)"; fi
  done

  if curl -fs -o /dev/null "http://127.0.0.1:$SITE_PORT/api/health"; then
    ligne "site" "$(marche) → http://localhost:$SITE_PORT"
  else
    ligne "site" "$(arret)"
  fi
fi