# MusicApp — test de charge avec JMeter (partie 4)

Les deux déploiements de la même application, **trois VM** ([`avec-vm/`](../avec-vm/LISEZMOI.md)) et **trois conteneurs** ([`avec-docker/`](../avec-docker/LISEZMOI.md)), sont soumis au même scénario de charge, dans les mêmes conditions, **un seul à la fois**. Le but n'est pas de désigner un gagnant : il s'agit de mesurer jusqu'à quelle charge chacun tient, et ce qui cède en premier.

Tout le test de charge est dans ce dossier : le code de l'application et les deux déploiements ne sont pas modifiés.

```
Ubuntu (WSL), sur l'hôte                         Système sous test (un seul démarré)
┌─────────────────────────────┐   HTTP    ┌──────────────────────────────────────────┐
│ JMeter, en ligne de commande │ ────────► │ proxy (Nginx) → métier (API ×3) → données │
│ relevés : charge/metriques/  │ ◄──────── │ VM : 192.168.56.11:80   Docker : localhost:80 │
└─────────────────────────────┘ cgroups,  └──────────────────────────────────────────┘
                                docker stats, état de MySQL
```

## Le scénario

Le sujet parle de « consultation de notes » : pour MusicApp, le parcours équivalent est **se connecter, puis consulter ses titres likés** (écran *Likes*). C'est le seul parcours qui traverse les trois couches : Nginx, l'API (argon2, JWT, Redis pour la session) et MySQL.

| Ordre | Requête | Ce qui est vérifié |
|---|---|---|
| 1 | `POST /api/auth/login` avec un compte tiré du fichier de comptes | code 200 et présence du cookie `access_token` |
| 2 | `GET /api/me/likes/tracks` : titres likés de l'utilisateur connecté | code 200 et au moins un titre (`$[0].id`) |

Le plan [`plan/musicapp.jmx`](plan/musicapp.jmx) contient les six éléments demandés :

| Élément | Dans le plan | Rôle |
|---|---|---|
| Groupe d'unités | *Utilisateurs* | nombre d'utilisateurs (`-Jutilisateurs`), montée (`-Jmontee`), durée (`-Jduree`) |
| Jeu de données | *Fichier de comptes* | [`comptes/comptes.csv`](comptes/comptes.csv) : 100 comptes, lus ligne par ligne |
| Gestionnaire de cookies | *Gestionnaire de cookies* | vidé à chaque itération : chaque parcours ouvre une nouvelle session |
| Extracteur | *Extracteur du jeton de session* | récupère le JWT dans `Set-Cookie`, renvoyé par l'en-tête *Jeton de session* |
| Assertions | une par vérification du tableau | code de retour **et** contenu attendu |
| Temporisation | *Temps de réflexion* | de 0,5 à 1,5 s avant chaque requête |

Un échec arrête l'itération en cours : sans session, la consultation n'aurait pas de sens.

## Choix techniques à connaître (et à justifier dans le rapport)

