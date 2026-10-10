#!/usr/bin/env bash
# Installation de la version sans Docker dans Ubuntu (WSL). À lancer une seule fois
# (le relancer ne casse rien : chaque étape vérifie ce qui est déjà fait).
#
#   bash sans-docker/installer.sh
#
# Téléchargements : paquets Ubuntu (~250 Mo), Elasticsearch 8.15.3 (~600 Mo, artifacts.elastic.co),
# Mailpit (~15 Mo, github.com/axllent/mailpit), dépendances Python (~100 Mo, PyPI).
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"
charger_env

mkdir -p "$LOCAL/bin" "$RUN" "$LOGS"

TARGET="${1:-}"
if [[ ! "$TARGET" =~ ^(db|api|web)$ ]]; then
  echo "Erreur: Définissez la cible d'installation. Usage: $0 [db|api|web]"
  exit 1
fi

# Les services ne démarrent pas pendant l'installation : Nginx tenterait d'utiliser le port 80,
# déjà pris par la version Docker. C'est demarrer.sh qui les lance.
BLOQUEUR=""
if [ ! -e /usr/sbin/policy-rc.d ]; then
  printf '#!/bin/sh\nexit 101\n' | sudo tee /usr/sbin/policy-rc.d > /dev/null
  sudo chmod 755 /usr/sbin/policy-rc.d
  BLOQUEUR=1
  trap 'sudo rm -f /usr/sbin/policy-rc.d' EXIT
fi

sudo apt-get update
if [ "$TARGET" == "db" ]; then
  etape "1/5 Paquets Ubuntu : MySQL and Redis"
  sudo apt-get install -y mysql-server redis-server curl
  sudo systemctl disable mysql redis-server 2>/dev/null || true
elif [ "$TARGET" == "api" ]; then
  etape "1/4 Paquets Ubuntu : Python (mot de passe sudo demandé)"
  sudo apt-get install -y python3-venv curl
elif [ "$TARGET" == "web" ]; then
  etape "1/3 Paquets Ubuntu : Nginx"
  sudo apt-get install -y nginx curl
  sudo systemctl disable nginx 2>/dev/null || true
fi

if [ -n "$BLOQUEUR" ]; then sudo rm -f /usr/sbin/policy-rc.d; trap - EXIT; fi
# Pas de démarrage automatique : ces services ne tournent que quand on lance cette version
ok "paquets installés"

if [ "$TARGET" == "db" ]; then
  etape "2/5 Réglage système pour Elasticsearch (vm.max_map_count)"
  echo 'vm.max_map_count=262144' | sudo tee /etc/sysctl.d/99-musicapp.conf > /dev/null
  sudo sysctl -q -w vm.max_map_count=262144
  ok "vm.max_map_count = $(cat /proc/sys/vm/max_map_count)"

  etape "3/5 MySQL : configuration utf8mb4, base et utilisateur"
  # Même fichier de configuration que la version Docker (couche données)
  sudo install -m 644 "$PROJET/donnees/mysql/conf.d/musicapp.cnf" /etc/mysql/mysql.conf.d/zz-musicapp.cnf
  sudo systemctl restart mysql
  MDP_SQL="${MYSQL_PASSWORD//\'/\'\'}"
  sudo mysql <<SQL
