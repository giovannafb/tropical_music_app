#!/usr/bin/env bash
# Réglages et fonctions communs aux scripts du test de charge (partie 4), lancés depuis Ubuntu (WSL),
# sur l'hôte : hors des VM et hors des conteneurs mesurés.
# Ce fichier est chargé par les autres scripts (ne pas l'exécuter directement).

# Fonctions de la version VM (vm_ssh, vbox, adresses des VM, etape/ok/erreur…), sans rien y modifier
. "$(dirname "${BASH_SOURCE[0]}")/../avec-vm/commun.sh"

CHARGE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTATS="$CHARGE/resultats"
PLAN="$CHARGE/plan/musicapp.jmx"
PLAN_STATIQUE="$CHARGE/plan/etalonnage.jmx"
PROPRIETES="$CHARGE/plan/resultats.properties"
COMPTES="$CHARGE/comptes/comptes.csv"
COMPTES_INVALIDES="$CHARGE/comptes/comptes-invalides.csv"
COMPTES_SANS_LIKE="$CHARGE/comptes/comptes-sans-like.csv"

# Outils de l'injecteur, installés hors du projet par charge/installer.sh (sans sudo)
OUTILS="$HOME/.musicapp-charge"
JMETER_VERSION="5.6.3"
JAVA_VERSION="21"
JMETER_HOME="$OUTILS/apache-jmeter-$JMETER_VERSION"
JAVA_DIR="$OUTILS/java-$JAVA_VERSION"

# ---------- Protocole de mesure (étape 16) : figé, identique pour toutes les campagnes ----------
# Seuls les paliers peuvent être prolongés (PALIERS="… 300" bash charge/campagne.sh …), et alors pour les deux déploiements.
PALIERS="${PALIERS:-1 10 25 50 100 150}"   # utilisateurs simultanés ; on monte tant que le débit croît
MONTEE=10                 # s : montée en charge de chaque palier, exclue des mesures
PLATEAU=60                # s : fenêtre de mesure, une fois la montée terminée (60 s minimum imposées)
MARGE=5                   # s : JMeter tourne un peu après la fenêtre, pour qu'elle soit pleine jusqu'au bout
REPOS=10                  # s : pause entre deux paliers, le temps que le système revienne au repos
INTERVALLE=5              # s : période des relevés côté serveur
REFLEXION_MIN=500         # ms : temps de réflexion avant chaque requête, tiré entre 500 et 1500 ms
REFLEXION_ALEA=1000

# Étalonnage de l'injecteur : ressource statique servie par le proxy, sans temps de réflexion
ETALONNAGE_PALIERS="10 50 100 200"
ETALONNAGE_MONTEE=10
ETALONNAGE_PLATEAU=60
RESSOURCE_STATIQUE="/assets/placeholder-cover.svg"

# ---------- Comptes de test (comptes/*.csv, créés dans la base par comptes/creer_comptes.py) ----------
NB_COMPTES=100                     # charge001 … charge100, chacun avec ses titres likés
PREFIXE_COMPTES="charge"           # + charge000 : compte témoin sans aucun like (test du test)
DOMAINE_COMPTES="charge.invalid"   # charge001@charge.invalid : domaine réservé, jamais un vrai email
MDP_COMPTES="charge-musicapp-2026"
LIKES_PAR_COMPTE=20

# ---------- Les deux déploiements mesurés ----------
# docker : port publié par le conteneur Nginx.
# vm : vm-presentation par le réseau privé hôte (autorisé par son pare-feu depuis WSL), et non par la
#      redirection de port 8081 de la carte NAT, dont le relais logiciel de VirtualBox serait mesuré en plus.
CIBLE_DOCKER="${CIBLE_DOCKER:-localhost:80}"
CIBLE_VM="${CIBLE_VM:-${IP[presentation]}:80}"

verifier_deploiement() {
  case "${1:-}" in
    docker | vm) ;;
    *) erreur "indique le déploiement mesuré : docker ou vm" ;;
  esac
}

cible() { if [ "$1" = docker ]; then echo "$CIBLE_DOCKER"; else echo "$CIBLE_VM"; fi; }
cible_hote() { local c; c="$(cible "$1")"; echo "${c%:*}"; }
cible_port() { local c; c="$(cible "$1")"; echo "${c##*:}"; }

# ---------- Docker ----------
# CLI de Docker Desktop : « docker » si l'intégration WSL est activée, sinon « docker.exe » (Windows)
docker_cli() {
  if command -v docker > /dev/null 2>&1; then echo docker
  elif command -v docker.exe > /dev/null 2>&1; then echo docker.exe
  else return 1
  fi
}

