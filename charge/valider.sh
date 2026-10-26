#!/usr/bin/env bash
# Étape 15 : valide le plan de test avec un seul utilisateur et une seule itération, en ligne de commande.
# Trois exécutions : le parcours qui doit réussir, puis deux parcours qui doivent échouer (le test du test) :
#   - mauvais mot de passe : l'assertion de la connexion doit se déclencher ;
#   - compte sans aucun like : la consultation répond 200, mais l'assertion de contenu doit la refuser.
# Les fichiers bruts et le compte rendu lisible vont dans charge/resultats/validation/.
#
#   bash charge/valider.sh docker
#   bash charge/valider.sh vm
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"
dep="${1:-}"
verifier_deploiement "$dep"
[ "$dep" = vm ] && verifier_virtualbox
verifier_jmeter
verifier_seul "$dep"
verifier_cible "$dep"
dossier="$RESULTATS/validation"
mkdir -p "$dossier"

etape "Comptes de test"
reinitialiser_comptes "$dep" | sed 's/^/    /'

# Affiche les requêtes d'une exécution : libellé, code, verdict des assertions
afficher() {
  python3 - "$1" <<'PY'
import csv, sys
for l in csv.DictReader(open(sys.argv[1], encoding="utf-8")):
    verdict = "réussie" if l["success"] == "true" else "ÉCHEC : " + (l["failureMessage"] or l["responseMessage"])
    print(f'    {l["label"]:<16} HTTP {l["responseCode"]}  {l["elapsed"]:>5} ms  {verdict}')
PY
}

# Vérifie qu'une exécution a donné exactement les résultats attendus (« libellé:true|false » dans l'ordre)
conforme() {
  [ "$(python3 -c 'import csv, sys; print(" ".join(l["label"] + ":" + l["success"] for l in csv.DictReader(open(sys.argv[1], encoding="utf-8"))))' "$1")" = "$2" ]
}

compte_rendu="$dossier/$dep-validation.txt"
{
  echo "Validation du plan charge/plan/musicapp.jmx — déploiement $dep (http://$(cible "$dep")) — $(date -Iseconds)"
  echo "1 utilisateur, 1 itération ; fichiers bruts : $dep-<cas>.csv"
} > "$compte_rendu"
echec=0
for cas in reussite echec-mot-de-passe echec-sans-like; do
  case "$cas" in
    reussite) comptes="$COMPTES"; attendu="1-Connexion:true 2-Titres-likes:true"
      titre="Parcours réussi (compte du fichier de comptes)" ;;
    echec-mot-de-passe) comptes="$COMPTES_INVALIDES"; attendu="1-Connexion:false"
      titre="Doit échouer : mauvais mot de passe" ;;
    echec-sans-like) comptes="$COMPTES_SANS_LIKE"; attendu="1-Connexion:true 2-Titres-likes:false"
      titre="Doit échouer : compte sans aucun like (réponse 200 mais liste vide)" ;;
  esac
  etape "$titre"
  rm -f "$dossier/$dep-$cas.csv"
  jmeter_executer "$dep" "$PLAN" "$dossier/$dep-$cas" -Jutilisateurs=1 -Jiterations=1 -Jmontee=0 -Jduree=60 \
    -Jcomptes="$comptes" > "$dossier/$dep-$cas.console" 2>&1 || true
  [ -s "$dossier/$dep-$cas.csv" ] || erreur "JMeter n'a rien produit (voir $dossier/$dep-$cas.log)"
  rm -f "$dossier/$dep-$cas.console"
  tableau="$(afficher "$dossier/$dep-$cas.csv")"
  echo "$tableau"
  if conforme "$dossier/$dep-$cas.csv" "$attendu"; then
    verdict="conforme à l'attendu"
    ok "$verdict"
  else
    verdict="NON CONFORME (attendu : $attendu)"
    echo "    $verdict"
    echec=1
  fi
  printf '\n== %s : %s\n%s\n' "$titre" "$verdict" "$tableau" >> "$compte_rendu"
done
echo
if grep -q ' 429 ' "$compte_rendu"; then
  echo "La connexion a reçu 429 : limite de Nginx (10 connexions par minute). Attendre une minute et relancer."
fi
[ "$echec" -eq 0 ] || erreur "le plan ne se comporte pas comme attendu (compte rendu : $compte_rendu)"
ok "le plan détecte le succès comme l'échec ; compte rendu : $compte_rendu"
info "Pour la capture d'écran demandée : la même exécution dans l'interface graphique (Arbre de résultats),"
info "  JAVA_HOME=$JAVA_DIR $JMETER_HOME/bin/jmeter -t charge/plan/musicapp.jmx -Jhote=$(cible_hote "$dep") -Jport=$(cible_port "$dep") -Jiterations=1"
info "  puis -Jcomptes=$COMPTES_INVALIDES pour le parcours en échec."
