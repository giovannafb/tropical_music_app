#!/usr/bin/env bash
# Démarre la version sans Docker : MySQL, Redis, Elasticsearch, Mailpit, API ×N, worker, Nginx.
#
#   bash sans-docker/demarrer.sh
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"
charger_env

[ -x "$VENV/bin/gunicorn" ] && [ -x "$ES_HOME/bin/elasticsearch" ] && [ -x "$MAILPIT" ] \
  || erreur "installation incomplète : lance d'abord bash sans-docker/installer.sh"
mkdir -p "$RUN" "$LOGS"

# Les deux versions ne tiennent pas ensemble en mémoire
dispo_mo=$(awk '/MemAvailable/ {print int($2 / 1024)}' /proc/meminfo)
if [ "$dispo_mo" -lt 2500 ]; then
  echo "ATTENTION : seulement ${dispo_mo} Mo de mémoire libre. Si la version Docker tourne, arrête-la d'abord"
  echo "            (dans PowerShell : cd avec-docker puis docker compose stop)."
fi

etape "Services système : MySQL, Redis (mot de passe sudo demandé)"
[ "$(cat /proc/sys/vm/max_map_count)" -ge 262144 ] || sudo sysctl -q -w vm.max_map_count=262144
sudo systemctl start mysql redis-server
ok "MySQL et Redis démarrés"

etape "Elasticsearch (1 nœud)"
if curl -fs -o /dev/null "$ES_URL"; then
  ok "déjà démarré"
else
  # -d : en arrière-plan ; setsid : dans sa propre session, pour survivre à la fermeture du terminal.
  # La sortie console va dans un fichier (l'option -q est refusée avec -d).
  nohup setsid "$ES_HOME/bin/elasticsearch" -d -p "$RUN/elasticsearch.pid" > "$LOGS/elasticsearch-demarrage.log" 2>&1 \
    || erreur "Elasticsearch n'a pas démarré (voir $LOGS/elasticsearch-demarrage.log)"
  attendre_url "$ES_URL/_cluster/health?wait_for_status=yellow&timeout=1s" 120 \
    || erreur "Elasticsearch ne répond pas (journal : $LOGS/elasticsearch/musicapp-local.log)"
  ok "démarré"
fi

etape "Mailpit (emails)"
if pid_actif "$RUN/mailpit.pid"; then
  ok "déjà démarré"
else
  nohup "$MAILPIT" --listen "0.0.0.0:$MAILPIT_UI_PORT" --smtp "127.0.0.1:$MAILPIT_SMTP_PORT" \
    > "$LOGS/mailpit.log" 2>&1 &
  echo $! > "$RUN/mailpit.pid"
  ok "démarré"
fi

etape "Migrations Alembic (couche données)"
cd "$PROJET/metier"
"$VENV/bin/alembic" -c "$PROJET/donnees/alembic.ini" upgrade head
touch "$RUN/base-prete"      # utilisé par executer.sh
ok "schéma à jour"

etape "API : $API_INSTANCES instance(s) gunicorn × $WEB_CONCURRENCY worker(s)"
for ((i = 0; i < API_INSTANCES; i++)); do
  port=$((API_FIRST_PORT + i))
  if pid_actif "$RUN/api-$port.pid"; then ok "port $port : déjà démarrée"; continue; fi
  "$VENV/bin/gunicorn" app.main:app -k uvicorn.workers.UvicornWorker -w "$WEB_CONCURRENCY" \
    -b "127.0.0.1:$port" --daemon --pid "$RUN/api-$port.pid" \
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

etape "Nginx (port $SITE_PORT)"
generer_conf_nginx > "$RUN/nginx-musicapp.conf"
sudo install -m 644 "$RUN/nginx-musicapp.conf" /etc/nginx/sites-available/musicapp
sudo ln -sf /etc/nginx/sites-available/musicapp /etc/nginx/sites-enabled/musicapp
sudo nginx -t -q
sudo systemctl restart nginx
attendre_url "http://127.0.0.1:$SITE_PORT/api/health" 30 \
  || erreur "l'API ne répond pas derrière Nginx (journaux : $LOGS/api-*.log)"
ok "prêt"

etape "MusicApp (sans Docker) est démarrée"
echo "    Application : http://localhost:$SITE_PORT"
echo "    API (docs)  : http://localhost:$SITE_PORT/api/docs"
echo "    Emails      : http://localhost:$MAILPIT_UI_PORT"
echo "    Journaux    : $LOGS"
echo "    Arrêt       : bash sans-docker/arreter.sh"