# docker compose, dans avec-docker/ (projet « musicapp »)
dc() {
  local cli
  cli="$(docker_cli)" || erreur "Docker introuvable dans Ubuntu (ni docker, ni docker.exe)"
  (cd "$PROJET/avec-docker" && "$cli" compose "$@")
}

docker_en_marche() {
  local cli
  cli="$(docker_cli)" || return 1
  [ -n "$(cd "$PROJET/avec-docker" && "$cli" compose ps -q --status running 2> /dev/null)" ]
}

vms_en_marche() {
  command -v VBoxManage > /dev/null 2>&1 || return 1
  vbox list runningvms 2> /dev/null | grep -Eq '"vm-(presentation|metier|donnees)"'
}

# Règle d'or : un seul déploiement en marche pendant une mesure
verifier_seul() {
  case "$1" in
    docker) if vms_en_marche; then erreur "des VM MusicApp sont démarrées : bash avec-vm/arreter.sh (un seul déploiement à la fois)"; fi ;;
    vm) if docker_en_marche; then erreur "la stack Docker tourne : docker compose stop, dans avec-docker/ (un seul déploiement à la fois)"; fi ;;
  esac
  if curl -fs -o /dev/null --max-time 2 "http://127.0.0.1:8080/api/health"; then
    erreur "la version sans Docker tourne : bash sans-docker/arreter.sh (un seul déploiement à la fois)"
  fi
}

# Après une surcharge, l'API continue de traiter les requêtes abandonnées par JMeter (argon2) : on attend
# qu'elle soit revenue au repos (trois réponses de /api/health en moins de 0,5 s d'affilée) avant de mesurer.
# Affiche la durée d'attente en secondes ; échoue au-delà de 15 minutes.
attendre_repos() {
  local debut=$SECONDS bons=0 duree
  while ((bons < 3)); do
    duree="$(curl -s -o /dev/null -w '%{http_code} %{time_total}' --max-time 5 "http://$(cible "$1")/api/health" || true)"
    if [[ "$duree" == 200\ * ]] && awk -v t="${duree#* }" 'BEGIN {exit !(t < 0.5)}'; then
      bons=$((bons + 1))
    else
      bons=0
      ((SECONDS - debut < 900)) || return 1
      sleep 5
    fi
  done
  echo $((SECONDS - debut))
}

verifier_cible() {
  curl -fs -o /dev/null --max-time 5 "http://$(cible "$1")/api/health" \
    || erreur "le déploiement $1 ne répond pas sur http://$(cible "$1")/api/health"
}

# ---------- JMeter ----------
verifier_jmeter() {
  [ -x "$JMETER_HOME/bin/jmeter" ] && [ -x "$JAVA_DIR/bin/java" ] \
    || erreur "JMeter n'est pas installé : bash charge/installer.sh"
}

jmeter_cli() {
  verifier_jmeter
  JAVA_HOME="$JAVA_DIR" PATH="$JAVA_DIR/bin:$PATH" "$JMETER_HOME/bin/jmeter" "$@"
}

# Une exécution en ligne de commande (jamais l'interface graphique) : jmeter_executer <déploiement> <plan> <résultats sans .csv> -Jcle=valeur…
jmeter_executer() {
  local dep="$1" plan="$2" sortie="$3"
  shift 3
  jmeter_cli -n -t "$plan" -q "$PROPRIETES" -l "$sortie.csv" -j "$sortie.log" \
    -Jhote="$(cible_hote "$dep")" -Jport="$(cible_port "$dep")" "$@"
}

# ---------- Comptes de test ----------
generer_comptes() {
  local i
  {
    echo "login,mot_de_passe"
    for ((i = 1; i <= NB_COMPTES; i++)); do printf '%s%03d,%s\n' "$PREFIXE_COMPTES" "$i" "$MDP_COMPTES"; done
  } > "$COMPTES"
  {
    echo "login,mot_de_passe"
    for ((i = 1; i <= NB_COMPTES; i++)); do printf '%s%03d,%s\n' "$PREFIXE_COMPTES" "$i" "mauvais-mot-de-passe"; done
  } > "$COMPTES_INVALIDES"
  printf 'login,mot_de_passe\n%s000,%s\n' "$PREFIXE_COMPTES" "$MDP_COMPTES" > "$COMPTES_SANS_LIKE"
}

# Lance un script Python DANS la couche métier du déploiement (lu sur l'entrée standard) :
# executer_metier <déploiement> <script local> <arguments…>
executer_metier() {
  local dep="$1" script="$2"
  shift 2
  case "$dep" in
    docker) dc exec -T api python - "$@" < "$script" ;;
    vm) vm_ssh metier "sudo musicapp-python - $(printf '%q ' "$@")" < "$script" ;;
  esac
}

