#!/usr/bin/env bash
# Étape 17 : une campagne de mesure sur UN déploiement, palier par palier, en ligne de commande.
#   1. vérifie qu'il est seul en marche et qu'il répond ;
#   2. réinitialise les comptes de test (même état de départ à chaque campagne) ;
#   3. consigne la configuration, puis met le proxy en mode charge (voir commun.sh, mode_proxy) ;
#   4. pour chaque palier : JMeter + relevés côté serveur et côté hôte, puis un résumé ;
#   5. remet le proxy en mode normal et produit la synthèse de la série.
# Fichiers bruts (jamais écrasés) : charge/resultats/<série>/<déploiement>-<utilisateurs>.csv, -serveur.csv, -hote.csv…
#
#   bash charge/campagne.sh vm serie-1
#   bash charge/campagne.sh docker serie-1
#   PALIERS="1 5 10 25 50 100 150 200 300" bash charge/campagne.sh docker serie-1   (paliers prolongés)
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"
dep="${1:-}"
serie="${2:-}"
verifier_deploiement "$dep"
[[ "$serie" =~ ^[A-Za-z0-9_-]+$ ]] || erreur "indique le nom de la série (lettres, chiffres, - et _), par exemple : serie-1"
dossier="$RESULTATS/$serie"
if compgen -G "$dossier/$dep-[0-9]*.csv" > /dev/null; then
  erreur "la série « $serie » contient déjà des mesures $dep : choisis un autre nom (les fichiers bruts ne sont jamais écrasés)"
fi
[ "$dep" = vm ] && verifier_virtualbox
verifier_jmeter
etape "Déploiement mesuré : $dep (http://$(cible "$dep"))"
verifier_seul "$dep"
attendre_repos "$dep" > /dev/null || erreur "le déploiement $dep ne revient pas au repos (http://$(cible "$dep")/api/health)"
ok "seul en marche, il répond, au repos"
mkdir -p "$dossier"

etape "Jeu de données : réinitialisation des comptes de test"
reinitialiser_comptes "$dep" | tee "$dossier/$dep-jeu-de-donnees.txt" | sed 's/^/    /'

consigner_configuration "$dep" > "$dossier/$dep-configuration.txt"
ok "configuration consignée : $dossier/$dep-configuration.txt"

etape "Proxy : mode charge (limite de connexion de Nginx levée pendant la campagne)"
trap 'arreter_releves; mode_proxy "$dep" normal > /dev/null 2>&1 \
  || echo "ATTENTION : proxy resté en mode charge : bash charge/proxy.sh $dep normal"' EXIT
mode_proxy "$dep" charge
verifier_mode_charge "$dep"
ok "activé"

duree=$((MONTEE + PLATEAU + MARGE))
nb=$(wc -w <<< "$PALIERS")
info "$nb paliers ($PALIERS) : environ $(( nb * (duree + REPOS + 10) / 60 )) minutes"
for n in $PALIERS; do
  etape "Palier $n utilisateurs ($MONTEE s de montée, $PLATEAU s de mesure)"
  base="$dossier/$dep-$n"
  debut=$(date +%s)
  demarrer_releves "$dep" "$base" $((duree + 5))
  jmeter_executer "$dep" "$PLAN" "$base" -Jutilisateurs="$n" -Jmontee="$MONTEE" -Jduree="$duree" \
    -Jcomptes="$COMPTES" -Jreflexion_min="$REFLEXION_MIN" -Jreflexion_alea="$REFLEXION_ALEA" 2>&1 \
    | grep --line-buffered '^summary +' | sed -u 's/^/    /' || true
  attendre_releves
  [ -s "$base.csv" ] || erreur "JMeter n'a rien produit (voir $base.log)"
  evenements "$dep" "$debut" > "$base-evenements.txt" 2> /dev/null || true
  python3 "$CHARGE/analyser.py" palier "$base.csv" --montee "$MONTEE" --plateau "$PLATEAU"
  sleep "$REPOS"
  # Le palier suivant ne commence qu'une fois le système revenu au repos ; cette durée est un résultat
  retour=$(attendre_repos "$dep") || erreur "le déploiement $dep ne revient pas au repos après $n utilisateurs"
  echo "retour_au_repos_s=$((REPOS + retour))" >> "$base-evenements.txt"
  [ "$retour" -gt 0 ] && info "retour au repos : $((REPOS + retour)) s après la fin du palier"
done

etape "Proxy : retour au mode normal"
trap - EXIT
mode_proxy "$dep" normal
ok "configuration d'origine rétablie"

etape "Synthèse de la série « $serie »"
python3 "$CHARGE/analyser.py" rapport "$serie"