1. **Le proxy passe en « mode charge » pendant les mesures.** Nginx limite la connexion à 10 requêtes par minute et par adresse IP (protection contre la force brute). Or toutes les requêtes de JMeter viennent d'une seule adresse : avec cette limite, les deux déploiements plafonneraient à la même valeur, et c'est le limiteur qui serait mesuré. Les scripts retirent donc cette seule ligne (`limit_req … login`) de la configuration installée dans le proxy, **à l'identique sur les deux déploiements**, puis la remettent à la fin, même en cas d'interruption. Aucun fichier du dépôt n'est modifié. En secours : `bash charge/proxy.sh <vm|docker> normal`.
2. **Les cookies de session sont `Secure`.** JMeter les reçoit, mais il ne les renvoie pas sur `http://`. Le plan extrait donc le jeton de la réponse de connexion et le renvoie lui-même : c'est l'extracteur prévu par le sujet. Vérifié : sans lui, la consultation reçoit 401.
3. **La VM est visée par le réseau privé hôte** (`192.168.56.11:80`, autorisé depuis WSL par le pare-feu de `vm-presentation`), et non par la redirection `localhost:8081`. Cette redirection passe par le relais NAT logiciel de VirtualBox, qui serait mesuré en plus. Docker est visé sur `localhost:80`. Les deux cibles se changent avec `CIBLE_VM` et `CIBLE_DOCKER`.
4. **Les comptes de test sont créés par un script, pas par le site** ([`comptes/creer_comptes.py`](comptes/creer_comptes.py), exécuté dans la couche métier). Il crée 100 comptes `charge001`…`charge100`, déjà vérifiés, avec 20 titres likés chacun, plus un compte témoin `charge000` sans aucun like. Les likes ne dépendent que du catalogue : avec le même import FMA, les deux déploiements ont les mêmes données. Le script affiche deux **empreintes** (catalogue et likes) qui permettent de le vérifier. Chaque campagne le relance : anciens comptes de test supprimés avec leurs likes et leurs sessions Redis, donc même état de départ. Le reste de la base (catalogue FMA) n'est que lu par le scénario.
5. **L'injecteur tourne dans Ubuntu (WSL)**, hors des VM et des conteneurs. La VM légère de WSL 2 héberge toutefois aussi VirtualBox et Docker Desktop : l'injecteur partage donc le processeur de la machine. L'étalonnage (étape 16) et le relevé du processeur de JMeter à chaque palier servent à vérifier qu'il ne limite jamais la mesure.

## Le protocole (figé dans [`commun.sh`](commun.sh))

| Réglage | Valeur | Pourquoi |
|---|---|---|
| Paliers | 1, 10, 25, 50, 100, 150 utilisateurs | progression large, jusqu'au-delà de la saturation des deux déploiements (`PALIERS="…"` pour la changer, des deux côtés) |
| Montée | 10 s, **exclue des mesures** | l'inclure ferait baisser le débit et gonflerait la latence |
| Fenêtre de mesure | 60 s par palier (le minimum imposé) | débit, centiles et relevés serveur portent sur cette fenêtre seulement |
| Pause entre paliers | 10 s, **puis attente du retour au repos** | après une surcharge, l'API traite encore les requêtes abandonnées : le palier suivant ne commence que lorsque `/api/health` répond de nouveau vite ; la durée est consignée (`retour_au_repos_s`) |
| Temps de réflexion | 0,5 à 1,5 s avant chaque requête | un usage réel, pas une attaque |
| Délais HTTP | 10 s à la connexion, 30 s de réponse | une requête qui ne répond pas devient une erreur |
| Relevés serveur | toutes les 5 s | voir plus bas |

Un palier = une exécution de JMeter en ligne de commande, avec un seul plan paramétré :

```
jmeter -n -t plan/musicapp.jmx -q plan/resultats.properties -l resultats/serie-1/vm-50.csv -Jutilisateurs=50 -Jmontee=10 -Jduree=75 …
```

## Procédure

Tout se lance dans le **terminal Ubuntu**, depuis le dossier du projet (là où se trouvent `avec-vm/` et `avec-docker/`). Les deux déploiements doivent être installés, avec **le même import FMA** (même `--limit`).

### Première fois

```
bash charge/installer.sh            # Java 21 et JMeter 5.6.3 dans ~/.musicapp-charge (sans sudo)
```

Pour Docker, la commande `docker` doit être utilisable dans Ubuntu : intégration WSL de Docker Desktop activée (*Settings > Resources > WSL integration*), sinon `docker.exe` est utilisé.

### Étape 15 — valider le plan

Avec un seul déploiement démarré :

```
bash charge/valider.sh vm           # puis, l'autre démarré seul : bash charge/valider.sh docker
```

Trois exécutions à 1 utilisateur et 1 itération : le parcours réussi, puis deux parcours qui **doivent** échouer (le test du test). Avec un mauvais mot de passe, l'assertion de la connexion se déclenche ; avec le compte sans like, la consultation répond 200 mais l'assertion de contenu la refuse. Compte rendu : `resultats/validation/<déploiement>-validation.txt`. Le script affiche aussi la commande qui ouvre l'interface graphique, pour la capture d'écran demandée (*Arbre de résultats*).