# Crée ou réinitialise les comptes de test dans la base du déploiement (même état à chaque campagne)
reinitialiser_comptes() {
  generer_comptes
  executer_metier "$1" "$CHARGE/comptes/creer_comptes.py" \
    --nombre "$NB_COMPTES" --prefixe "$PREFIXE_COMPTES" --domaine "$DOMAINE_COMPTES" \
    --mot-de-passe "$MDP_COMPTES" --likes "$LIKES_PAR_COMPTE"
}

# ---------- Proxy : « mode charge » ----------
# Nginx limite la connexion à 10 requêtes par minute et par adresse IP (protection contre la force brute).
# Toutes les requêtes de JMeter viennent de la même adresse : sans lever cette limite, la campagne
# mesurerait le limiteur (le même plafond des deux côtés), et non le déploiement.
# Le mode charge retire cette seule ligne (limit_req … login) de la configuration installée, à
# l'identique sur les deux déploiements ; le mode normal remet la configuration d'origine.
mode_proxy() {
  local dep="$1" mode="$2"
  local script='
    f="$1"; s="$2"; mode="$3"
    if [ "$mode" = charge ]; then
      [ -f "$s" ] || cp "$f" "$s"
      sed "/limit_req zone=[a-z_]*login/d" "$s" > "$f"
    elif [ -f "$s" ]; then
      cp "$s" "$f" && rm -f "$s"
    fi
    nginx -t -q'
  case "$dep" in
    docker)
      dc exec -T nginx sh -c "$script && nginx -s reload" sh \
        /etc/nginx/conf.d/default.conf /etc/nginx/default.conf.normal "$mode" ;;
    vm)
      vm_ssh presentation "sudo sh -c '$script && systemctl reload nginx' sh \
        /etc/nginx/sites-available/musicapp /etc/nginx/musicapp.conf.normal $mode" ;;
  esac
  sleep 2   # rechargement progressif des processus Nginx
}

# Vérifie le mode charge : 12 connexions immédiates (compte inexistant, donc rapides) ne doivent pas recevoir de 429
verifier_mode_charge() {
  local i code refus=0
  for ((i = 0; i < 12; i++)); do
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 -H 'Content-Type: application/json' \
      -d '{"login":"verification-mode-charge","password":"xxxxxxxx"}' "http://$(cible "$1")/api/auth/login")"
    [ "$code" = 429 ] && refus=$((refus + 1))
  done
  [ "$refus" -eq 0 ] || erreur "la limite de connexion de Nginx est toujours active ($refus refus 429 sur 12)"
}

# ---------- Relevés côté serveur et côté hôte (metriques/releve.py) ----------
# Chaque ligne reçoit l'heure de l'hôte (microsecondes) : une seule horloge pour l'injecteur, les VM et les conteneurs.
horodater() {
  local ligne
  while IFS= read -r ligne; do printf '%s,%s\n' "${EPOCHREALTIME/[.,]/}" "$ligne"; done
}

RELEVES=()
# demarrer_releves <déploiement> <préfixe des fichiers> <durée en s> : en arrière-plan
demarrer_releves() {
  local dep="$1" prefixe="$2" duree="$3" role releve="$CHARGE/metriques/releve.py"
  local options=(--duree "$duree" --intervalle "$INTERVALLE")
  RELEVES=()
  echo "horodatage_us,source,service,mesure,valeur" > "$prefixe-hote.csv"
  echo "horodatage_us,source,service,mesure,valeur" > "$prefixe-serveur.csv"
  python3 "$releve" hote "${options[@]}" | horodater >> "$prefixe-hote.csv" &
  RELEVES+=($!)
  case "$dep" in
    docker)
      python3 "$releve" docker "${options[@]}" --docker "$(docker_cli)" --compose "$PROJET/avec-docker" \
        | horodater >> "$prefixe-serveur.csv" &
      RELEVES+=($!)
      ;;
    vm)
      for role in "${ROLES[@]}"; do
        vm_ssh "$role" "sudo python3 - systemd --machine $(nom_vm "$role") ${options[*]}" < "$releve" \
          | horodater >> "$prefixe-serveur.csv" &
        RELEVES+=($!)
      done
      ;;
  esac
}

attendre_releves() {
  local pid
  for pid in "${RELEVES[@]}"; do wait "$pid" || true; done
  RELEVES=()
}

arreter_releves() {
  local pid
  for pid in "${RELEVES[@]}"; do kill "$pid" 2> /dev/null || true; done
  RELEVES=()
}

