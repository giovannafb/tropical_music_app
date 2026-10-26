# Rapport d'étalonnage (étapes 15 et 16)

Ce rapport établit que l'instrument mesure le système, et non lui-même. Mesures du 26 octobre 2026, sur un même poste et dans la même séance. Les fichiers bruts sont dans `charge/resultats/validation/` et `charge/resultats/etalonnage/`.

## 1. L'instrument

| Élément | Valeur |
|---|---|
| Outil d'injection | Apache JMeter 5.6.3, Java 21.0.13 (Eclipse Temurin), installés par `charge/installer.sh` |
| Exécution | en ligne de commande uniquement (`jmeter -n`) ; l'interface graphique ne sert qu'à construire et déboguer le plan |
| Emplacement de l'injecteur | Ubuntu 24.04 (WSL 2), sur l'hôte : hors des VM et hors des conteneurs |
| Poste | AMD Ryzen 5 7500F (6 cœurs, 12 fils), 15,4 Go de mémoire pour WSL, noyau 6.6.87.2-microsoft-standard-WSL2 |
| Déploiements | 3 VM VirtualBox 7.1.18 (`avec-vm/`) ; 3 conteneurs, moteur Docker installé dans Ubuntu (`avec-docker/`) |
| Plan de test | `charge/plan/musicapp.jmx` : connexion (`POST /api/auth/login`) puis titres likés (`GET /api/me/likes/tracks`) |
| Jeu de données | import FMA `--limit 500` des deux côtés (archives vérifiées par leur SHA-1 officiel) : 500 titres ; 100 comptes de test, 20 likes chacun |
| Identité des jeux de données | empreintes identiques sur les deux déploiements : catalogue `7d7618aa71d1a0dd`, likes `bec4fef387e73cc0` (`resultats/jeu-de-donnees/`) |

## 2. Validation du plan (étape 15)

`bash charge/valider.sh <vm|docker>` ; comptes rendus dans `resultats/validation/vm-validation.txt` et `docker-validation.txt`.

| Exécution (1 utilisateur, 1 itération) | Attendu | Trois VM | Trois conteneurs |
|---|---|---|---|
| Compte valide | connexion 200 + cookie, puis au moins un titre liké | conforme : 200 puis 200 | conforme : 200 puis 200 |
| Mauvais mot de passe | l'assertion de la connexion échoue, la consultation n'est pas jouée | conforme : 401, assertion déclenchée | conforme : 401, assertion déclenchée |
| Compte sans like (`charge000`) | consultation en 200, mais l'assertion de contenu échoue | conforme : 200, « No results for path: $[0]['id'] » | conforme : idem |

Le troisième cas montre que le plan ne se contente pas d'un code de succès : une liste vide, ou une page d'erreur renvoyée avec un code 200, est comptée comme une erreur.

Deux points vérifiés pendant la construction du plan :
- **Les cookies sont `Secure`, donc JMeter ne les renvoie pas sur `http://`.** Sans l'extracteur du jeton, la consultation reçoit 401.
- **La limite de Nginx (10 connexions par minute et par IP) est levée** pendant les campagnes, à l'identique sur les deux déploiements, puis rétablie (`charge/commun.sh`, `mode_proxy`).

Captures d'écran de l'interface graphique (*Arbre de résultats*) : à ajouter.

## 3. Plafond de l'injecteur

`bash charge/etalonner.sh <vm|docker>` : ressource statique servie par le proxy seul (`/assets/placeholder-cover.svg`), sans temps de réflexion, 10 s de montée, 60 s de mesure (`resultats/etalonnage/synthese.md`). Processeur en % d'un cœur.

| Utilisateurs | VM : débit (req/s) | VM : Nginx | VM : JMeter | Docker : débit (req/s) | Docker : Nginx | Docker : JMeter | Docker : hôte (sur 1 200) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 10 | 4 597 | 99 / 100 | 46 | 19 640 | 172 | 170 | 719 |
| 50 | 4 473 | 100 / 100 | 52 | 39 313 | 253 | 313 | 924 |
| 100 | 4 365 | 100 / 100 | 52 | 43 153 | 283 | 349 | 983 |
| 200 | 3 566 | 100 / 100 | 45 | 40 192 | 278 | 382 | 1 017 |

