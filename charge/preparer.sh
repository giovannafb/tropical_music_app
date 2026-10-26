#!/usr/bin/env bash
# Crée ou réinitialise les comptes de test (comptes/comptes.csv) dans la base d'un déploiement, et affiche
# l'empreinte du catalogue et des likes : elle doit être la même pour les deux déploiements (même jeu de données).
# campagne.sh et valider.sh le refont d'eux-mêmes ; ce script sert à vérifier le jeu de données avant les mesures.
#
#   bash charge/preparer.sh docker
#   bash charge/preparer.sh vm
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"
dep="${1:-}"
verifier_deploiement "$dep"
[ "$dep" = vm ] && verifier_virtualbox
verifier_cible "$dep"

etape "Comptes de test dans le déploiement $dep"
mkdir -p "$RESULTATS/jeu-de-donnees"
reinitialiser_comptes "$dep" | tee "$RESULTATS/jeu-de-donnees/$dep.txt" | sed 's/^/    /'
ok "fichiers de comptes : charge/comptes/*.csv ; empreintes : charge/resultats/jeu-de-donnees/$dep.txt"
autre=$([ "$dep" = vm ] && echo docker || echo vm)
if [ -f "$RESULTATS/jeu-de-donnees/$autre.txt" ]; then
  if diff -q <(grep -i empreinte "$RESULTATS/jeu-de-donnees/$dep.txt") \
             <(grep -i empreinte "$RESULTATS/jeu-de-donnees/$autre.txt") > /dev/null; then
    ok "même catalogue et mêmes likes que le déploiement $autre"
  else
    echo "ATTENTION : les empreintes diffèrent de celles du déploiement $autre : le jeu de données n'est pas identique"
    echo "            (même import FMA, avec le même --limit, des deux côtés ?)"
  fi
fi
