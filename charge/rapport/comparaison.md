# Comparaison chiffrée : trois VM contre trois conteneurs (étapes 17 et 18)

Mesures du 26 octobre 2026, sur le même poste et dans la même séance :

| Série | Ordre | Horaires |
|---|---|---|
| `serie-1` | conteneurs, puis VM | 19 h 12 – 19 h 35 |
| `serie-2` | VM, puis conteneurs (ordre inversé) | 19 h 43 – 20 h 06 |
| `controle-1`, `controle-2` | deux campagnes identiques sur les conteneurs (répétabilité) | 20 h 06 – 20 h 28 |

Fichiers bruts et synthèses : `charge/resultats/<série>/` (`synthese.md`, `vm-*.csv`, `docker-*.csv`, relevés serveur `*-serveur.csv`, configuration `*-configuration.txt`). Les tableaux ci-dessous sont ceux de la série 1 ; la série 2 est comparée en partie 5.

## 1. Conditions de mesure

- **Même application** (même commit), **même jeu de données** : import FMA `--limit 500` des deux côtés, 100 comptes de test avec 20 likes chacun. Les empreintes sont identiques : catalogue `7d7618aa71d1a0dd`, likes `bec4fef387e73cc0`.
- **Même plan, même fichier de comptes, même protocole** : paliers 1, 10, 25, 50, 100, 150 utilisateurs ; 10 s de montée exclues ; 60 s de mesure ; temps de réflexion de 0,5 à 1,5 s ; attente du retour au repos entre les paliers (voir `rapport/etalonnage.md`).
- **Un seul déploiement en marche** pendant chaque campagne (vérifié par `campagne.sh`).
- La limite de Nginx de 10 connexions par minute et par IP est levée pendant les campagnes, à l'identique des deux côtés, puis rétablie.
- **Ressources**, telles que livrées par chaque déploiement :
  - VM : présentation 1 CPU / 512 Mo, métier 2 CPU / 1,5 Go, données 2 CPU / 2,5 Go ;
  - conteneurs : aucune limite, soit les 12 fils et 15,4 Go de la VM de WSL ;
  - dans les deux cas : 3 instances d'API × 2 workers gunicorn.
- **Injecteur** : JMeter 5.6.3, dans Ubuntu (WSL), hors du système mesuré. Il utilise au plus 0,2 cœur pendant les campagnes et son plafond dépasse 40 000 req/s : il n'a jamais limité la mesure.

## 2. Tableau de synthèse

