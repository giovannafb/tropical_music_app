#!/usr/bin/env bash
# Les mesures de référence des étapes 10 (VM) et 14 (conteneurs), avec le même protocole pour les deux
# déploiements : trois exécutions, médiane retenue, configuration consignée.
#   - Temps de démarrage complet : du déploiement arrêté (VM éteintes, conteneurs arrêtés) jusqu'au
#     parcours connexion + likes qui réussit à travers le proxy.
#   - Mémoire consommée au repos : mémoire utilisée de la VM de WSL 2, qui héberge à la fois VirtualBox et
#     Docker, déploiement démarré et au repos depuis 60 s, moins la même mesure à vide (VM éteintes ; conteneurs
#     arrêtés et mémoire du moteur retirée s'il tourne dans Ubuntu, ou Docker Desktop quitté) : le moteur est compté.
#   - Latence applicative : dix appels à une route de consultation (GET /api/me/likes/tracks, session ouverte),
#     au repos, à travers le proxy ; médiane des dix.
#   - Empreinte disque (une fois) : fichiers de disque des 3 VM, ou images et volumes du projet Docker.
# Les comptes de test doivent exister (bash charge/preparer.sh <déploiement>).
#
#   bash charge/repos.sh vm
#   bash charge/repos.sh docker
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"
dep="${1:-}"
verifier_deploiement "$dep"
REPETITIONS="${REPETITIONS:-3}"
REPOS_APRES_DEMARRAGE=60
[ "$dep" = vm ] && verifier_virtualbox
dossier="$RESULTATS/repos"
mkdir -p "$dossier"
sortie="$dossier/$dep.txt"

# Mémoire utilisée hors cache (Mo) : moyenne de 3 lectures sur 6 s
memoire() {
  local total=0 i
  for i in 1 2 3; do
    total=$((total + $(awk '/MemTotal/ {t=$2} /MemAvailable/ {a=$2} END {print int((t - a) / 1024)}' /proc/meminfo)))
    sleep 2
  done
  echo $((total / 3))
}

# Le parcours mesuré par JMeter, une fois, avec curl (cookie Secure renvoyé à la main, comme dans le plan)
parcours_ok() {
  local jeton
  jeton="$(curl -s -D - -o /dev/null --max-time 10 -H 'Content-Type: application/json' \
    -d "{\"login\":\"${PREFIXE_COMPTES}001\",\"password\":\"$MDP_COMPTES\"}" "http://$(cible "$dep")/api/auth/login" \
    | sed -n 's/^[Ss]et-[Cc]ookie: access_token=\([^;]*\).*/\1/p')"
  [ -n "$jeton" ] && curl -fs --max-time 10 -H "Cookie: access_token=$jeton" \
    "http://$(cible "$dep")/api/me/likes/tracks" | grep -q '"id"'
}

# Latence applicative (ms) : médiane de dix appels à la consultation des likes, avec une session ouverte
latence() {
  local jeton i
  jeton="$(curl -s -D - -o /dev/null --max-time 10 -H 'Content-Type: application/json' \
    -d "{\"login\":\"${PREFIXE_COMPTES}001\",\"password\":\"$MDP_COMPTES\"}" "http://$(cible "$dep")/api/auth/login" \
    | sed -n 's/^[Ss]et-[Cc]ookie: access_token=\([^;]*\).*/\1/p')"
  for ((i = 0; i < 10; i++)); do
    curl -s -o /dev/null -w '%{time_total}\n' --max-time 10 -H "Cookie: access_token=$jeton" \
      "http://$(cible "$dep")/api/me/likes/tracks"
    sleep 0.5
  done | LC_ALL=C sort -g | awk '{v[NR] = $1 * 1000} END {printf "%.1f", (v[5] + v[6]) / 2}'
}

# Empreinte disque (Mo) : ce qu'il faut stocker pour faire tourner le déploiement
empreinte_disque() {
  case "$dep" in
    vm) du -sb "$DOSSIER_VMS" | awk '{printf "%d Mo de disques de VM (%s)", $1 / 1048576, "~/VirtualBox VMs/MusicApp"}' ;;
    docker)
      local images volumes
      images=$(dc images --format json | python3 -c 'import json, sys; print(sum({i["ID"]: i["Size"] for i in json.load(sys.stdin)}.values()) // 1048576)')
      volumes=$("$(docker_cli)" system df -v 2> /dev/null | awk '/^musicapp_/ {s = $3; u = s; gsub(/[0-9.]/, "", u); n = s + 0;
        f = (u == "GB") ? 1000 : (u == "MB") ? 1 : (u == "kB") ? 0.001 : (u == "B") ? 0.000001 : 0; t += n * f} END {printf "%d", t}')
      echo "$((images + volumes)) Mo ($images Mo d'images, $volumes Mo de volumes)"
      ;;
  esac
}

