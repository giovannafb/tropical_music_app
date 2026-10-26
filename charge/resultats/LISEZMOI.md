# Résultats bruts du test de charge

Fichiers produits par les scripts de `charge/`, **conservés et versionnés** : un tableau de synthèse sans les données qui l'ont produit n'est pas vérifiable. Rien ici n'est écrit à la main, et un fichier brut n'est jamais écrasé.

| Dossier | Produit par |
|---|---|
| `validation/` | `valider.sh` (étape 15) : un parcours réussi et deux en échec, par déploiement |
| `etalonnage/` | `etalonner.sh` (étape 16) : plafond de l'injecteur |
| `controle-1/`, `controle-2/` | deux campagnes identiques : répétabilité (étape 16) |
| `serie-1/`, `serie-2/` | `campagne.sh` (étape 17), l'ordre des déploiements étant inversé d'une série à l'autre |
| `repos/` | `repos.sh` : temps de démarrage et mémoire au repos (pas encore mesuré) |
| `repetabilite-<A>-<B>.md` | `analyser.py comparer` : écarts entre deux séries |
| `exploration-docker/` | première campagne, protocole long (30 s de montée, 90 s de mesure, jusqu'à 400 utilisateurs) : conservée, non comparable aux séries |
| `interrompu-controle-1/` | campagne interrompue lors du raccourcissement du protocole : conservée, non exploitée |
| `jeu-de-donnees/` | `preparer.sh` : empreintes du catalogue et des likes de chaque déploiement |

Dans le dossier d'une série, pour chaque déploiement (`vm` ou `docker`) et chaque palier `N` :

| Fichier | Contenu |
|---|---|
| `<dép>-configuration.txt` | configuration qui a produit les chiffres : protocole, poste, versions, ressources des VM ou de Docker |
| `<dép>-jeu-de-donnees.txt` | empreintes du catalogue et des likes au début de la campagne |
| `<dép>-N.csv` | résultats JMeter : une ligne par requête (horodatage, durée, code, succès, message d'assertion…) ; compressé en `.csv.xz` pour l'étalonnage (`xz -dk` pour le relire) |
| `<dép>-N.log` | journal de JMeter |
| `<dép>-N-serveur.csv` | relevés du système sous test, toutes les 5 s (`horodatage_us,source,service,mesure,valeur`) |
| `<dép>-N-hote.csv` | relevés de l'hôte : processeur total, JMeter, chaque VM |
| `<dép>-N-evenements.txt` | incidents pendant le palier |
| `synthese.md`, `synthese.csv`, `*.svg` | analyse (`python3 charge/analyser.py rapport <série>`) |

Les horodatages sont ceux de l'hôte : les relevés des VM et des conteneurs sont horodatés à leur arrivée, sur la même horloge que JMeter.