| Grandeur | Trois machines virtuelles | Trois conteneurs |
|---|---|---|
| Débit maximal soutenu | **7,4 req/s** (série 1) / 8,3 req/s (série 2), à 10 utilisateurs | **53,5 req/s** (série 1) / 55,2 req/s (série 2), à 100 utilisateurs |
| Charge au point de saturation | **10 utilisateurs**, dans les deux séries ; à 25, 5 à 25 % d'erreurs | **100 utilisateurs**, dans les deux séries ; aucune erreur jusqu'à 150 |
| Latence au 95e centile, à charge égale (10 utilisateurs) | **625 ms** | **84 ms** |
| Goulot d'étranglement identifié | **mémoire, puis processeur, de `vm-metier`** : le hachage argon2 des connexions fait tuer les workers gunicorn faute de mémoire (1,5 Go) | **processeur de l'hôte**, consommé par le hachage argon2 de l'API (10,9 cœurs sur 12) |
| Temps de démarrage complet | **109,1 s** (médiane de 3 ; `avec-vm/mesures.md`) | **17,1 s** (médiane de 3 ; `avec-docker/mesures.md`) |
| Mémoire consommée au repos | **3 621 Mo** (3 VM, vues de l'hôte) | **4 899 Mo**, moteur compté ; pile plus lourde : Elasticsearch ×3 et Kibana pèsent 2,7 Go (voir `docs/comparaison.md`) |

Définitions appliquées par `analyser.py` :
- **Débit maximal soutenu** : le plus haut débit de requêtes réussies sur un palier où moins de 1 % des requêtes échouent.
- **Point de saturation** : le dernier palier avant que le débit cesse de croître (moins de 10 % de plus), alors que la latence au 95e centile augmente, ou avant que les erreurs dépassent 1 %.

## 3. Résultats côté client

| Utilisateurs | VM : réussies (req/s) | VM : p95 (ms) | VM : erreurs | Conteneurs : réussies (req/s) | Conteneurs : p95 (ms) | Conteneurs : erreurs |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0,9 | 200 | 0 % | 1,0 | 78 | 0 % |
| 10 | 7,4 | 625 | 0 % | 9,6 | 84 | 0 % |
| 25 | 8,0 | 3 121 | 24,6 % | 23,7 | 107 | 0 % |
| 50 | 1,7 | 4 629 | 93,0 % | 45,7 | 309 | 0 % |
| 100 | 3,3 | 11 920 | 89,1 % | 53,5 | 2 303 | 0 % |
| 150 | 4,2 | 30 031 | 86,8 % | 52,1 | 4 601 | 0 % |

![Débit de requêtes réussies](../resultats/serie-1/debit.svg)

![Latence au 95e centile](../resultats/serie-1/latence-p95.svg)

![Taux d'erreur](../resultats/serie-1/erreurs.svg)

**Les conteneurs** suivent la charge jusqu'à 50 utilisateurs (45,7 req/s pour 50 utilisateurs). Entre 50 et 100, le débit ne gagne que 17 % tandis que le 95e centile est multiplié par 7 (309 ms, puis 2,3 s). À 150, le débit recule légèrement (52,1 req/s) et la médiane dépasse 1,7 s. Les requêtes attendent, mais aucune n'échoue.

**Les VM** sont déjà plus lentes à 10 utilisateurs : 7,4 req/s au lieu des 9,6 attendues, et un 95e centile de 625 ms. À 25 utilisateurs, le débit ne croît plus (8,0 req/s) et un quart des requêtes échouent en 502. Au-delà, le service s'effondre : la grande majorité des requêtes échouent, et la médiane de 2 à 4 ms est celle des refus immédiats de Nginx.

## 4. Point de saturation et goulot d'étranglement

### Trois machines virtuelles : la mémoire et le processeur de `vm-metier`

Relevés serveur de `serie-1` (`vm-<N>-serveur.csv`, `vm-<N>-evenements.txt`) :

| Utilisateurs | Processeur de `vm-metier` (utilisé / disponible) | dont API | Mémoire de `vm-metier` (sur 1 463 Mo) | Workers tués faute de mémoire | Workers relancés | Erreurs de Nginx |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 16 / 200 | 15 | 932 Mo | 0 | 0 | 0 |
| 10 | 126 / 200 | 123 | 1 041 Mo | 0 | 0 | 0 |
| 25 | 199 / 200 | 222 | 1 079 Mo | 6 | 9 | 178 |
| 50 | 181 / 200 | 232 | 1 129 Mo | 16 | 25 | 1 549 |

Le mécanisme :
1. Chaque connexion vérifie le mot de passe avec argon2, un hachage volontairement coûteux en calcul **et en mémoire**, qui réserve 64 Mo.
2. L'API exécute ces vérifications en parallèle dans ses fils, et les requêtes s'accumulent dès que les 2 cœurs sont pleins. Les 1,5 Go de `vm-metier` ne suffisent plus.
3. Le noyau tue alors des workers gunicorn. Le journal de `vm-metier` le montre : « Out of memory: Killed process (gunicorn) anon-rss:503664kB ».
4. Pendant que gunicorn les relance, Nginx n'a plus d'instance disponible (« no live upstreams while connecting to upstream ») et renvoie 502.

La base de données n'y est pour rien. MySQL utilise 7 à 11 % d'un cœur, 20 connexions en moyenne, et `vm-donnees` reste sous 21 % de ses 2 cœurs.

**Goulot : la mémoire de `vm-metier`**, épuisée par le hachage argon2 des connexions concurrentes, avec un processeur saturé au même moment (199 / 200).

### Trois conteneurs : le processeur de l'hôte

À 100 utilisateurs, l'API consomme 10,9 cœurs, et l'hôte est à 97 % de ses 12 fils. MySQL reste à 14 % d'un cœur, avec 2 requêtes actives en moyenne. Le 95e centile de la connexion (2,5 s) est 12 fois celui de la consultation des likes (210 ms) : c'est bien le hachage qui sature.

En revanche, aucune instance n'est tuée : les conteneurs n'ont pas de limite de mémoire. Les requêtes attendent donc au lieu d'échouer, ce qui explique 0 % d'erreurs jusqu'à 150 utilisateurs.

**Goulot : le processeur, consommé par argon2.**

À noter : isolée, une vérification argon2 coûte 53 ms de processeur. Sous charge, l'API consomme environ 400 ms de processeur par connexion (10,9 cœurs pour 27 connexions/s). Les hachages concurrents, de 64 Mo chacun, se disputent les caches et la bande passante mémoire.

Lors de la campagne exploratoire (`resultats/exploration-docker/`, jusqu'à 400 utilisateurs), une deuxième limite est apparue. Au-delà de 200 utilisateurs, le pool de connexions SQLAlchemy de chaque instance (5 + 10) s'épuise (« QueuePool limit of size 5 overflow 10 reached »), et des requêtes expirent au bout de 30 s. Après la surcharge, l'API a mis environ 5 minutes à traiter les requêtes déjà abandonnées par JMeter.

### Pourquoi l'écart

- **Débit maximal soutenu : facteur 7** (53,5 contre 7,4 req/s). **Charge supportée : facteur 10** (100 contre 10 utilisateurs). Cet écart vient avant tout **des ressources attribuées, et non de la technique d'isolation**. Les deux déploiements butent sur la même opération : argon2 à la connexion. L'API des VM ne dispose que de 2 cœurs et 1,5 Go ; celle des conteneurs, de 12 fils et de 15 Go.
- **La virtualisation a un coût propre, mesurable mais secondaire.** À 10 utilisateurs, `vm-metier` utilise 126 % d'un cœur vu de l'intérieur, et 136 % vu de l'hôte. Pour `vm-donnees`, c'est 21 % contre 49 %. L'étalonnage montre la même chose sur Nginx : 100 % dans la VM correspondent à 135 % sur l'hôte.
- **Le chemin réseau joue même sans charge.** À 1 utilisateur, rien n'est saturé, et pourtant la consultation des likes a un 95e centile de 58 ms côté VM, contre 8 ms côté conteneurs. Elle traverse trois machines par le réseau privé de VirtualBox, au lieu d'un pont virtuel dans le même noyau.
- **Le mode de défaillance diffère.** Faute de mémoire, les VM perdent des processus et renvoient des erreurs. Les conteneurs, sans limite, ralentissent mais répondent. Avec une limite de mémoire sur les conteneurs, il faudrait s'attendre au même effondrement.

## 5. Répétabilité et ordre de passage

Comparaisons produites par `python3 charge/analyser.py comparer <A> <B>` : `resultats/repetabilite-serie-1-serie-2.md` et `resultats/repetabilite-controle-1-controle-2.md`. Tolérance du sujet : 10 %.

### Ordre de passage (série 1 contre série 2)

| Utilisateurs | Conteneurs : débit S1 / S2 | Écart | VM : débit S1 / S2 | Écart |
|---:|---:|---:|---:|---:|
| 1 | 1,0 / 0,9 | −5 % | 0,9 / 0,9 | +4 % |
| 10 | 9,6 / 9,8 | +2 % | 7,4 / 8,3 | +13 % |
| 25 | 23,7 / 23,6 | 0 % | 8,0 / 9,5 | +18 % |
| 50 | 45,7 / 45,8 | 0 % | 1,7 / 2,5 | +43 % |
| 100 | 53,5 / 55,2 | +3 % | 3,3 / 2,3 | −31 % |
| 150 | 52,1 / 53,1 | +2 % | 4,2 / 1,8 | −59 % |

- **Conteneurs** : les 6 paliers sont dans la tolérance (au plus 5 % sur le débit, 9 % sur le 95e centile). L'ordre de passage n'influe pas.
- **VM** : seul le palier de 1 utilisateur reste dans la tolérance. Au-delà de la saturation, l'écart n'a plus de sens : le débit dépend du moment où le noyau tue les workers et de leur relance, et ce régime est chaotique par nature. À 10 utilisateurs, l'écart est de +13 %. Les conclusions restent les mêmes dans les deux séries : saturation à 10 utilisateurs, effondrement en 502 dès 25.

### Répétabilité (deux campagnes identiques sur les conteneurs)

| Utilisateurs | Débit contrôle 1 / 2 | Écart | p95 contrôle 1 / 2 (ms) | Écart |
|---:|---:|---:|---:|---:|
| 1 | 1,0 / 0,9 | −5 % | 71 / 68 | −4 % |
| 10 | 9,8 / 9,5 | −2 % | 75 / 75 | 0 % |
| 25 | 23,9 / 23,9 | 0 % | 115 / 123 | +7 % |
| 50 | 45,8 / 46,7 | +2 % | 326 / 259 | −21 % |
| 100 | 55,1 / 46,7 | −15 % | 2 254 / 4 060 | +80 % |
| 150 | 52,9 / 43,2 | −18 % | 4 483 / 6 116 | +36 % |

**Sous la saturation, la mesure est répétable** : écart de débit de 5 % au plus. **À saturation, elle ne l'est pas** :
- au contrôle 2, à 100 et 150 utilisateurs, le processeur de l'hôte est aussi plein qu'au contrôle 1 (1 143 % contre 1 162 %), mais le débit est inférieur de 15 à 18 %. Le même processeur a fait moins de travail ;
- **le poste servait aussi à d'autres tâches pendant cette partie de la séance** : la VM de WSL partageait alors le processeur physique avec Windows ;
- les trois autres campagnes sur les conteneurs (séries 1 et 2, contrôle 1) concordent à ±3 % à 100 utilisateurs (53,5, 55,2 et 55,1 req/s). Le contrôle 2 est donc l'exception, et non la règle.

Conclusion : les chiffres à saturation des conteneurs sont à prendre à ±3 % dans un poste au repos, et le contrôle 2 illustre l'avertissement du sujet : c'est alors le bruit du poste qui est mesuré. Un nouveau contrôle, poste au repos, lèverait la réserve.

## 6. Ce que la mesure ne montre pas

- **La précision** : un écart de moins de 10 % entre les déploiements ne serait pas significatif ; à saturation, une mesure faite pendant que le poste sert à autre chose s'écarte de 15 à 18 %. Les écarts observés ici sont d'un facteur 7 à 10, et reproduits dans les deux séries : ce n'est pas du bruit.
- **Un seul parcours.** La connexion et la consultation des likes sont mesurées ; la recherche (Elasticsearch), l'écoute (fichiers audio par Nginx et NFS) et l'envoi d'albums ne le sont pas. Les trois nœuds Elasticsearch de la version Docker ne sont pas sollicités.
- **Un parcours dominé par la connexion.** Chaque parcours se reconnecte, donc refait un hachage argon2. Une application réelle garde la session (JWT de 15 min, session de 7 jours) : la capacité de consultation serait bien plus élevée.
- **Une seule machine.** L'injecteur, VirtualBox et le moteur Docker partagent le même processeur : les chiffres absolus dépendent du poste. Côté conteneurs, l'API a pu prendre les cœurs de l'hôte ; côté VM, non.
- **Des ressources différentes.** La comparaison porte sur les deux déploiements tels qu'ils sont livrés, pas sur deux techniques à ressources égales. Un essai complémentaire limiterait les conteneurs comme les VM (`cpus: 2`, `mem_limit: 1.5g` pour l'API).
- **Un seul client.** Toutes les requêtes viennent de la même adresse IP : la limite de connexion de Nginx a dû être levée.
- **Une charge fermée.** Chaque utilisateur virtuel attend la réponse avant de continuer, donc la charge offerte baisse quand le système ralentit.
- **La durée.** Des paliers de 60 s ne révèlent ni fuite de mémoire, ni dégradation lente.
- **Le démarrage et la mémoire au repos** ont été mesurés en fin de séance (étapes 10 et 14), alors que le poste servait aussi à d'autres tâches : la charge moyenne de l'hôte est consignée à chaque exécution (`charge/resultats/repos/`).
