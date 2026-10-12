#!/usr/bin/env bash
# Crée les 3 VM VirtualBox (présentation, métier, données), installe chaque couche et démarre l'application.
# À lancer depuis Ubuntu (WSL), là où VirtualBox est installé. Aucun mot de passe sudo n'est demandé.
# Le relancer ne casse rien : ce qui existe déjà est conservé, la configuration est réappliquée.
#
#   bash avec-vm/installer.sh
#
# Téléchargements (une seule fois, gardés dans ~/.musicapp-vm/cache) : Ubuntu Server 24.04 (~600 Mo),
# Elasticsearch 8.15.3 (~600 Mo), Mailpit (~10 Mo). Dans les VM : paquets Ubuntu et dépendances Python.
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"

verifier_virtualbox
mkdir -p "$LOCAL" "$CACHE" "$SEMENCES" "$DOSSIER_VMS"
chmod 700 "$LOCAL"                 # contient la clé SSH et la configuration cloud-init (mot de passe des VM)
etape "Configuration (avec-vm/.env)"
charger_env
ok "réglages chargés"

etape "1/7 Clé SSH dédiée aux VM"
[ -f "$CLE_SSH" ] || ssh-keygen -q -t ed25519 -N "" -C "musicapp-vm" -f "$CLE_SSH"
ok "$CLE_SSH"

etape "2/7 Téléchargements (vérifiés par somme de contrôle)"
cd "$CACHE"
if [ ! -f "$UBUNTU_OVA.ok" ]; then
  curl -fL --progress-bar -o "$UBUNTU_OVA" "$UBUNTU_URL/$UBUNTU_OVA"
  curl -fsSL "$UBUNTU_URL/SHA256SUMS" | grep " \*$UBUNTU_OVA\$" | sed 's/ \*/  /' > "$UBUNTU_OVA.sha256"
  sha256sum -c "$UBUNTU_OVA.sha256" && touch "$UBUNTU_OVA.ok"
fi
ok "Ubuntu Server 24.04 (image cloud)"
if [ ! -f "$ES_ARCHIVE.ok" ]; then
  curl -fL --progress-bar -o "$ES_ARCHIVE" "https://artifacts.elastic.co/downloads/elasticsearch/$ES_ARCHIVE"
  curl -fsSL -o "$ES_ARCHIVE.sha512" "https://artifacts.elastic.co/downloads/elasticsearch/$ES_ARCHIVE.sha512"
  sha512sum -c "$ES_ARCHIVE.sha512" && touch "$ES_ARCHIVE.ok"
fi
ok "Elasticsearch $ES_VERSION"
if [ ! -f "$MAILPIT_ARCHIVE" ]; then
  curl -fL --progress-bar -o "$MAILPIT_ARCHIVE.part" \
    "https://github.com/axllent/mailpit/releases/latest/download/$MAILPIT_ARCHIVE"
  mv "$MAILPIT_ARCHIVE.part" "$MAILPIT_ARCHIVE"
fi
ok "Mailpit"
cd "$PROJET"

etape "3/7 Disque de base (le disque de l'image Ubuntu, converti au format VirtualBox)"
if [ ! -f "$DISQUE_BASE" ]; then
  tmp="$(mktemp -d)"
  tar -xf "$CACHE/$UBUNTU_OVA" -C "$tmp" --wildcards '*.vmdk'
  vmdk="$(ls "$tmp"/*.vmdk)"
  vbox clonemedium disk "$vmdk" "$DISQUE_BASE" --format VDI > /dev/null
  vbox closemedium disk "$vmdk" > /dev/null
  vbox closemedium disk "$DISQUE_BASE" > /dev/null
  rm -rf "$tmp"
fi
ok "$DISQUE_BASE"

etape "4/7 Réseau privé hôte $RESEAU_HOTE ($IP_HOTE/24)"
if ! vbox list hostonlyifs | grep -q "^Name: *$RESEAU_HOTE\$"; then
  vbox hostonlyif create > /dev/null
