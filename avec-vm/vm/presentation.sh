#!/usr/bin/env bash
# Couche PRÉSENTATION (vm-presentation) : Nginx sert la SPA (client/), répartit /api/ entre les instances
# de vm-metier et envoie les fichiers audio / covers, lus sur le partage NFS de vm-donnees (lecture seule).
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"
SITE=/var/www/musicapp

etape "Paquets : Nginx, client NFS"
paquets nginx nfs-common curl ufw
ecrire_hosts
ok "installés"

etape "Fichiers audio et covers : partage NFS de vm-donnees monté sur $MEDIA (lecture seule)"
monter_media ro
ok "monté"

etape "Client (SPA) dans $SITE"
rm -rf "$SITE.nouveau"
cp -r "$ICI/code/client" "$SITE.nouveau"
chown -R root:root "$SITE.nouveau"
chmod -R u=rwX,go=rX "$SITE.nouveau"
rm -rf "$SITE"
mv "$SITE.nouveau" "$SITE"
ok "copié"

etape "Nginx : $API_INSTANCES instance(s) d'API sur vm-metier"
serveurs=""
for ((i = 0; i < API_INSTANCES; i++)); do
  serveurs+="    server vm-metier:$((API_FIRST_PORT + i));"$'\n'
done
conf="$(< "$FICHIERS/nginx-musicapp.conf.modele")"
conf="${conf//@SERVEURS_API@/${serveurs%$'\n'}}"
conf="${conf//@SITE@/$SITE}"
conf="${conf//@MEDIA@/$MEDIA}"
printf '%s\n' "$conf" > /etc/nginx/sites-available/musicapp
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/musicapp /etc/nginx/sites-enabled/musicapp
nginx -t -q
systemctl enable -q nginx
systemctl restart nginx
attendre_url "http://127.0.0.1/api/health" 30 || erreur "l'API ne répond pas derrière Nginx"
ok "le site répond et joint l'API"

etape "Pare-feu : port 80 par la redirection de port VirtualBox (et depuis WSL)"
pare_feu_debut
ufw allow in on "$(interface_nat)" to any port 80 proto tcp comment 'Site (redirection de port VirtualBox)' > /dev/null
ufw allow from "$IP_HOTE" to any port 80 proto tcp comment 'Site (tests depuis WSL)' > /dev/null
pare_feu_fin
