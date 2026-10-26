#!/usr/bin/env bash
# Étape 16 : plafond de l'injecteur. JMeter demande une ressource statique servie par le proxy (Nginx seul),
# sans temps de réflexion, à plusieurs paliers. Le débit obtenu doit être nettement supérieur à celui attendu
# de l'application : sinon les campagnes mesureraient JMeter, et non le déploiement.
# Les connexions HTTP sont réutilisées : on mesure ce que JMeter peut produire, pas l'ouverture de connexions.
#
#   bash charge/etalonner.sh docker
#   bash charge/etalonner.sh vm
#
# Le contrôle de répétabilité de l'étape 16 se fait avec deux campagnes identiques :
#   bash charge/campagne.sh vm controle-1 && bash charge/campagne.sh vm controle-2
#   python3 charge/analyser.py comparer controle-1 controle-2
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"
dep="${1:-}"
verifier_deploiement "$dep"
[ "$dep" = vm ] && verifier_virtualbox
verifier_jmeter
verifier_seul "$dep"
verifier_cible "$dep"
curl -fs -o /dev/null "http://$(cible "$dep")$RESSOURCE_STATIQUE" || erreur "$RESSOURCE_STATIQUE n'est pas servie par le proxy"
dossier="$RESULTATS/etalonnage"
if compgen -G "$dossier/$dep-[0-9]*.csv*" > /dev/null; then
  erreur "charge/resultats/etalonnage contient déjà des mesures $dep (les fichiers bruts ne sont jamais écrasés : les déplacer d'abord)"
fi
mkdir -p "$dossier"

PALIERS="$ETALONNAGE_PALIERS" MONTEE="$ETALONNAGE_MONTEE" PLATEAU="$ETALONNAGE_PLATEAU" REFLEXION_MIN=0 REFLEXION_ALEA=0
consigner_configuration "$dep" > "$dossier/$dep-configuration.txt"
echo "ressource=$RESSOURCE_STATIQUE" >> "$dossier/$dep-configuration.txt"
trap arreter_releves EXIT

duree=$((MONTEE + PLATEAU + MARGE))
for n in $PALIERS; do
  etape "Ressource statique, $n utilisateurs sans temps de réflexion ($MONTEE s de montée, $PLATEAU s de mesure)"
  base="$dossier/$dep-$n"
  demarrer_releves "$dep" "$base" $((duree + 5))
  jmeter_executer "$dep" "$PLAN_STATIQUE" "$base" -Jutilisateurs="$n" -Jmontee="$MONTEE" -Jduree="$duree" \
    -Jchemin="$RESSOURCE_STATIQUE" -Jhttpclient.reset_state_on_thread_group_iteration=false 2>&1 \
    | grep --line-buffered '^summary +' | sed -u 's/^/    /' || true
  attendre_releves
  [ -s "$base.csv" ] || erreur "JMeter n'a rien produit (voir $base.log)"
  python3 "$CHARGE/analyser.py" palier "$base.csv" --montee "$MONTEE" --plateau "$PLATEAU"
  xz -T0 "$base.csv"   # une ligne par requête, à des dizaines de milliers de req/s : 30 fois moins lourd, lu tel quel par l'analyse
  sleep "$REPOS"
done
trap - EXIT

etape "Synthèse de l'étalonnage"
python3 "$CHARGE/analyser.py" rapport etalonnage
info "Plafond de l'injecteur = débit maximal de cette série ; à reporter dans charge/rapport/etalonnage.md,"
info "avec la charge processeur de JMeter et de l'hôte (tableaux « Côté serveur » de la synthèse)."