### Étape 16 — étalonner

```
bash charge/etalonner.sh vm         # et/ou docker
```

JMeter demande une ressource statique servie par le proxy seul (`/assets/placeholder-cover.svg`), sans temps de réflexion, à 10, 50, 100 et 200 utilisateurs. Le débit maximal obtenu est le **plafond de l'injecteur**. Il doit être nettement supérieur au débit de l'application.

Contrôle de répétabilité : deux campagnes identiques sur le même déploiement, puis la comparaison (écart toléré : 10 %).

```
bash charge/campagne.sh vm controle-1
bash charge/campagne.sh vm controle-2
python3 charge/analyser.py comparer controle-1 controle-2
```

Reporter les chiffres dans [`rapport/etalonnage.md`](rapport/etalonnage.md).

### Étape 17 — les campagnes

Pour chaque campagne : **démarrer un seul déploiement, arrêter l'autre complètement**. Le script refuse de mesurer si l'autre tourne encore, ou si la version sans Docker tourne. Ensuite, toujours dans la même séance :

```
# Série 1 : VM, puis Docker
bash avec-vm/demarrer.sh
bash charge/campagne.sh vm serie-1
bash avec-vm/arreter.sh
(cd avec-docker && docker compose up -d --scale api=3)
bash charge/campagne.sh docker serie-1
(cd avec-docker && docker compose stop)

# Série 2 : ordre inversé, pour vérifier que l'ordre de passage n'influe pas
(cd avec-docker && docker compose up -d --scale api=3)
bash charge/campagne.sh docker serie-2
(cd avec-docker && docker compose stop)
bash avec-vm/demarrer.sh
bash charge/campagne.sh vm serie-2
bash avec-vm/arreter.sh

python3 charge/analyser.py comparer serie-1 serie-2
```

Une campagne de 6 paliers dure une dizaine de minutes, plus le temps de retour au repos après les paliers saturés. Avant de lancer la mesure, chaque campagne vérifie le déploiement, réinitialise les comptes de test, consigne la configuration et passe le proxy en mode charge. Elle relève ensuite les métriques serveur à chaque palier et affiche un résumé par palier. Les fichiers bruts ne sont jamais écrasés : un nom de série déjà utilisé est refusé.

Pour un poste stable : navigateur, antivirus et mises à jour au repos, secteur branché, même session de travail pour les deux déploiements.

### Étape 18 — analyser

```
python3 charge/analyser.py rapport serie-1
```

Le script produit `resultats/serie-1/synthese.md`, qui contient :

- le tableau côté client par palier (débit, centiles 50/90/95/99, erreurs par requête) ;
- les relevés côté serveur (processeur et mémoire par service, connexions et entrées-sorties de MySQL, incidents) ;
- le point de saturation de chaque déploiement, et le **tableau de synthèse** ;
- les graphiques `debit.svg`, `latence-p95.svg` et `erreurs.svg`.

`campagne.sh` le lance à la fin de chaque campagne. L'analyse rédigée va dans [`rapport/comparaison.md`](rapport/comparaison.md).

Les deux dernières lignes du tableau (temps de démarrage, mémoire au repos) viennent des étapes 10 et 14. Pour les relever avec le même protocole des deux côtés (trois exécutions, médiane) :

```
bash charge/repos.sh vm
bash charge/repos.sh docker         # moteur compté : sa mémoire est retirée de la mesure à vide (Docker Desktop : il faut le quitter)
```

## Ce qui est relevé