CREATE DATABASE IF NOT EXISTS \`$MYSQL_DATABASE\` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER IF NOT EXISTS '$MYSQL_USER'@'localhost' IDENTIFIED BY '$MDP_SQL';
CREATE USER IF NOT EXISTS '$MYSQL_USER'@'${HOST_BACKEND}' IDENTIFIED BY '$MDP_SQL';
ALTER USER '$MYSQL_USER'@'localhost' IDENTIFIED BY '$MDP_SQL';
ALTER USER '$MYSQL_USER'@'${HOST_BACKEND}' IDENTIFIED BY '$MDP_SQL';
GRANT ALL PRIVILEGES ON \`$MYSQL_DATABASE\`.* TO '$MYSQL_USER'@'localhost';
GRANT ALL PRIVILEGES ON \`$MYSQL_DATABASE\`.* TO '$MYSQL_USER'@'${HOST_BACKEND}';
SQL
  sudo systemctl stop mysql
  ok "base « $MYSQL_DATABASE » et utilisateur « $MYSQL_USER » prêts"

  etape "4/5 Elasticsearch $ES_VERSION (un seul nœud, dans $ES_HOME)"
  if [ ! -x "$ES_HOME/bin/elasticsearch" ]; then
    archive="elasticsearch-$ES_VERSION-linux-x86_64.tar.gz"
    url="https://artifacts.elastic.co/downloads/elasticsearch/$archive"
    curl -fL --progress-bar -o "$LOCAL/$archive" "$url"
    curl -fsL -o "$LOCAL/$archive.sha512" "$url.sha512"
    (cd "$LOCAL" && sha512sum -c "$archive.sha512")
    tar -xzf "$LOCAL/$archive" -C "$LOCAL"
    rm -f "$LOCAL/$archive" "$LOCAL/$archive.sha512"
  fi
  mkdir -p "$LOCAL/es-data" "$LOGS/elasticsearch"
  # Configuration écrite avant le premier démarrage : la sécurité n'est donc jamais auto-configurée
  cat > "$ES_HOME/config/elasticsearch.yml" <<YML
cluster.name: musicapp-local
node.name: local-1
path.data: $LOCAL/es-data
path.logs: $LOGS/elasticsearch
network.host: 0.0.0.0
http.port: 9200
discovery.type: single-node
# Développement uniquement : sécurité (TLS + mot de passe) désactivée, comme la version Docker
xpack.security.enabled: false
YML
  printf -- '-Xms512m\n-Xmx512m\n' > "$ES_HOME/config/jvm.options.d/musicapp.options"
  ok "Elasticsearch installé"

  etape "5/5 Réglage système pour Redis"
  sudo sed -i 's/bind 127.0.0.1/bind 0.0.0.0/g' /etc/redis/redis.conf
  sudo sed -i 's/^protected-mode yes/protected-mode no/' /etc/redis/redis.conf
  sudo systemctl restart redis-server
fi

if [ "$TARGET" == "api" ]; then
  etape "2/4 Dossier des fichiers audio et covers ($MEDIA)"
  sudo install -d -o "$USER" -g "$USER" -m 755 /var/lib/musicapp "$MEDIA" "$MEDIA/audio" "$MEDIA/covers"
  sudo chmod -R 755 /var/lib/musicapp/media
  ok "dossier prêt"

  etape "3/4 Python : environnement virtuel et dépendances de l'API"
  [ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --upgrade pip
  "$VENV/bin/pip" install -q -r "$PROJET/metier/requirements.txt"
  ok "$("$VENV/bin/python" --version) dans $VENV"


  etape "4/4 Mailpit (capture des emails en développement)"
  if [ ! -x "$MAILPIT" ]; then
    curl -fL --progress-bar -o "$LOCAL/mailpit.tar.gz" \
      https://github.com/axllent/mailpit/releases/latest/download/mailpit-linux-amd64.tar.gz
    tar -xzf "$LOCAL/mailpit.tar.gz" -C "$LOCAL/bin" mailpit
    rm -f "$LOCAL/mailpit.tar.gz"
  fi
  ok "$("$MAILPIT" version 2>/dev/null | head -1)"
fi

if [ "$TARGET" == "web" ]; then
  etape "2/3 Nginx : retrait du site par défaut (port 80 réservé à la version Docker)"
  sudo rm -f /etc/nginx/sites-enabled/default

  etape "3/3 SSHFS et configuration FUSE:" 
  #Utilisé pour faire une liaison entre les dossiers de media dans 
  #la machine de front et les mêmes dossiers dans la machine de backend
  sudo apt-get install -y sshfs
  sudo sed -i 's/^#user_allow_other/user_allow_other/' /etc/fuse.conf
  sudo mkdir -p /var/lib/musicapp/media
  sudo chown -R $USER:$USER /var/lib/musicapp
  ok "la configuration MusicApp est générée à chaque démarrage par demarrer.sh"
fi

etape "Installation terminée"
echo "    Étape suivante : bash sans-docker/demarrer.sh"