arreter() {
  case "$dep" in
    docker) dc stop > /dev/null 2>&1 ;;
    vm) bash "$AVEC_VM/arreter.sh" > /dev/null ;;
  esac
}

demarrer() {
  case "$dep" in
    docker) dc up -d --scale api=3 > /dev/null 2>&1 ;;
    # Juste après l'arrêt des VM, le service VBoxSVC se relance et le premier appel peut échouer : une seconde tentative
    vm) bash "$AVEC_VM/demarrer.sh" > /dev/null 2>&1 || { sleep 10; bash "$AVEC_VM/demarrer.sh" > /dev/null; } ;;
  esac
}

verifier_seul "$dep"
verifier_cible "$dep"
parcours_ok || erreur "le parcours échoue : créer d'abord les comptes de test (bash charge/preparer.sh $dep)"

# Moteur Docker installé dans Ubuntu (dockerd, containerd visibles ici) ou Docker Desktop (sa propre distribution WSL)
moteur_natif() { pgrep -x dockerd > /dev/null; }
memoire_moteur() { ps -C dockerd,containerd -o rss= | awk '{s += $1} END {print int(s / 1024)}'; }

etape "Mémoire à vide"
arreter
if [ "$dep" = docker ] && ! moteur_natif; then
  read -r -p "    Quitte Docker Desktop (icône > Quit Docker Desktop), puis appuie sur Entrée " _
  while docker_cli > /dev/null && "$(docker_cli)" info > /dev/null 2>&1; do sleep 2; done
fi
sleep 10
base=$(memoire)
if [ "$dep" = docker ] && moteur_natif; then
  # Le moteur reste en marche, conteneurs arrêtés : sa mémoire est retirée de la mesure à vide, donc comptée
  moteur=$(memoire_moteur)
  base=$((base - moteur))
  ok "$base Mo utilisés dans WSL, conteneurs arrêtés, hors moteur Docker ($moteur Mo pour dockerd et containerd)"
else
  ok "$base Mo utilisés dans WSL, déploiement $dep arrêté"
fi
if [ "$dep" = docker ] && ! moteur_natif; then
  read -r -p "    Relance Docker Desktop, puis appuie sur Entrée " _
  until docker_cli > /dev/null && "$(docker_cli)" info > /dev/null 2>&1; do sleep 2; done
  ok "moteur Docker prêt"
fi

{
  echo "# Mesures de référence (étapes 10 et 14) — déploiement $dep — $(date -Iseconds)"
  echo "# démarrage : de l'arrêt complet au parcours connexion + likes réussi ; mémoire : WSL au repos ($REPOS_APRES_DEMARRAGE s) moins WSL à vide ;"
  echo "# latence : médiane de 10 GET /api/me/likes/tracks au repos ; charge : charge moyenne de l'hôte sur 1 min au moment de la mesure"
  echo "cible=http://$(cible "$dep")"
  echo "memoire_a_vide_mo=$base"
} > "$sortie"
durees=()
memoires=()
latences=()
for ((n = 1; n <= REPETITIONS; n++)); do
  etape "Exécution $n / $REPETITIONS"
  arreter
  sleep 5
  debut=$(date +%s.%N)
  demarrer
  until curl -fs -o /dev/null --max-time 2 "http://$(cible "$dep")/api/health"; do sleep 1; done
  until parcours_ok; do sleep 6; done   # 6 s : sous la limite de 10 connexions par minute de Nginx
  duree=$(awk -v fin="$(date +%s.%N)" -v debut="$debut" 'BEGIN {printf "%.1f", fin - debut}')
  ok "démarrage complet en $duree s"
  sleep "$REPOS_APRES_DEMARRAGE"
  utilisee=$(( $(memoire) - base ))
  ok "mémoire consommée au repos : $utilisee Mo"
  lat=$(latence)
  ok "latence applicative : $lat ms (médiane de 10 appels)"
  durees+=("$duree")
  memoires+=("$utilisee")
  latences+=("$lat")
  echo "execution_$n=demarrage $duree s, memoire $utilisee Mo, latence $lat ms, charge $(cut -d' ' -f1 /proc/loadavg)" >> "$sortie"
done

mediane() { printf '%s\n' "$@" | LC_ALL=C sort -g | awk '{v[NR] = $1} END {print (NR % 2) ? v[(NR + 1) / 2] : (v[NR / 2] + v[NR / 2 + 1]) / 2}'; }
{
  echo "demarrage_median_s=$(mediane "${durees[@]}")"
  echo "memoire_repos_mediane_mo=$(mediane "${memoires[@]}")"
  echo "latence_mediane_ms=$(mediane "${latences[@]}")"
  echo "empreinte_disque=$(empreinte_disque)"
} >> "$sortie"
etape "Résultat (médianes)"
tail -4 "$sortie" | sed 's/^/    /'
ok "écrit dans $sortie"
