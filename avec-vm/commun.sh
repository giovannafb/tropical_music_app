#!/usr/bin/env bash
# Réglages et fonctions communs aux scripts de la version VM, lancés depuis Ubuntu (WSL), où tourne VirtualBox.
# Ce fichier est chargé par les autres scripts (ne pas l'exécuter directement).
set -euo pipefail

AVEC_VM="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJET="$(cd "$AVEC_VM/.." && pwd)"

# Fichiers hors du projet, dans le système de fichiers Linux (plus rapide que /mnt/c)
LOCAL="$HOME/.musicapp-vm"
CACHE="$LOCAL/cache"                           # téléchargements (gardés pour recréer les VM sans tout retélécharger)
CLE_SSH="$LOCAL/cle_ssh"                       # clé SSH dédiée aux 3 VM
SEMENCES="$LOCAL/cloud-init"                   # configuration du premier démarrage (cloud-init)
DISQUE_BASE="$LOCAL/ubuntu-24.04-base.vdi"     # disque Ubuntu Server de départ, cloné pour chaque VM
DOSSIER_VMS="$HOME/VirtualBox VMs/MusicApp"

UBUNTU_OVA="noble-server-cloudimg-amd64.ova"   # image « cloud » officielle d'Ubuntu Server 24.04
UBUNTU_URL="https://cloud-images.ubuntu.com/noble/current"
ES_VERSION="8.15.3"                            # même version que les deux autres versions
ES_ARCHIVE="elasticsearch-$ES_VERSION-linux-x86_64.tar.gz"
MAILPIT_ARCHIVE="mailpit-linux-amd64.tar.gz"

# Les 3 VM, dans l'ordre de démarrage : chaque couche a besoin de celle du dessous
ROLES=(donnees metier presentation)

# Réseau privé hôte (host-only) : WSL y a l'adresse 192.168.56.1, chaque VM une adresse fixe
RESEAU_HOTE=vboxnet0
IP_HOTE=192.168.56.1
declare -A IP=([presentation]=192.168.56.11 [metier]=192.168.56.12 [donnees]=192.168.56.13)
declare -A DISQUE_MO=([presentation]=10240 [metier]=20480 [donnees]=30720)

# Ports ouverts sur la machine (redirections de port VirtualBox, sur 127.0.0.1 uniquement).
# Différents de ceux des autres versions (80/8025 Docker, 8080/8026 sans Docker) : aucun conflit.
SITE_PORT=8081          # -> vm-presentation:80 (Nginx)
MAILPIT_PORT=8027       # -> vm-metier:8025 (interface web de Mailpit)
SEMENCES_PORT=8099      # serveur web temporaire de cloud-init (premier démarrage uniquement)
API_FIRST_PORT=8000     # API sur vm-metier : 8000, 8001…

etape() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
ok() { printf '\033[32m    %s\033[0m\n' "$1"; }
info() { printf '    %s\n' "$1"; }
erreur() { printf '\033[31mERREUR : %s\033[0m\n' "$1" >&2; exit 1; }

# VBoxManage, sans le message parasite de WSLg (« screen size is bogus »)
vbox() {
  local code=0
  VBoxManage "$@" 2> >(grep -v 'screen size is bogus' >&2) || code=$?
  return "$code"
}

nom_vm() { echo "vm-$1"; }
# Adresses MAC fixes : la configuration réseau de chaque VM reconnaît ses cartes par leur MAC
mac_nat() { printf '0800270A00%s' "${IP[$1]##*.}"; }
mac_prive() { printf '0800270B00%s' "${IP[$1]##*.}"; }
avec_deux_points() { echo "$1" | sed 's/../&:/g; s/:$//' | tr 'A-F' 'a-f'; }

vm_existe() { vbox showvminfo "$(nom_vm "$1")" > /dev/null 2>&1; }
etat_vm() {
  vbox showvminfo "$(nom_vm "$1")" --machinereadable 2>/dev/null | sed -n 's/^VMState="\(.*\)"$/\1/p'
}
vm_allumee() { [ "$(etat_vm "$1")" = "running" ]; }

verifier_virtualbox() {
  command -v VBoxManage > /dev/null || erreur "VirtualBox n'est pas installé dans cet Ubuntu"
  [ -e /dev/vboxdrv ] || erreur "le module vboxdrv n'est pas chargé (sudo modprobe vboxdrv, ou sudo /sbin/vboxconfig)"
}

