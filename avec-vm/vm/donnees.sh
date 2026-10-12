#!/usr/bin/env bash
# Couche DONNÉES (vm-donnees) : MySQL, Redis, Elasticsearch (1 nœud) et partage NFS des fichiers audio / covers.
# Chaque service écoute sur l'adresse privée et n'accepte que vm-metier (sauf NFS, en lecture seule pour vm-presentation).
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"

etape "Paquets : MySQL, Redis, serveur NFS"
paquets mysql-server redis-server nfs-kernel-server curl ufw
creer_utilisateur_app
ecrire_hosts
ok "installés"

etape "MySQL : utf8mb4, écoute sur $IP_DONNEES, compte réservé à vm-metier"
# Même configuration utf8mb4 que les autres versions (donnees/mysql/conf.d/musicapp.cnf)
install -m 644 "$FICHIERS/musicapp.cnf" /etc/mysql/mysql.conf.d/zz-musicapp.cnf
cat > /etc/mysql/mysql.conf.d/zz-musicapp-vm.cnf <<EOF
[mysqld]
# Joignable sur le réseau privé (par défaut : 127.0.0.1 seulement)
bind-address = $IP_DONNEES
mysqlx-bind-address = 127.0.0.1
# VM à mémoire limitée : les statistiques de performance (~200 Mo) sont désactivées
performance_schema = OFF
EOF
attendre_reseau_pour mysql
systemctl daemon-reload
systemctl enable -q mysql
systemctl restart mysql
MDP_SQL="${MYSQL_PASSWORD//\'/\'\'}"
mysql <<SQL
CREATE DATABASE IF NOT EXISTS \`$MYSQL_DATABASE\` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
-- Un compte MySQL = un utilisateur + l'adresse d'où il se connecte : ici, uniquement vm-metier
CREATE USER IF NOT EXISTS '$MYSQL_USER'@'$IP_METIER' IDENTIFIED BY '$MDP_SQL';
ALTER USER '$MYSQL_USER'@'$IP_METIER' IDENTIFIED BY '$MDP_SQL';
GRANT ALL PRIVILEGES ON \`$MYSQL_DATABASE\`.* TO '$MYSQL_USER'@'$IP_METIER';
SQL
ok "base « $MYSQL_DATABASE », utilisateur « $MYSQL_USER »@$IP_METIER"

etape "Redis : écoute sur $IP_DONNEES, mot de passe obligatoire"
install -m 640 -o redis -g redis /dev/null /etc/redis/musicapp.conf
cat > /etc/redis/musicapp.conf <<EOF
# Chargé à la fin de redis.conf : ces valeurs remplacent celles du fichier d'origine
bind 127.0.0.1 $IP_DONNEES
protected-mode yes
requirepass $REDIS_PASSWORD
appendonly yes
EOF
grep -qxF 'include /etc/redis/musicapp.conf' /etc/redis/redis.conf \
  || echo 'include /etc/redis/musicapp.conf' >> /etc/redis/redis.conf
attendre_reseau_pour redis-server
systemctl daemon-reload
systemctl enable -q redis-server
systemctl restart redis-server
ok "prêt"

etape "Elasticsearch $ES_VERSION (1 nœud, écoute sur $IP_DONNEES)"
id elasticsearch > /dev/null 2>&1 \
  || useradd --system --home-dir /opt/elasticsearch --no-create-home --shell /usr/sbin/nologin elasticsearch
if [ ! -x "/opt/elasticsearch-$ES_VERSION/bin/elasticsearch" ]; then
  [ -f "$ICI/cache/$ES_ARCHIVE" ] || erreur "archive Elasticsearch absente"
  tar -xzf "$ICI/cache/$ES_ARCHIVE" -C /opt
fi
ln -sfn "/opt/elasticsearch-$ES_VERSION" /opt/elasticsearch
# Configuration écrite avant le premier démarrage : la sécurité n'est donc jamais auto-configurée
cat > /opt/elasticsearch/config/elasticsearch.yml <<EOF
cluster.name: musicapp-vm
node.name: vm-donnees
path.data: /var/lib/elasticsearch
path.logs: /var/log/elasticsearch
network.host: [_local_, "$IP_DONNEES"]
http.port: 9200
discovery.type: single-node
# Développement uniquement : sécurité (TLS + mot de passe) désactivée, comme les autres versions ;
# l'accès est limité à vm-metier par le pare-feu
xpack.security.enabled: false
EOF
printf -- '-Xms512m\n-Xmx512m\n' > /opt/elasticsearch/config/jvm.options.d/musicapp.options
install -d /var/lib/elasticsearch /var/log/elasticsearch
chown -R elasticsearch:elasticsearch "/opt/elasticsearch-$ES_VERSION" /var/lib/elasticsearch /var/log/elasticsearch
echo 'vm.max_map_count=262144' > /etc/sysctl.d/99-elasticsearch.conf
sysctl -q -p /etc/sysctl.d/99-elasticsearch.conf
install -m 644 "$FICHIERS/elasticsearch.service" /etc/systemd/system/elasticsearch.service
systemctl daemon-reload
systemctl enable -q elasticsearch
systemctl restart elasticsearch
attendre_url "http://127.0.0.1:9200/_cluster/health?wait_for_status=yellow&timeout=1s" 180 \
  || erreur "Elasticsearch ne répond pas (journalctl -u elasticsearch)"
ok "état du cluster : $(curl -fs 'http://127.0.0.1:9200/_cluster/health?filter_path=status' | tr -d '{}"' | cut -d: -f2)"

etape "Partage NFS des fichiers audio et covers ($MEDIA_SERVEUR)"
install -d -o musicapp -g musicapp -m 755 "$MEDIA_SERVEUR" "$MEDIA_SERVEUR/audio" "$MEDIA_SERVEUR/covers"
install -d -m 755 /etc/exports.d
cat > /etc/exports.d/musicapp.exports <<EOF
# Écrits par l'API (vm-metier), lus par Nginx (vm-presentation) en lecture seule
$MEDIA_SERVEUR $IP_METIER(rw,sync,no_subtree_check) $IP_PRESENTATION(ro,sync,no_subtree_check)
EOF
systemctl enable -q nfs-server
systemctl restart nfs-server
exportfs -ra
ok "partagé vers vm-metier (lecture-écriture) et vm-presentation (lecture seule)"

etape "Pare-feu : n'accepte que vm-metier (et NFS pour vm-presentation)"
pare_feu_debut
ufw allow from "$IP_METIER" to any port 3306 proto tcp comment 'MySQL (vm-metier)' > /dev/null
ufw allow from "$IP_METIER" to any port 6379 proto tcp comment 'Redis (vm-metier)' > /dev/null
ufw allow from "$IP_METIER" to any port 9200 proto tcp comment 'Elasticsearch (vm-metier)' > /dev/null
ufw allow from "$IP_METIER" to any port 2049 proto tcp comment 'NFS (vm-metier)' > /dev/null
ufw allow from "$IP_PRESENTATION" to any port 2049 proto tcp comment 'NFS lecture seule (vm-presentation)' > /dev/null
pare_feu_fin