- **VM** : le débit est plafonné par Nginx, qui sature l'unique cœur de `vm-presentation` (100 / 100). JMeter n'utilise alors qu'un demi-cœur, et l'hôte 23 % de sa capacité : le plafond de l'injecteur est donc supérieur à 4 600 req/s.
- **Docker** : environ 43 000 req/s, avec l'hôte à 82 % de ses 12 fils, partagés entre JMeter (3,5 cœurs), Nginx et le noyau. C'est le plafond de l'injecteur sur ce poste.
- **Débit maximal de l'application** (étape 17) : 52 à 54 req/s environ côté Docker (campagne exploratoire), moins côté VM. Soit **un centième du plafond de l'injecteur**, et moins de 2 % du plafond du Nginx de la VM. Pendant les campagnes, JMeter utilise au plus 0,2 cœur. L'injecteur n'est donc jamais le facteur limitant.

Déjà visible ici : le même travail (100 % d'un cœur dans `vm-presentation`) coûte 135 % d'un cœur vu de l'hôte. C'est le coût de la virtualisation.

## 4. Protocole retenu, puis gelé

Fixé dans `charge/commun.sh`, identique pour les deux déploiements. Il a été raccourci par rapport au premier essai (30 s de montée, 90 s de mesure, 10 paliers jusqu'à 400 utilisateurs), pour tenir dans une seule séance.

| Réglage | Valeur | Justification |
|---|---|---|
| Paliers | 1, 10, 25, 50, 100, 150 utilisateurs | progression large ; la campagne exploratoire montre que Docker sature entre 50 et 100 utilisateurs ; 150 dépasse la saturation des deux déploiements |
| Montée | 10 s, exclue des mesures | 150 utilisateurs démarrés en 10 s, soit un toutes les 0,07 s |
| Fenêtre de mesure | 60 s par palier | le minimum imposé hors montée |
| Pause entre paliers | 10 s, puis attente du retour au repos | après une surcharge, l'API traite encore pendant plusieurs minutes les requêtes que JMeter a abandonnées (constaté : environ 5 min après 400 utilisateurs) ; le palier suivant ne démarre qu'une fois `/api/health` revenu sous 0,5 s, trois fois de suite |
| Temps de réflexion | 0,5 à 1,5 s, tiré avant chaque requête | usage réel : environ un parcours toutes les 2 s par utilisateur |
| Délais HTTP | 10 s pour la connexion TCP, 30 s pour la réponse | une requête sans réponse compte comme une erreur, au lieu de bloquer un utilisateur |
| Comptes | 100, réinitialisés au début de chaque campagne | même état de départ, sessions Redis comprises |

## 5. Répétabilité

Deux campagnes identiques sur les conteneurs, `controle-1` puis `controle-2` (20 h 06 – 20 h 28), comparées par `python3 charge/analyser.py comparer controle-1 controle-2` (`resultats/repetabilite-controle-1-controle-2.md`). Tolérance : 10 %.

| Utilisateurs | Écart de débit | Écart de latence au 95e centile | Verdict |
|---:|---:|---:|---|
| 1 | −5,0 % | −4,2 % | dans la tolérance |
| 10 | −2,4 % | 0,0 % | dans la tolérance |
| 25 | −0,3 % | +7,0 % | dans la tolérance |
| 50 | +2,1 % | −20,6 % | hors tolérance (latence) |
| 100 | −15,3 % | +80,1 % | hors tolérance |
| 150 | −18,2 % | +36,4 % | hors tolérance |

Verdict :
- **Sous la saturation, la mesure est répétable.**
- **À saturation, elle ne l'est pas.** Pendant le contrôle 2, le poste servait aussi à d'autres tâches : à processeur de l'hôte égal (plein), le débit était inférieur de 15 à 18 %.
- Les trois autres campagnes sur les conteneurs (séries 1 et 2, contrôle 1) concordent à ±3 % à 100 utilisateurs. Sur ce poste au repos, la précision à saturation est donc d'environ ±3 %.
- Comme le dit le sujet, un écart de plus de 10 % mesure le bruit du poste, pas le déploiement. Il faudra refaire le contrôle poste au repos pour lever la réserve.

Les fichiers `resultats/exploration-docker/` (campagne exploratoire, protocole long) et `resultats/interrompu-controle-1/` (campagne interrompue, avant le raccourcissement du protocole) sont conservés pour traçabilité. Ils ne sont pas comparables aux séries, puisque le protocole y diffère.
