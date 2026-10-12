#!/usr/bin/env bash
# Couche MÉTIER (vm-metier) : API FastAPI (N instances gunicorn), worker, Mailpit, migrations Alembic.
# Seule cette VM parle à vm-donnees ; elle n'accepte que Nginx (vm-presentation) sur les ports de l'API.
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"
APP=/opt/musicapp
DERNIER_PORT=$((API_FIRST_PORT + API_INSTANCES - 1))

etape "Paquets : Python, client NFS"
paquets python3-venv nfs-common curl ufw
creer_utilisateur_app
ecrire_hosts
ok "installés"

etape "Fichiers audio et covers : partage NFS de vm-donnees monté sur $MEDIA (lecture-écriture)"
monter_media rw
# Test en tant que musicapp : root, lui, n'a aucun droit sur le partage (root_squash le transforme en « nobody »)
setpriv --reuid=musicapp --regid=musicapp --init-groups \
  sh -c "touch '$MEDIA/audio/.test-ecriture' && rm '$MEDIA/audio/.test-ecriture'" \
  || erreur "l'utilisateur musicapp ne peut pas écrire dans $MEDIA"
ok "écriture vérifiée (utilisateur musicapp, UID 2000)"

etape "Jeu de données FMA : dossier partagé VirtualBox monté sur /fma (lecture seule)"
modinfo vboxsf > /dev/null 2>&1 || paquets "linux-modules-extra-$(uname -r)" || true
if modinfo vboxsf > /dev/null 2>&1; then
  install -d -m 755 /fma
  sed -i '/# musicapp-fma$/d' /etc/fstab
  echo "fma /fma vboxsf ro,gid=2000,dmode=0750,fmode=0640,nofail,x-systemd.automount 0 0 # musicapp-fma" >> /etc/fstab
  systemctl daemon-reload
  systemctl stop fma.mount fma.automount 2> /dev/null || true
  systemctl start fma.automount
  ok "disponible pour app.scripts.seed_fma (--metadata /fma/fma_metadata.zip --audio /fma/fma_small.zip)"
else
  ok "module vboxsf indisponible : import FMA impossible depuis cette VM"
fi

etape "Code de la couche métier et migrations ($APP)"
install -d -m 755 "$APP"
for dossier in metier donnees; do
  rm -rf "$APP/$dossier.nouveau"
  cp -r "$ICI/code/$dossier" "$APP/$dossier.nouveau"
  chown -R root:root "$APP/$dossier.nouveau"
  chmod -R u=rwX,go=rX "$APP/$dossier.nouveau"
  rm -rf "$APP/$dossier"
  mv "$APP/$dossier.nouveau" "$APP/$dossier"
done
[ -x "$APP/venv/bin/python" ] || python3 -m venv "$APP/venv"
empreinte="$(sha256sum "$APP/metier/requirements.txt" | cut -d' ' -f1)"
if [ "$(cat "$APP/venv/.requirements" 2> /dev/null)" != "$empreinte" ]; then
  "$APP/venv/bin/pip" install -q --upgrade pip
  "$APP/venv/bin/pip" install -q -r "$APP/metier/requirements.txt"
  echo "$empreinte" > "$APP/venv/.requirements"
fi
install -d -o musicapp -g musicapp /var/cache/musicapp
ok "$("$APP/venv/bin/python" --version), dépendances à jour"

etape "Configuration de l'application (/etc/musicapp)"
install -d -m 750 -o root -g musicapp /etc/musicapp
install -m 640 -o root -g musicapp /dev/null /etc/musicapp/metier.env
cat > /etc/musicapp/metier.env <<EOF
# Lu par systemd (EnvironmentFile) et par musicapp-python. Les autres VM sont désignées par leur nom (/etc/hosts).
DATABASE_URL="mysql+pymysql://$MYSQL_USER:$MYSQL_PASSWORD@vm-donnees:3306/$MYSQL_DATABASE?charset=utf8mb4"
REDIS_URL="redis://:$REDIS_PASSWORD@vm-donnees:6379/0"
ES_HOSTS="http://vm-donnees:9200"
ES_REPLICAS="0"
JWT_SECRET="$JWT_SECRET"
PUBLIC_URL="$PUBLIC_URL"
COOKIE_SECURE="$COOKIE_SECURE"
MEDIA_ROOT="$MEDIA"
SMTP_HOST="127.0.0.1"
SMTP_PORT="1025"
MAIL_FROM="$MAIL_FROM"
API_BIND="$IP_METIER"
WEB_CONCURRENCY="$WEB_CONCURRENCY"
FORWARDED_ALLOW_IPS="$IP_PRESENTATION"
PYTHONPYCACHEPREFIX="/var/cache/musicapp/pycache"
EOF
# Mots de passe des scripts (create_admin, seed_fma) : lisibles par root seulement
install -m 600 -o root -g root /dev/null /etc/musicapp/scripts.env
cat > /etc/musicapp/scripts.env <<EOF
ADMIN_PASSWORD="$ADMIN_PASSWORD"
SEED_ARTIST_PASSWORD="$SEED_ARTIST_PASSWORD"
EOF
install -m 755 "$FICHIERS/musicapp-python" /usr/local/bin/musicapp-python
ok "metier.env, scripts.env, commande musicapp-python"

etape "Mailpit (capture des emails)"
tar -xzf "$ICI/cache/$MAILPIT_ARCHIVE" -C /usr/local/bin mailpit
chmod 755 /usr/local/bin/mailpit
ok "$(/usr/local/bin/mailpit version 2> /dev/null | head -1)"

etape "Migrations Alembic (schéma MySQL sur vm-donnees)"
musicapp-python -m alembic -c "$APP/donnees/alembic.ini" upgrade head
ok "schéma à jour"

etape "Services systemd : Mailpit, worker, API ×$API_INSTANCES (ports $API_FIRST_PORT à $DERNIER_PORT)"
install -m 644 "$FICHIERS/mailpit.service" "$FICHIERS/musicapp-worker.service" "$FICHIERS/musicapp-api@.service" \
  /etc/systemd/system/
systemctl daemon-reload
systemctl enable -q mailpit musicapp-worker
systemctl restart mailpit musicapp-worker
# Instances en trop (si API_INSTANCES a baissé)
for lien in /etc/systemd/system/multi-user.target.wants/musicapp-api@*.service; do
  [ -e "$lien" ] || continue
  port="${lien##*@}"
  port="${port%.service}"
  if [ "$port" -gt "$DERNIER_PORT" ]; then systemctl disable -q --now "musicapp-api@$port"; fi
done
for ((port = API_FIRST_PORT; port <= DERNIER_PORT; port++)); do
  systemctl enable -q "musicapp-api@$port"
  systemctl restart "musicapp-api@$port"
done
for ((port = API_FIRST_PORT; port <= DERNIER_PORT; port++)); do
  attendre_url "http://$IP_METIER:$port/api/health" 60 \
    || erreur "l'API du port $port ne répond pas (journalctl -u musicapp-api@$port)"
done
ok "API, worker et Mailpit démarrés"

etape "Pare-feu : API pour vm-presentation seulement, Mailpit par la redirection de port"
pare_feu_debut
ufw allow from "$IP_PRESENTATION" to any port "$API_FIRST_PORT:$DERNIER_PORT" proto tcp comment 'API (vm-presentation)' > /dev/null
ufw allow in on "$(interface_nat)" to any port 8025 proto tcp comment 'Mailpit (redirection de port VirtualBox)' > /dev/null
pare_feu_fin
