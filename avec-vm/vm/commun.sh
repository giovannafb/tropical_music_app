#!/usr/bin/env bash
# Fonctions communes aux scripts exécutés DANS les VM (en root) : donnees.sh, metier.sh, presentation.sh.
# avec-vm/installer.sh copie ce dossier dans /tmp/musicapp-vm de chaque VM, avec reglages.env, puis le supprime.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_SUSPEND=1                   # apt : pas de liste des services à redémarrer

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FICHIERS="$ICI/fichiers"
[ "$(id -u)" -eq 0 ] || { echo "à lancer en root" >&2; exit 1; }
. "$ICI/reglages.env"

etape() { printf '\033[1;34m  [%s] %s\033[0m\n' "$(hostname)" "$1"; }
ok() { printf '\033[32m      %s\033[0m\n' "$1"; }
erreur() { printf '\033[31m  [%s] ERREUR : %s\033[0m\n' "$(hostname)" "$1" >&2; exit 1; }

# Dossier des fichiers audio et covers : sur vm-donnees (/srv/musicapp/media), partagé en NFS,
# monté au même endroit sur vm-metier (lecture-écriture) et vm-presentation (lecture seule)
MEDIA_SERVEUR=/srv/musicapp/media
MEDIA=/var/lib/musicapp/media

paquets() {
  if [ ! -f /var/lib/apt/periodic/musicapp-update ] || [ -n "$(find /var/lib/apt/periodic/musicapp-update -mmin +720)" ]; then
    apt-get update -q > /dev/null
    install -D /dev/null /var/lib/apt/periodic/musicapp-update
  fi
  apt-get install -y -q --no-install-recommends "$@" > /dev/null
}

# Utilisateur de l'application : même UID sur toutes les VM, car NFS vérifie les droits par numéro, pas par nom
creer_utilisateur_app() {
  getent group musicapp > /dev/null || groupadd --gid 2000 musicapp
  id musicapp > /dev/null 2>&1 \
    || useradd --uid 2000 --gid 2000 --home-dir /opt/musicapp --no-create-home --shell /usr/sbin/nologin musicapp
}

# Les VM se trouvent par leur nom (ce que faisait le DNS interne de Docker)
ecrire_hosts() {
  sed -i '/# musicapp-debut/,/# musicapp-fin/d' /etc/hosts
  cat >> /etc/hosts <<EOF
# musicapp-debut
$IP_PRESENTATION vm-presentation
$IP_METIER vm-metier
$IP_DONNEES vm-donnees
# musicapp-fin
EOF
}

# Un service qui écoute sur l'adresse privée doit attendre que le réseau soit configuré
attendre_reseau_pour() {
  local service="$1"
  mkdir -p "/etc/systemd/system/$service.service.d"
  printf '[Unit]\nAfter=network-online.target\nWants=network-online.target\n' \
    > "/etc/systemd/system/$service.service.d/musicapp-reseau.conf"
}

# Montage NFS du dossier media, à la demande (automount) : la VM démarre même si vm-donnees est éteinte
monter_media() {
  local options="$1" unite
  unite="$(systemd-escape -p "$MEDIA")"
  install -d -m 755 "$MEDIA"
  sed -i '/# musicapp-media$/d' /etc/fstab
  echo "vm-donnees:$MEDIA_SERVEUR $MEDIA nfs4 $options,_netdev,x-systemd.automount,x-systemd.mount-timeout=30 0 0 # musicapp-media" >> /etc/fstab
  systemctl daemon-reload
  systemctl stop "$unite.mount" "$unite.automount" 2> /dev/null || true
  systemctl start "$unite.automount"
  ls "$MEDIA/audio" > /dev/null || erreur "le partage NFS de vm-donnees est inaccessible"
}

# Nom de l'interface de la carte NAT (carte 1), repérée par son adresse MAC
interface_nat() { ip -o link | awk -v mac="$MAC_NAT" '$0 ~ mac { sub(":", "", $2); print $2 }'; }

# Pare-feu : tout est refusé en entrée, sauf SSH depuis WSL et les règles ajoutées par chaque couche
pare_feu_debut() {
  ufw --force reset > /dev/null
  rm -f /etc/ufw/*.rules.[0-9]* /etc/ufw/*.rules.*_[0-9]*
  ufw default deny incoming > /dev/null
  ufw default allow outgoing > /dev/null
  ufw allow from "$IP_HOTE" to any port 22 proto tcp comment 'SSH depuis WSL' > /dev/null
}
pare_feu_fin() {
  ufw --force enable > /dev/null
  ok "pare-feu actif : $(ufw status | grep -c ALLOW) règle(s)"
}

# Attend qu'une URL réponde (délai en secondes)
attendre_url() {
  local url="$1" delai="$2" i
  for ((i = 0; i < delai; i++)); do
    curl -fs -o /dev/null "$url" && return 0
    sleep 1
  done
  return 1
}
