#!/usr/bin/env bash
# Démarre la version distribuée : base de données, API, ou Nginx.
#
#   bash sans-docker/demarrer.sh [db|api|web]
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"
charger_env

TARGET="${1:-}"
if [[ ! "$TARGET" =~ ^(db|api|web)$ ]]; then
  echo "Erreur: Définissez la cible de démarrage. Usage: $0 [db|api|web]"
  exit 1
fi

# Vérification des dépendances séparée par machine
if [ "$TARGET" == "db" ]; then
  [ -x "$ES_HOME/bin/elasticsearch" ] || erreur "installation incomplète : lance d'abord bash sans-docker/installer.sh db"
elif [ "$TARGET" == "api" ]; then
  [ -x "$VENV/bin/gunicorn" ] && [ -x "$MAILPIT" ] || erreur "installation incomplète : lance d'abord bash sans-docker/installer.sh api"
fi

mkdir -p "$RUN" "$LOGS"

dispo_mo=$(awk '/MemAvailable/ {print int($2 / 1024)}' /proc/meminfo)
if [ "$dispo_mo" -lt 2500 ]; then
  echo "ATTENTION : seulement ${dispo_mo} Mo de mémoire libre. Si la version Docker tourne, arrête-la d'abord"
fi

if [ "$TARGET" == "db" ]; then
  etape "Services système : MySQL, Redis (mot de passe sudo demandé)"
  [ "$(cat /proc/sys/vm/max_map_count)" -ge 262144 ] || sudo sysctl -q -w vm.max_map_count=262144
  sudo systemctl start mysql redis-server
  ok "MySQL et Redis démarrés"

  etape "Elasticsearch (1 nœud)"
  # Utilise 127.0.0.1 spécifiquement pour la vérification locale sur la VM
  if curl -fs -o /dev/null "http://127.0.0.1:9200"; then
    ok "déjà démarré"
  else
    nohup setsid "$ES_HOME/bin/elasticsearch" -d -p "$RUN/elasticsearch.pid" > "$LOGS/elasticsearch-demarrage.log" 2>&1 \
      || erreur "Elasticsearch n'a pas démarré (voir $LOGS/elasticsearch-demarrage.log)"
    attendre_url "http://127.0.0.1:9200/_cluster/health?wait_for_status=yellow&timeout=1s" 120 \
      || erreur "Elasticsearch ne répond pas (journal : $LOGS/elasticsearch/musicapp-local.log)"
    ok "démarré"
  fi
fi

if [ "$TARGET" == "api" ]; then
  etape "Mailpit (emails)"
  if pid_actif "$RUN/mailpit.pid"; then
    ok "déjà démarré"
  else
    # Changement pour écouter sur toutes les interfaces (0.0.0.0)
    nohup "$MAILPIT" --listen "0.0.0.0:$MAILPIT_UI_PORT" --smtp "0.0.0.0:$MAILPIT_SMTP_PORT" \
      > "$LOGS/mailpit.log" 2>&1 &
    echo $! > "$RUN/mailpit.pid"
    ok "démarré"
  fi

  etape "Migrations Alembic (couche données)"
  cd "$PROJET/metier"
  "$VENV/bin/alembic" -c "$PROJET/donnees/alembic.ini" upgrade head
  touch "$RUN/base-prete"
  ok "schéma à jour"

  etape "API : $API_INSTANCES instance(s) gunicorn × $WEB_CONCURRENCY worker(s)"
  for ((i = 0; i < API_INSTANCES; i++)); do
    port=$((API_FIRST_PORT + i))
    if pid_actif "$RUN/api-$port.pid"; then ok "port $port : déjà démarrée"; continue; fi
    # Changement du bind de 127.0.0.1 à 0.0.0.0 pour accepter les requêtes de Nginx
    "$VENV/bin/gunicorn" app.main:app -k uvicorn.workers.UvicornWorker -w "$WEB_CONCURRENCY" \
      -b "0.0.0.0:$port" --daemon --pid "$RUN/api-$port.pid" \
      --access-logfile "$LOGS/api-$port.log" --error-logfile "$LOGS/api-$port.log"
    ok "port $port"
  done

  etape "Worker (indexation Elasticsearch, emails, compteurs)"
  if pid_actif "$RUN/worker.pid"; then
    ok "déjà démarré"
  else
    nohup "$VENV/bin/python" -m app.workers.main > "$LOGS/worker.log" 2>&1 &
    echo $! > "$RUN/worker.pid"
    ok "démarré"
  fi
fi

if [ "$TARGET" == "web" ]; then
  etape "Nginx (port $SITE_PORT)"
  generer_conf_nginx > "$RUN/nginx-musicapp.conf"
  sudo install -m 644 "$RUN/nginx-musicapp.conf" /etc/nginx/sites-available/musicapp
  sudo ln -sf /etc/nginx/sites-available/musicapp /etc/nginx/sites-enabled/musicapp
  sudo nginx -t -q
  sudo systemctl restart nginx
  attendre_url "http://127.0.0.1:$SITE_PORT/api/health" 30 \
    || erreur "l'API ne répond pas derrière Nginx (journaux : $LOGS/api-*.log)"
  ok "prêt"

  etape "MusicApp distribuée est démarrée"
  echo "    Application : http://localhost:$SITE_PORT"
  echo "    API (docs)  : http://localhost:$SITE_PORT/api/docs"
  echo "    Emails      : http://${HOST_BACKEND:-localhost}:$MAILPIT_UI_PORT"
  echo "    Journaux    : $LOGS"
  echo "    Arrêt       : bash sans-docker/arreter.sh"
fi