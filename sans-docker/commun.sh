#!/usr/bin/env bash
# Réglages et fonctions communs aux scripts de la version sans Docker.
# Ce fichier est chargé par les autres scripts (ne pas l'exécuter directement).
set -euo pipefail

SANS_DOCKER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJET="$(cd "$SANS_DOCKER/.." && pwd)"

# Logiciels installés hors du projet, dans le système de fichiers Linux (plus rapide que /mnt/c)
LOCAL="$HOME/.musicapp"
VENV="$LOCAL/venv"
ES_VERSION="8.15.3"                        # même version que la version Docker
ES_HOME="$LOCAL/elasticsearch-$ES_VERSION"
MAILPIT="$LOCAL/bin/mailpit"
RUN="$LOCAL/run"                           # fichiers PID
LOGS="$LOCAL/logs"

# Fichiers audio et covers : hors du dossier personnel, qui n'est pas lisible par Nginx
MEDIA="/var/lib/musicapp/media"

# Ports choisis pour ne jamais entrer en conflit avec la version Docker (80, 8025, 5601)
SITE_PORT=8080
MAILPIT_UI_PORT=8026
MAILPIT_SMTP_PORT=1026
API_FIRST_PORT=8000
#ES_URL="http://${HOST_DB}:9200"

etape() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
ok() { printf '\033[32m    %s\033[0m\n' "$1"; }
erreur() { printf '\033[31mERREUR : %s\033[0m\n' "$1" >&2; exit 1; }

# Lit sans-docker/.env (même format que avec-docker/.env) et prépare l'environnement de l'application
charger_env() {
  local fichier="$SANS_DOCKER/.env" ligne cle valeur
  [ -f "$fichier" ] || erreur "fichier sans-docker/.env introuvable. Crée-le avec : cp sans-docker/.env.example sans-docker/.env"
  while IFS= read -r ligne || [ -n "$ligne" ]; do
    ligne="${ligne%$'\r'}"                       # fichier éventuellement édité sous Windows
    [[ -z "$ligne" || "$ligne" == \#* ]] && continue
    cle="${ligne%%=*}"
    valeur="${ligne#*=}"
    [[ "$cle" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    if [[ "$valeur" =~ ^\"(.*)\"$ || "$valeur" =~ ^\'(.*)\'$ ]]; then valeur="${BASH_REMATCH[1]}"; fi
    export "$cle=$valeur"
  done < "$fichier"

  for cle in MYSQL_DATABASE MYSQL_USER MYSQL_PASSWORD JWT_SECRET; do
    [ -n "${!cle:-}" ] || erreur "$cle est vide dans sans-docker/.env"
    [[ "${!cle}" == change-me* ]] && erreur "remplace la valeur « change-me » de $cle dans sans-docker/.env"
  done

  local mot_de_passe
  mot_de_passe="$(python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$MYSQL_PASSWORD")"
  export DATABASE_URL="mysql+pymysql://${MYSQL_USER}:${mot_de_passe}@${HOST_DB}:3306/${MYSQL_DATABASE}?charset=utf8mb4"
  export REDIS_URL="redis://${HOST_DB}:6379/0"
  export ES_URL="http://${HOST_DB}:9200"  
  export ES_HOSTS="$ES_URL"
  export ES_REPLICAS=0                          # un seul nœud : pas de réplique possible
  export MEDIA_ROOT="$MEDIA"
  export SMTP_HOST=127.0.0.1 SMTP_PORT="$MAILPIT_SMTP_PORT"
  export PUBLIC_URL="http://${HOST_FRONT}:$SITE_PORT"
  export PYTHONPYCACHEPREFIX="$LOCAL/pycache"   # pas de __pycache__ dans le projet
  API_INSTANCES="${API_INSTANCES:-3}"
  WEB_CONCURRENCY="${WEB_CONCURRENCY:-2}"
  [[ "$API_INSTANCES" =~ ^[1-9]$ ]] || erreur "API_INSTANCES doit être un nombre entre 1 et 9"
}

# Vrai si le processus du fichier PID tourne encore
pid_actif() { [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null; }

# Attend qu'une URL réponde (délai en secondes)
attendre_url() {
  local url="$1" delai="$2" i
  for ((i = 0; i < delai; i++)); do
    curl -fs -o /dev/null "$url" && return 0
    sleep 1
  done
  return 1
}

# Configuration Nginx générée depuis le modèle : ports, chemins et nombre d'instances d'API
generer_conf_nginx() {
  local conf serveurs="" i
  shopt -u patsub_replacement 2>/dev/null || true   # bash 5.2 : « & » reste littéral dans les remplacements
  for ((i = 0; i < API_INSTANCES; i++)); do
    serveurs+="    server 127.0.0.1:$((API_FIRST_PORT + i));"$'\n'
  done
  conf="$(<"$SANS_DOCKER/nginx/musicapp.conf.modele")"
  conf="${conf//@SERVEURS_API@/${serveurs%$'\n'}}"
  conf="${conf//@SITE_PORT@/$SITE_PORT}"
  conf="${conf//@CLIENT@/$PROJET/client}"
  conf="${conf//@MEDIA@/$MEDIA}"
  printf '%s\n' "$conf"
}