fi
vbox hostonlyif ipconfig "$RESEAU_HOTE" --ip "$IP_HOTE" --netmask 255.255.255.0
ok "WSL = $IP_HOTE ; vm-presentation = ${IP[presentation]} ; vm-metier = ${IP[metier]} ; vm-donnees = ${IP[donnees]}"

# Configuration du premier démarrage, lue par cloud-init dans la VM (utilisateur, clé SSH, adresses IP)
ecrire_semences() {
  local role="$1" nom dossier
  nom="$(nom_vm "$role")"
  dossier="$SEMENCES/$nom"
  mkdir -p "$dossier"
  printf 'instance-id: %s-1\nlocal-hostname: %s\n' "$nom" "$nom" > "$dossier/meta-data"
  : > "$dossier/vendor-data"                   # facultatif, mais demandé par cloud-init
  cat > "$dossier/user-data" <<EOF
#cloud-config
hostname: $nom
ssh_pwauth: false
users:
  - name: ubuntu
    groups: [adm, sudo]
    shell: /bin/bash
    sudo: "ALL=(ALL) NOPASSWD:ALL"
    lock_passwd: false
    ssh_authorized_keys:
      - $(cat "$CLE_SSH.pub")
chpasswd:
  expire: false
  users:
    - {name: ubuntu, password: $VM_PASSWORD, type: text}
write_files:
  # Carte 1 (NAT) : Internet par DHCP ; carte 2 (réseau privé hôte) : adresse fixe
  - path: /etc/netplan/50-cloud-init.yaml
    permissions: "0600"
    content: |
      network:
        version: 2
        ethernets:
          nat:
            match: {macaddress: "$(avec_deux_points "$(mac_nat "$role")")"}
            dhcp4: true
          prive:
            match: {macaddress: "$(avec_deux_points "$(mac_prive "$role")")"}
            dhcp4: false
            addresses: [${IP[$role]}/24]
  - path: /etc/cloud/cloud.cfg.d/99-musicapp.cfg
    content: |
      network: {config: disabled}
runcmd:
  - [netplan, apply]
  # Configuration faite une fois pour toutes : cloud-init ne s'exécute plus aux démarrages suivants
  - [touch, /etc/cloud/cloud-init.disabled]
EOF
}

creer_vm() {
  local role="$1" nom dossier disque
  nom="$(nom_vm "$role")"
  dossier="$DOSSIER_VMS/$nom"
  disque="$dossier/$nom.vdi"
  vbox createvm --name "$nom" --platform-architecture=x86 --ostype Ubuntu_64 --groups /MusicApp \
    --basefolder "$DOSSIER_VMS" --register > /dev/null
  vbox modifyvm "$nom" --memory "${RAM[$role]}" --cpus "${CPU[$role]}" --ioapic on --rtc-use-utc on \
    --graphicscontroller vmsvga --vram 16 --audio-enabled off --usb-ohci off \
    --boot1 disk --boot2 none --boot3 none --boot4 none \
    --nic1 nat --nic-type1 virtio --mac-address1 "$(mac_nat "$role")" --nat-localhostreachable1 on \
    --nic2 hostonly --nic-type2 virtio --host-only-adapter2 "$RESEAU_HOTE" --mac-address2 "$(mac_prive "$role")" \
    --uart1 0x3F8 4 --uart-mode1 file "$dossier/console.log"
  # cloud-init trouve sa configuration grâce au numéro de série (DMI) de la VM : ds=nocloud;s=<url>
  vbox setextradata "$nom" "VBoxInternal/Devices/pcbios/0/Config/DmiSystemSerial" \
    "ds=nocloud;s=http://10.0.2.2:$SEMENCES_PORT/$nom/"
  vbox clonemedium disk "$DISQUE_BASE" "$disque" --format VDI > /dev/null
  vbox modifymedium disk "$disque" --resize "${DISQUE_MO[$role]}"
  vbox storagectl "$nom" --name SATA --add sata --controller IntelAhci --portcount 1
  vbox storageattach "$nom" --storagectl SATA --port 0 --device 0 --type hdd --medium "$disque"
  case "$role" in
    presentation)
      vbox modifyvm "$nom" --nat-pf1 "site,tcp,127.0.0.1,$SITE_PORT,,80" ;;
    metier)
      vbox modifyvm "$nom" --nat-pf1 "mailpit,tcp,127.0.0.1,$MAILPIT_PORT,,8025"
      # Jeu de données FMA : dossier partagé en lecture seule, comme le montage /fma de la version Docker
      if [ -d "$PROJET/donnees/fma" ]; then
        vbox sharedfolder add "$nom" --name fma --hostpath "$PROJET/donnees/fma" --readonly
      fi ;;
  esac
}