| Côté client (JMeter, fichier brut `<déploiement>-<N>.csv`) | Côté serveur (`<déploiement>-<N>-serveur.csv`, `-hote.csv`) |
|---|---|
| débit en requêtes/s, et parcours complets/s | processeur par service : cgroups systemd dans chaque VM, `docker stats` pour les conteneurs (même source : les cgroups du noyau) |
| latence : médiane, 90e, 95e et 99e centiles | mémoire par service (hors cache inactif, comme `docker stats`), et par VM |
| taux d'erreur par requête, avec leurs causes | MySQL : connexions ouvertes et actives, requêtes SQL/s, octets lus et écrits par InnoDB ; disque de la base |
| utilisateurs simultanés effectifs | hôte : processeur total, processeur de JMeter et de chaque VM vue de l'hôte |
| | incidents : workers gunicorn relancés ou hors délai, processus tués faute de mémoire, erreurs de Nginx |

Le processeur est exprimé en **pourcentage d'un cœur** (200 = deux cœurs pleins). Une VM a les cœurs qui lui sont attribués (`CPU_*` dans `avec-vm/.env`) ; les conteneurs n'ont pas de limite et se partagent les cœurs de la VM de WSL.

## Différences connues entre les deux déploiements

Elles ne viennent pas du protocole, mais elles expliquent une partie des écarts : à citer dans l'analyse.

| | Trois VM | Trois conteneurs |
|---|---|---|
| Processeur et mémoire | fixés par VM : présentation 1 CPU / 512 Mo, métier 2 CPU / 1,5 Go, données 2 CPU / 2,5 Go | sans limite : tous les cœurs et toute la mémoire de la VM de WSL |
| API | 3 instances × 2 workers gunicorn | 3 conteneurs × 2 workers gunicorn |
| MySQL | paquet Ubuntu 24.04 (8.0) | image `mysql:8.4` |
| Elasticsearch | 1 nœud | 3 nœuds + Kibana (inactifs pour ce scénario, mais en mémoire) |
| Réseau | trois machines, réseau privé hôte VirtualBox | un pont virtuel dans le même noyau |

## Fichiers

| Fichier | Rôle |
|---|---|
| `installer.sh` | Java + JMeter dans `~/.musicapp-charge` |
| `valider.sh`, `etalonner.sh`, `campagne.sh`, `repos.sh` | étapes 15, 16, 17, et relevés des étapes 10/14 |
| `preparer.sh` | crée les comptes de test seuls et compare les empreintes des deux déploiements |
| `proxy.sh` | met le proxy en mode charge ou normal, à la main |
| `analyser.py` | synthèse, saturation, graphiques, répétabilité (étape 18) |
| `commun.sh` | protocole figé, cibles, fonctions communes (réutilise `avec-vm/commun.sh` sans le modifier) |
| `plan/musicapp.jmx`, `plan/etalonnage.jmx` | plans de test |
| `plan/resultats.properties` | format du fichier de résultats bruts (CSV) |
| `comptes/` | fichiers de comptes (générés et versionnés) et script de création |
| `metriques/releve.py` | relevés côté serveur et hôte (bibliothèque standard Python : rien à installer dans les VM) |
| `resultats/` | **fichiers bruts versionnés**, un sous-dossier par série (voir [`resultats/LISEZMOI.md`](resultats/LISEZMOI.md)) |
| `rapport/` | rapport d'étalonnage et comparaison chiffrée, à compléter avec les mesures |

## En cas de problème

| Symptôme | Cause probable |
|---|---|
| Connexions en **429** | proxy pas en mode charge : `bash charge/proxy.sh <déploiement> charge` (ou une campagne interrompue a remis le mode normal) |
| Quelques **401** isolés juste après une connexion réussie | l'horloge de WSL a reculé de quelques centaines de millisecondes : le JWT paraît émis dans le futur (`iat`), et PyJWT le refuse. Observé sur le banc d'essai ; à signaler comme erreur, sans la masquer |
| Le débit plafonne à la même valeur des deux côtés | l'injecteur est saturé : comparer au plafond de l'étalonnage et au processeur de JMeter |
| `JMeter n'a rien produit` | lire `resultats/<série>/<déploiement>-<N>.log` |
| La campagne refuse de démarrer | l'autre déploiement (ou la version sans Docker) tourne encore |
| Les empreintes diffèrent entre les deux déploiements | imports FMA différents (`--limit`) : refaire l'import d'un côté |
