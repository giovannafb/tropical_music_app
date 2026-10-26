#!/usr/bin/env bash
# Met le proxy d'un déploiement en mode charge (limite de connexion de Nginx levée) ou le remet en mode normal.
# campagne.sh et etalonner.sh le font d'eux-mêmes ; ce script sert si une campagne a été interrompue brutalement.
#
#   bash charge/proxy.sh docker normal
#   bash charge/proxy.sh vm charge
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"
dep="${1:-}"
mode="${2:-}"
verifier_deploiement "$dep"
[[ "$mode" == charge || "$mode" == normal ]] || erreur "indique le mode : charge ou normal"
[ "$dep" = vm ] && verifier_virtualbox
mode_proxy "$dep" "$mode"
[ "$mode" = charge ] && verifier_mode_charge "$dep"
ok "proxy du déploiement $dep en mode $mode"