# Événements pendant un palier, depuis <début> (secondes epoch) : processus tués faute de mémoire,
# workers gunicorn relancés ou arrêtés pour dépassement de délai, erreurs de Nginx
evenements() {
  local dep="$1" debut="$2" depuis role
  depuis="$(date -u -d "@$debut" +%Y-%m-%dT%H:%M:%SZ)"
  case "$dep" in
    docker)
      echo "workers_relances=$(dc logs --no-log-prefix --since "$depuis" api 2>&1 | grep -c 'Booting worker' || true)"
      echo "workers_hors_delai=$(dc logs --no-log-prefix --since "$depuis" api 2>&1 | grep -c 'WORKER TIMEOUT' || true)"
      echo "erreurs_nginx=$(dc logs --no-log-prefix --since "$depuis" nginx 2>&1 | grep -c '\[error\]' || true)"
      echo "conteneurs_tues_memoire=$(dc ps -aq | xargs -r "$(docker_cli)" inspect --format '{{.State.OOMKilled}}' | grep -c true || true)"
      ;;
    vm)
      echo "workers_relances=$(vm_ssh metier "sudo journalctl -q -o cat --since=@$debut -u 'musicapp-api@*'" | grep -c 'Booting worker' || true)"
      echo "workers_hors_delai=$(vm_ssh metier "sudo journalctl -q -o cat --since=@$debut -u 'musicapp-api@*'" | grep -c 'WORKER TIMEOUT' || true)"
      echo "erreurs_nginx=$(vm_ssh presentation "sudo awk -v d=\"\$(date -d @$debut '+%Y/%m/%d %H:%M:%S')\" 'substr(\$0, 1, 19) >= d' /var/log/nginx/error.log" | grep -c '\[error\]' || true)"
      for role in "${ROLES[@]}"; do
        echo "$(nom_vm "$role")_tues_memoire=$(vm_ssh "$role" "sudo journalctl -q -k -o cat --since=@$debut" | grep -ci 'out of memory' || true)"
      done
      ;;
  esac
}

# ---------- Configuration consignée avec chaque série de chiffres ----------
consigner_configuration() {
  local dep="$1" cle
  echo "# Configuration qui a produit les mesures de ce dossier (format clé=valeur)"
  echo "date=$(date -Iseconds)"
  echo "deploiement=$dep"
  echo "cible=http://$(cible "$dep")"
  echo "commit=$(git -C "$PROJET" rev-parse --short HEAD 2> /dev/null || echo inconnu)$(git -C "$PROJET" diff --quiet HEAD -- client metier donnees avec-docker avec-vm 2> /dev/null || echo '-modifie')"
  echo "paliers=$PALIERS"
  echo "montee=$MONTEE"
  echo "plateau=$PLATEAU"
  echo "marge=$MARGE"
  echo "repos=$REPOS"
  echo "intervalle_releves=$INTERVALLE"
  echo "reflexion_ms=$REFLEXION_MIN+[0..$REFLEXION_ALEA]"
  echo "comptes=$NB_COMPTES"
  echo "likes_par_compte=$LIKES_PAR_COMPTE"
  echo "jmeter=$JMETER_VERSION"
  echo "java=$("$JAVA_DIR/bin/java" -version 2>&1 | head -1 | tr -d '"')"
  echo "hote_cpu=$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2- | sed 's/^ *//')"
  echo "hote_coeurs=$(nproc)"
  echo "hote_memoire_mo=$(awk '/MemTotal/ {print int($2 / 1024)}' /proc/meminfo)"
  echo "hote_noyau=$(uname -r)"
  case "$dep" in
    docker)
      echo "docker=$("$(docker_cli)" version --format '{{.Server.Version}}' 2> /dev/null || echo inconnu)"
      echo "docker_coeurs=$("$(docker_cli)" info --format '{{.NCPU}}' 2> /dev/null || echo inconnu)"
      echo "docker_memoire_mo=$(( $("$(docker_cli)" info --format '{{.MemTotal}}' 2> /dev/null || echo 0) / 1048576 ))"
      echo "conteneurs=$(dc ps --format '{{.Service}}' 2> /dev/null | sort | uniq -c | awk '{printf "%s%s×%s", sep, $2, $1; sep=" "}')"
      for cle in WEB_CONCURRENCY ES_REPLICAS COOKIE_SECURE; do
        echo "$cle=$(sed -n "s/^$cle=//p" "$PROJET/avec-docker/.env" 2> /dev/null | tr -d '\r')"
      done
      ;;
    vm)
      echo "virtualbox=$(vbox --version 2> /dev/null || echo inconnu)"
      for role in "${ROLES[@]}"; do
        echo "$(nom_vm "$role")=$(vbox showvminfo "$(nom_vm "$role")" --machinereadable 2> /dev/null \
          | awk -F= '/^memory=/ {m=$2} /^cpus=/ {c=$2} END {printf "%s Mo, %s CPU", m, c}')"
      done
      for cle in API_INSTANCES WEB_CONCURRENCY COOKIE_SECURE; do
        echo "$cle=$(sed -n "s/^$cle=//p" "$AVEC_VM/.env" 2> /dev/null | tr -d '\r')"
      done
      ;;
  esac
}