etape "5/7 Création des VM"
for role in "${ROLES[@]}"; do
  if vm_existe "$role"; then
    ok "$(nom_vm "$role") existe déjà"
  else
    creer_vm "$role"
    ok "$(nom_vm "$role") créée (${RAM[$role]} Mo, ${CPU[$role]} CPU, disque ${DISQUE_MO[$role]} Mo)"
  fi
done

etape "6/7 Démarrage des VM"
verifier_memoire
serveur=""
for role in "${ROLES[@]}"; do
  [ -f "$LOCAL/$(nom_vm "$role").initialisee" ] && continue
  ecrire_semences "$role"
  if [ -z "$serveur" ]; then
    python3 -m http.server "$SEMENCES_PORT" --bind 127.0.0.1 --directory "$SEMENCES" > "$LOCAL/semences.log" 2>&1 &
    serveur=$!
    trap 'kill "$serveur" 2> /dev/null || true' EXIT
  fi
done
for role in "${ROLES[@]}"; do
  if vm_allumee "$role"; then
    ok "$(nom_vm "$role") déjà démarrée"
  else
    preparer_vm "$role"
    vbox startvm "$(nom_vm "$role")" --type headless > /dev/null
    ok "$(nom_vm "$role") démarrée"
  fi
done
for role in "${ROLES[@]}"; do
  nom="$(nom_vm "$role")"
  info "attente de $nom (premier démarrage : 1 à 3 minutes)…"
  attendre_ssh "$role" 600 || erreur "$nom ne répond pas en SSH. Journal de démarrage : $DOSSIER_VMS/$nom/console.log"
  if [ ! -f "$LOCAL/$nom.initialisee" ]; then
    vm_ssh "$role" "cloud-init status --wait > /dev/null; test -f /etc/cloud/cloud-init.disabled" \
      || erreur "cloud-init a échoué sur $nom (voir : bash avec-vm/ssh.sh $role sudo cat /var/log/cloud-init-output.log)"
    touch "$LOCAL/$nom.initialisee"
  fi
  ok "$nom prête (ssh ubuntu@${IP[$role]})"
done
[ -n "$serveur" ] && kill "$serveur" 2> /dev/null || true
trap - EXIT

etape "7/7 Installation des couches, de bas en haut"
for role in "${ROLES[@]}"; do provisionner "$role"; done

etape "Compte admin et playlist à la une"
vm_ssh metier "sudo musicapp-python -m app.scripts.create_admin --username admin --email admin@example.com"

etape "MusicApp (VM) est installée et démarrée"
echo "    Application  : http://localhost:$SITE_PORT   (depuis Windows ou Ubuntu)"
echo "    API (docs)   : http://localhost:$SITE_PORT/api/docs"
echo "    Emails       : http://localhost:$MAILPIT_PORT"
echo "    Admin        : admin / mot de passe ADMIN_PASSWORD de avec-vm/.env"
echo "    État         : bash avec-vm/etat.sh"
echo "    Import FMA   : voir avec-vm/LISEZMOI.md"
echo "    Arrêt        : bash avec-vm/arreter.sh"