# Lit avec-vm/.env ; au premier lancement, le crée depuis .env.example avec des secrets aléatoires
charger_env() {
  local fichier="$AVEC_VM/.env" ligne cle valeur
  if [ ! -f "$fichier" ]; then
    python3 - "$AVEC_VM/.env.example" "$fichier" <<'PY'
import re, secrets, sys
source, cible = sys.argv[1:]
texte = open(source, encoding="utf-8").read()
texte = re.sub(r"=change-me$", lambda m: "=" + secrets.token_urlsafe(24).replace("-", "x").replace("_", "y"), texte, flags=re.M)
open(cible, "w", encoding="utf-8").write(texte)
PY
    chmod 600 "$fichier"
    ok "avec-vm/.env créé avec des mots de passe aléatoires (modifiable)"
  fi
  while IFS= read -r ligne || [ -n "$ligne" ]; do
    ligne="${ligne%$'\r'}"                       # fichier éventuellement édité sous Windows
    [[ -z "$ligne" || "$ligne" == \#* ]] && continue
    cle="${ligne%%=*}"
    valeur="${ligne#*=}"
    [[ "$cle" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    if [[ "$valeur" =~ ^\"(.*)\"$ || "$valeur" =~ ^\'(.*)\'$ ]]; then valeur="${BASH_REMATCH[1]}"; fi
    export "$cle=$valeur"
  done < "$fichier"

  for cle in MYSQL_DATABASE MYSQL_USER MYSQL_PASSWORD REDIS_PASSWORD JWT_SECRET ADMIN_PASSWORD SEED_ARTIST_PASSWORD VM_PASSWORD; do
    [ -n "${!cle:-}" ] || erreur "$cle est vide dans avec-vm/.env"
    [[ "${!cle}" == change-me* ]] && erreur "remplace la valeur « change-me » de $cle dans avec-vm/.env"
    [[ "${!cle}" =~ ^[A-Za-z0-9_-]+$ ]] || erreur "$cle : lettres, chiffres, « - » et « _ » uniquement"
  done
  [ "${#ADMIN_PASSWORD}" -ge 8 ] || erreur "ADMIN_PASSWORD : 8 caractères minimum"
  [ "${#SEED_ARTIST_PASSWORD}" -ge 8 ] || erreur "SEED_ARTIST_PASSWORD : 8 caractères minimum"
  [[ "${MAIL_FROM:-}" != *\'* ]] || erreur "MAIL_FROM ne doit pas contenir d'apostrophe"
  API_INSTANCES="${API_INSTANCES:-3}"
  WEB_CONCURRENCY="${WEB_CONCURRENCY:-2}"
  COOKIE_SECURE="${COOKIE_SECURE:-true}"
  MAIL_FROM="${MAIL_FROM:-MusicApp <no-reply@musicapp.local>}"
  [[ "$API_INSTANCES" =~ ^[1-9]$ ]] || erreur "API_INSTANCES doit être un nombre entre 1 et 9"
  [[ "$WEB_CONCURRENCY" =~ ^[1-9]$ ]] || erreur "WEB_CONCURRENCY doit être un nombre entre 1 et 9"
  declare -gA RAM=([presentation]="${RAM_PRESENTATION:-512}" [metier]="${RAM_METIER:-1536}" [donnees]="${RAM_DONNEES:-2560}")
  declare -gA CPU=([presentation]="${CPU_PRESENTATION:-1}" [metier]="${CPU_METIER:-2}" [donnees]="${CPU_DONNEES:-2}")
}

# ---------- SSH vers les VM (utilisateur « ubuntu », clé dédiée, réseau privé) ----------
# Les VM sont recréables : leur clé d'hôte change, elle n'est donc pas mémorisée.
SSH_OPTS=(-i "$CLE_SSH" -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
          -o LogLevel=ERROR -o ConnectTimeout=5 -o ServerAliveInterval=15)
vm_ssh() { local role="$1"; shift; ssh "${SSH_OPTS[@]}" -o BatchMode=yes "ubuntu@${IP[$role]}" "$@"; }
vm_ssh_tty() { local role="$1"; shift; ssh "${SSH_OPTS[@]}" -t "ubuntu@${IP[$role]}" "$@"; }

attendre_ssh() {
  local role="$1" delai="$2" i
  for ((i = 0; i < delai; i += 5)); do
    vm_ssh "$role" true 2> /dev/null && return 0
    sleep 5
  done
  return 1
}

# Avant chaque démarrage (VM éteinte) : mémoire et processeurs lus dans .env
preparer_vm() {
  local role="$1" nom
  nom="$(nom_vm "$role")"
  vbox modifyvm "$nom" --memory "${RAM[$role]}" --cpus "${CPU[$role]}"
  # Le serveur web de cloud-init (sur 127.0.0.1 de WSL) ne sert qu'au premier démarrage :
  # ensuite, la VM n'a plus accès aux services de WSL.
  if [ -f "$LOCAL/$nom.initialisee" ]; then
    vbox modifyvm "$nom" --nat-localhostreachable1 off
  fi
}

# ---------- Installation d'une couche dans sa VM ----------
# Chaque VM ne reçoit que les réglages et les secrets dont elle a besoin.
reglages_role() {
  local role="$1" cle
  local cles=(IP_PRESENTATION IP_METIER IP_DONNEES IP_HOTE MAC_NAT API_INSTANCES API_FIRST_PORT)
  case "$role" in
    donnees) cles+=(MYSQL_DATABASE MYSQL_USER MYSQL_PASSWORD REDIS_PASSWORD ES_VERSION ES_ARCHIVE) ;;
    metier) cles+=(MYSQL_DATABASE MYSQL_USER MYSQL_PASSWORD REDIS_PASSWORD JWT_SECRET COOKIE_SECURE
                   WEB_CONCURRENCY MAIL_FROM PUBLIC_URL ADMIN_PASSWORD SEED_ARTIST_PASSWORD MAILPIT_ARCHIVE) ;;
  esac
  local IP_PRESENTATION="${IP[presentation]}" IP_METIER="${IP[metier]}" IP_DONNEES="${IP[donnees]}"
  local MAC_NAT PUBLIC_URL="http://localhost:$SITE_PORT"
  MAC_NAT="$(avec_deux_points "$(mac_nat "$role")")"
  echo "# Réglages de $(nom_vm "$role"), générés par avec-vm (supprimés après l'installation)"
  for cle in "${cles[@]}"; do printf "%s='%s'\n" "$cle" "${!cle}"; done
}

# Copie avec-vm/vm/ (+ réglages, code, archives) dans la VM, puis y lance <role>.sh en root
provisionner() {
  local role="$1" tmp
  etape "$(nom_vm "$role") (${IP[$role]}) : installation de la couche $role"
  tmp="$(mktemp -d)"
  cp -r "$AVEC_VM/vm/." "$tmp/"
  reglages_role "$role" > "$tmp/reglages.env"
  mkdir -p "$tmp/code" "$tmp/cache"
  case "$role" in
    donnees)
      cp "$PROJET/donnees/mysql/conf.d/musicapp.cnf" "$tmp/fichiers/"
      # Archive Elasticsearch (600 Mo) : envoyée seulement si elle n'est pas déjà installée
      if ! vm_ssh donnees test -x "/opt/elasticsearch-$ES_VERSION/bin/elasticsearch"; then
        ln -s "$CACHE/$ES_ARCHIVE" "$tmp/cache/$ES_ARCHIVE"
      fi
      ;;
    metier)
      tar -C "$PROJET" --exclude=__pycache__ --exclude='*.pyc' \
        -cf - metier/app metier/requirements.txt donnees/alembic.ini donnees/migrations | tar -C "$tmp/code" -xf -
      ln -s "$CACHE/$MAILPIT_ARCHIVE" "$tmp/cache/$MAILPIT_ARCHIVE"
      ;;
    presentation)
      tar -C "$PROJET" --exclude=client/Dockerfile --exclude=client/nginx -cf - client | tar -C "$tmp/code" -xf -
      ;;
  esac
  tar -C "$tmp" -chf - . | vm_ssh "$role" \
    'sudo rm -rf /tmp/musicapp-vm && sudo install -d -m 700 /tmp/musicapp-vm && sudo tar -xf - -C /tmp/musicapp-vm'
  rm -rf "$tmp"
  vm_ssh "$role" "sudo bash /tmp/musicapp-vm/$role.sh; code=\$?; sudo rm -rf /tmp/musicapp-vm; exit \$code" \
    || erreur "l'installation de $(nom_vm "$role") a échoué (voir les messages ci-dessus)"
}

# Mémoire libre dans WSL : les 3 VM doivent y tenir
verifier_memoire() {
  local besoin=0 dispo role
  for role in "${ROLES[@]}"; do
    vm_allumee "$role" || besoin=$((besoin + RAM[$role]))
  done
  dispo=$(awk '/MemAvailable/ {print int($2 / 1024)}' /proc/meminfo)
  if [ "$besoin" -gt 0 ] && [ "$dispo" -lt $((besoin + 300)) ]; then
    echo "ATTENTION : les VM à démarrer demandent ${besoin} Mo, il reste ${dispo} Mo dans WSL."
    echo "            Arrête l'autre version (sans Docker : bash sans-docker/arreter.sh ; Docker : docker compose stop)"
    echo "            ou baisse RAM_* dans avec-vm/.env."
  fi
}
