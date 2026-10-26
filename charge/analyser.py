"""Analyse des campagnes de charge (étape 18) : lit les fichiers bruts de charge/resultats/ et produit,
pour chaque série, la synthèse par palier, le tableau de synthèse et les graphiques.

    python3 charge/analyser.py rapport <série>              synthèse d'une série (un ou deux déploiements)
    python3 charge/analyser.py comparer <série A> <série B> répétabilité : écart entre deux séries identiques
    python3 charge/analyser.py palier <fichier.csv>         résumé d'un seul palier (affiché pendant la campagne)

Seules les requêtes lancées dans la fenêtre de mesure comptent : de la fin de la montée (première requête
+ montée) à la fin du plateau. La montée gonflerait la latence et ferait baisser le débit.
Centiles : rang le plus proche (le 95e centile est la durée sous laquelle 95 % des requêtes ont été servies).
Bibliothèque standard uniquement (Python 3.10 ou plus).
"""
import argparse
import csv
import lzma
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

RESULTATS = Path(__file__).resolve().parent / "resultats"
DEPLOIEMENTS = {"vm": "Trois machines virtuelles", "docker": "Trois conteneurs"}
COURT = {"vm": "3 VM", "docker": "3 conteneurs"}
CENTILES = (50, 90, 95, 99)
SEUIL_ERREURS = 1.0       # % : au-delà, le débit ne décrit plus le service rendu
SEUIL_CROISSANCE = 10.0   # % : un palier qui n'ajoute pas au moins 10 % de débit marque la saturation
SEUIL_REPETABILITE = 10.0 # % : écart maximal entre deux exécutions identiques

# Services de l'application, dans l'ordre des couches (les autres services systemd sont ignorés)
SERVICES = ["nginx", "api", "worker", "mysql", "redis", "elasticsearch", "kibana", "mailpit"]


# ---------- Lecture des fichiers ----------

def lire_configuration(dossier: Path, dep: str) -> dict[str, str]:
    config = {}
    fichier = dossier / f"{dep}-configuration.txt"
    if fichier.exists():
        for ligne in fichier.read_text(encoding="utf-8").splitlines():
            if "=" in ligne and not ligne.startswith("#"):
                cle, _, valeur = ligne.partition("=")
                config[cle.strip()] = valeur.strip()
    return config


def ouvrir(fichier: Path):
    """Fichier CSV brut, éventuellement compressé (.csv.xz : étalonnage, une ligne par requête à 40 000 req/s)."""
    if fichier.suffix == ".xz":
        return lzma.open(fichier, "rt", newline="", encoding="utf-8")
    return open(fichier, newline="", encoding="utf-8")


def paliers(dossier: Path, dep: str) -> list[tuple[int, Path]]:
    trouves = []
    for f in dossier.glob(f"{dep}-*.csv*"):
        m = re.fullmatch(rf"{dep}-(\d+)\.csv(\.xz)?", f.name)
        if m:
            trouves.append((int(m.group(1)), f))
    return sorted(trouves)


def centile(valeurs: list[float], p: float) -> float:
    if not valeurs:
        return math.nan
    return valeurs[max(0, math.ceil(p / 100 * len(valeurs)) - 1)]


def stats_requetes(lignes: list[dict]) -> dict:
    durees = sorted(int(l["elapsed"]) for l in lignes)
    erreurs = sum(1 for l in lignes if l["success"] != "true")
    return {
        "n": len(lignes),
        "erreurs": erreurs,
        "taux_erreur": 100 * erreurs / len(lignes) if lignes else math.nan,
        "moyenne": statistics.fmean(durees) if durees else math.nan,
        "max": durees[-1] if durees else math.nan,
        **{f"p{p}": centile(durees, p) for p in CENTILES},
    }


def analyser_palier(fichier: Path, montee: float, plateau: float) -> dict:
    with ouvrir(fichier) as f:
        lignes = list(csv.DictReader(f))
    if not lignes:
        raise SystemExit(f"{fichier} est vide")
    t0 = min(int(l["timeStamp"]) for l in lignes)
    debut, fin = t0 + montee * 1000, t0 + (montee + plateau) * 1000
    fenetre = [l for l in lignes if debut <= int(l["timeStamp"]) < fin]
    par_requete = defaultdict(list)
    for l in fenetre:
        par_requete[l["label"]].append(l)
    reussies = [l for l in fenetre if l["success"] == "true"]
    derniere = sorted(par_requete)[-1] if par_requete else None   # 2-Titres-likes : fin d'un parcours
    causes = Counter(f'{l["responseCode"]} {l["failureMessage"] or l["responseMessage"]}'.strip()
                     for l in fenetre if l["success"] != "true")
    return {
        "fenetre_ms": (debut, fin),
        "plateau": plateau,
        "utilisateurs": statistics.median(int(l["allThreads"]) for l in fenetre) if fenetre else 0,
        "debit": len(fenetre) / plateau,
        "debit_reussi": len(reussies) / plateau,
        "parcours": sum(1 for l in par_requete.get(derniere, []) if l["success"] == "true") / plateau,
        "global": stats_requetes(fenetre),
        "requetes": {label: stats_requetes(ls) for label, ls in sorted(par_requete.items())},
        "causes": causes.most_common(3),
    }


def service_logique(source: str, service: str) -> str | None:
    if source == "docker":
        m = re.fullmatch(r"musicapp-(.+)-\d+", service)
        nom = m.group(1) if m else service
        return "elasticsearch" if re.fullmatch(r"es\d+", nom) else nom
    if source == "hote":
        return service
    if service == "machine":
        return "machine"
    nom = re.sub(r"^musicapp-", "", service)
    nom = {"redis-server": "redis"}.get(nom, nom)
    nom = nom.split("@")[0]
    return nom if nom in SERVICES else None


def analyser_releves(fichier: Path, fenetre_ms: tuple[float, float]) -> dict:
    """(groupe, service) -> mesure -> valeur sur la fenêtre de mesure.
    Jauges : moyenne par instance, puis somme des instances (les 3 API) ; « _max » : maximum.
    Compteurs « _cumul » : débit (unité par seconde), somme des instances."""
    if not fichier.exists():
        return {}
    debut, fin = fenetre_ms
    series = defaultdict(list)   # (groupe, service, instance, mesure) -> [(t_ms, valeur)]
    with open(fichier, newline="", encoding="utf-8") as f:
        for l in csv.DictReader(f):
            try:
                t = int(l["horodatage_us"]) / 1000
                valeur = float(l["valeur"])
            except (KeyError, ValueError):
                continue
            service = service_logique(l["source"], l["service"])
            if service is None or (l["mesure"] == "cpu_pct" and valeur < 0):
                continue   # processeur négatif : service relancé pendant l'intervalle (compteur remis à zéro)
            groupe = "docker" if l["source"] == "docker" else l["source"]
            if l["mesure"] == "coeurs" or debut <= t <= fin:
                series[(groupe, service, l["service"], l["mesure"])].append((t, valeur))
    resultat = defaultdict(lambda: defaultdict(float))
    for (groupe, service, _instance, mesure), points in series.items():
        valeurs = [v for _, v in points]
        if mesure.endswith("_cumul"):
            if len(points) >= 2 and points[-1][0] > points[0][0]:
                duree = (points[-1][0] - points[0][0]) / 1000
                resultat[(groupe, service)][mesure.removesuffix("_cumul") + "_s"] += (valeurs[-1] - valeurs[0]) / duree
        elif mesure in ("coeurs", "connexions_max"):
            resultat[(groupe, service)][mesure] = max(valeurs)
        else:
            resultat[(groupe, service)][mesure] += statistics.fmean(valeurs)
            resultat[(groupe, service)][mesure + "_max"] = max(resultat[(groupe, service)][mesure + "_max"], max(valeurs))
    return resultat


def lire_evenements(fichier: Path) -> dict[str, str]:
    if not fichier.exists():
        return {}
    return dict(l.split("=", 1) for l in fichier.read_text(encoding="utf-8").splitlines() if "=" in l)


def analyser_deploiement(dossier: Path, dep: str) -> list[dict]:
    config = lire_configuration(dossier, dep)
    montee, plateau = float(config.get("montee", 30)), float(config.get("plateau", 90))
    lignes = []
    for n, fichier in paliers(dossier, dep):
        p = analyser_palier(fichier, montee, plateau)
        p["palier"] = n
        p["serveur"] = analyser_releves(dossier / f"{dep}-{n}-serveur.csv", p["fenetre_ms"])
        p["hote"] = analyser_releves(dossier / f"{dep}-{n}-hote.csv", p["fenetre_ms"])
        p["evenements"] = lire_evenements(dossier / f"{dep}-{n}-evenements.txt")
        lignes.append(p)
    return lignes


# ---------- Saturation ----------

def saturation(lignes: list[dict]) -> dict:
    """Débit maximal soutenu : le plus haut débit de requêtes réussies sur un palier à moins de 1 % d'erreurs.
    Point de saturation : le premier palier après lequel le débit cesse de croître (moins de 10 % de plus au
    palier suivant) alors que la latence au 95e centile, elle, augmente ; ou dès que les erreurs dépassent 1 %."""
    if not lignes:
        return {}
    sains = [p for p in lignes if p["global"]["taux_erreur"] <= SEUIL_ERREURS] or lignes[:1]
    meilleur = max(sains, key=lambda p: p["debit_reussi"])
    point = None
    for avant, apres in zip(lignes, lignes[1:]):
        croissance = 100 * (apres["debit_reussi"] / avant["debit_reussi"] - 1) if avant["debit_reussi"] else math.inf
        latence_monte = apres["global"]["p95"] > avant["global"]["p95"]
        if (croissance < SEUIL_CROISSANCE and latence_monte) or apres["global"]["taux_erreur"] > SEUIL_ERREURS:
            point = avant
            break
    return {"meilleur": meilleur, "point": point}


def indice_goulot(dep: str, p: dict) -> str:
    """Ressource la plus chargée au palier donné, rapportée à ce dont elle dispose : à confirmer sur les relevés."""
    candidats = []
    if dep == "vm":
        for (groupe, service), m in p["serveur"].items():
            if service == "machine" and m.get("coeurs"):
                candidats.append((m["cpu_pct"] / m["coeurs"], f"{groupe} : processeur à {m['cpu_pct'] / m['coeurs']:.0f} % "
                                  f"de ses {m['coeurs']:.0f} cœurs"))
    else:
        hote = p["hote"].get(("hote", "machine"), {})
        if hote.get("coeurs"):
            candidats.append((hote["cpu_pct"] / hote["coeurs"], f"hôte : processeur à {hote['cpu_pct'] / hote['coeurs']:.0f} % "
                              f"de ses {hote['coeurs']:.0f} cœurs"))
    if not candidats:
        return "relevés serveur absents"
    charge, texte = max(candidats)
    services = sorted(((m.get("cpu_pct", 0), s) for (g, s), m in p["serveur"].items() if s in SERVICES), reverse=True)
    detail = ", ".join(f"{s} {cpu:.0f} %" for cpu, s in services[:3] if cpu >= 1)
    return f"{texte}{' (' + detail + ' d’un cœur)' if detail else ''}"


# ---------- Mise en forme ----------

def ms(v: float) -> str:
    return "–" if math.isnan(v) else f"{v:.0f}"


def pct(v: float) -> str:
    return "–" if math.isnan(v) else f"{v:.1f} %"


def table(entetes: list[str], lignes: list[list[str]]) -> str:
    sortie = ["| " + " | ".join(entetes) + " |", "|" + "|".join("---:" if i else "---" for i in range(len(entetes))) + "|"]
    sortie += ["| " + " | ".join(l) + " |" for l in lignes]
    return "\n".join(sortie)


def tableau_client(lignes: list[dict]) -> str:
    labels = sorted({label for p in lignes for label in p["requetes"]})
    entetes = ["Utilisateurs", "Effectifs", "Débit (req/s)", "Réussies (req/s)", "Parcours/s",
               "Médiane (ms)", "p90 (ms)", "p95 (ms)", "p99 (ms)"]
    entetes += [f"p95 {label} (ms)" for label in labels] + [f"Erreurs {label}" for label in labels]
    corps = []
    for p in lignes:
        g = p["global"]
        corps.append([str(p["palier"]), f"{p['utilisateurs']:.0f}", f"{p['debit']:.1f}", f"{p['debit_reussi']:.1f}",
                      f"{p['parcours']:.1f}", ms(g["p50"]), ms(g["p90"]), ms(g["p95"]), ms(g["p99"])]
                     + [ms(p["requetes"].get(label, {}).get("p95", math.nan)) for label in labels]
                     + [pct(p["requetes"].get(label, {}).get("taux_erreur", math.nan)) for label in labels])
    return table(entetes, corps)


def tableau_serveur(dep: str, lignes: list[dict]) -> str:
    presents = sorted({s for p in lignes for (_, s) in p["serveur"] if s in SERVICES}, key=SERVICES.index)
    machines = sorted({g for p in lignes for (g, s) in p["serveur"] if s == "machine"})
    vues_hote = sorted({s for p in lignes for (_, s) in p["hote"] if s.startswith("vm-")})   # processus VBoxHeadless
    sortie = []

    entetes = (["Utilisateurs"] + presents + [f"{m} (total)" for m in machines]
               + [f"{v} vue de l'hôte" for v in vues_hote] + ["hôte (total)", "JMeter"])
    corps = []
    for p in lignes:
        par_service = defaultdict(float)
        for (g, s), m in p["serveur"].items():
            if s in SERVICES:
                par_service[s] += m.get("cpu_pct", 0)
        ligne = [str(p["palier"])] + [f"{par_service[s]:.0f}" for s in presents]
        for machine in machines:
            m = p["serveur"].get((machine, "machine"), {})
            ligne.append(f"{m['cpu_pct']:.0f} / {m['coeurs'] * 100:.0f}" if "cpu_pct" in m else "–")
        for v in vues_hote:
            m = p["hote"].get(("hote", v), {})
            ligne.append(f"{m['cpu_pct']:.0f}" if "cpu_pct" in m else "–")
        h, j = p["hote"].get(("hote", "machine"), {}), p["hote"].get(("hote", "jmeter"), {})
        ligne.append(f"{h['cpu_pct']:.0f} / {h['coeurs'] * 100:.0f}" if "cpu_pct" in h else "–")
        ligne.append(f"{j['cpu_pct']:.0f}" if "cpu_pct" in j else "–")
        corps.append(ligne)
    sortie.append("Processeur moyen sur la fenêtre de mesure, en % d'un cœur (200 = deux cœurs pleins) ; "
                  "« total » : utilisé / disponible ; « vue de l'hôte » : le processus de la VM dans WSL, "
                  "virtualisation comprise.\n\n" + table(entetes, corps))

    entetes = ["Utilisateurs"] + presents + [f"{m} (total)" for m in machines]
    corps = []
    for p in lignes:
        par_service = defaultdict(float)
        for (g, s), m in p["serveur"].items():
            if s in SERVICES:
                par_service[s] += m.get("mem_octets", 0)
        ligne = [str(p["palier"])] + [f"{par_service[s] / 2**20:.0f}" for s in presents]
        for machine in machines:
            m = p["serveur"].get((machine, "machine"), {})
            ligne.append(f"{m['mem_octets'] / 2**20:.0f}" if "mem_octets" in m else "–")
        corps.append(ligne)
    sortie.append("Mémoire moyenne, en Mo.\n\n" + table(entetes, corps))

    entetes = ["Utilisateurs", "Connexions MySQL (moy. / max)", "Requêtes SQL/s", "InnoDB lu (ko/s)",
               "InnoDB écrit (ko/s)", "Disque de la base, écrit (ko/s)", "Événements"]
    corps = []
    for p in lignes:
        bd = next((m for (g, s), m in p["serveur"].items() if s == "mysql" and "connexions" in m), {})
        disque = (p["serveur"].get(("vm-donnees", "machine"), {}) if dep == "vm"
                  else next((m for (g, s), m in p["serveur"].items() if s == "mysql" and "cpu_pct" in m), {}))
        evenements = ", ".join(f"{k} {v}" for k, v in p["evenements"].items() if v.strip() not in ("0", "")) or "aucun"
        corps.append([str(p["palier"]),
                      f"{bd['connexions']:.0f} / {bd['connexions_max']:.0f}" if "connexions" in bd else "–",
                      f"{bd['requetes_sql_s']:.0f}" if "requetes_sql_s" in bd else "–",
                      f"{bd['innodb_lu_octets_s'] / 1024:.0f}" if "innodb_lu_octets_s" in bd else "–",
                      f"{bd['innodb_ecrit_octets_s'] / 1024:.0f}" if "innodb_ecrit_octets_s" in bd else "–",
                      f"{disque['disque_ecrit_octets_s'] / 1024:.0f}" if "disque_ecrit_octets_s" in disque else "–",
                      evenements])
    sortie.append("Base de données et incidents (« connexions max » : record depuis le démarrage de MySQL).\n\n"
                  + table(entetes, corps))
    return "\n\n".join(sortie)


# ---------- Graphiques (SVG autonome, thème clair et sombre) ----------

COULEURS = {"vm": ("#2a78d6", "#3987e5"), "docker": ("#eb6834", "#d95926")}   # créneaux 1 et 2 de la palette


def graduations(maximum: float, nombre: int = 5) -> list[float]:
    if maximum <= 0:
        return [0, 1]
    brut = maximum / nombre
    puissance = 10 ** math.floor(math.log10(brut))
    pas = next(m * puissance for m in (1, 2, 2.5, 5, 10) if m * puissance >= brut)
    return [i * pas for i in range(math.ceil(maximum / pas - 1e-9) + 1)]


def nombre(v: float) -> str:
    return f"{v:.0f}" if v >= 10 or v == int(v) else f"{v:.1f}"


def graphique(fichier: Path, titre: str, sous_titre: str, unite: str, series: dict[str, list[tuple[float, float]]]) -> None:
    L, H, g, d, h, b = 680, 390, 64, 132, 88, 48
    xs = [x for pts in series.values() for x, _ in pts]
    ys = [y for pts in series.values() for _, y in pts if not math.isnan(y)]
    gx, gy = graduations(max(xs, default=1)), graduations(max(ys, default=1))
    X = lambda x: g + (L - g - d) * x / gx[-1]
    Y = lambda y: H - b - (H - h - b) * y / gy[-1]
    styles = ["--surface:#fcfcfb;--texte:#0b0b0b;--texte2:#52514e;--discret:#898781;--grille:#e1e0d9;--axe:#c3c2b7;"]
    sombre = ["--surface:#1a1a19;--texte:#f0efec;--texte2:#c3c2b7;--discret:#898781;--grille:#2c2c2a;--axe:#383835;"]
    for dep, (clair, fonce) in COULEURS.items():
        styles.append(f"--{dep}:{clair};")
        sombre.append(f"--{dep}:{fonce};")
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {L} {H}" width="{L}" height="{H}" role="img" '
         f'aria-label="{titre}">',
         f"<style>svg{{{''.join(styles)}font-family:system-ui,-apple-system,'Segoe UI',sans-serif}}"
         f"@media (prefers-color-scheme:dark){{svg{{{''.join(sombre)}}}}}"
         ".t{fill:var(--texte)}.t2{fill:var(--texte2)}.m{fill:var(--discret);font-variant-numeric:tabular-nums}</style>",
         f'<rect width="{L}" height="{H}" fill="var(--surface)"/>',
         f'<text x="{g}" y="28" class="t" font-size="16" font-weight="600">{titre}</text>',
         f'<text x="{g}" y="48" class="t2" font-size="12">{sous_titre}</text>']
    for v in gy:
        s.append(f'<line x1="{g}" x2="{L - d}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="var(--grille)" stroke-width="1"/>')
        s.append(f'<text x="{g - 8}" y="{Y(v) + 4:.1f}" class="m" font-size="11" text-anchor="end">{nombre(v)}</text>')
    s.append(f'<line x1="{g}" x2="{L - d}" y1="{Y(0):.1f}" y2="{Y(0):.1f}" stroke="var(--axe)" stroke-width="1"/>')
    for v in gx:
        s.append(f'<text x="{X(v):.1f}" y="{H - b + 18}" class="m" font-size="11" text-anchor="middle">{nombre(v)}</text>')
    s.append(f'<text x="{(g + L - d) / 2}" y="{H - 8}" class="t2" font-size="12" text-anchor="middle">'
             f'utilisateurs simultanés</text>')
    s.append(f'<text x="14" y="{(h + H - b) / 2}" class="t2" font-size="12" text-anchor="middle" '
             f'transform="rotate(-90 14 {(h + H - b) / 2})">{unite}</text>')
    # Légende (dès deux séries ; une seule est nommée par l'étiquette de fin) puis courbes, marqueurs, étiquettes
    for i, dep in enumerate(series if len(series) > 1 else []):
        lx = g + i * 150
        s.append(f'<line x1="{lx}" x2="{lx + 18}" y1="68" y2="68" stroke="var(--{dep})" stroke-width="2" stroke-linecap="round"/>')
        s.append(f'<text x="{lx + 24}" y="72" class="t2" font-size="12">{COURT[dep]}</text>')
    fins = []
    for dep, pts in series.items():
        pts = [(x, y) for x, y in pts if not math.isnan(y)]
        if not pts:
            continue
        chemin = " ".join(f"{'M' if i == 0 else 'L'}{X(x):.1f},{Y(y):.1f}" for i, (x, y) in enumerate(pts))
        s.append(f'<path d="{chemin}" fill="none" stroke="var(--{dep})" stroke-width="2" '
                 f'stroke-linejoin="round" stroke-linecap="round"/>')
        for x, y in pts:
            s.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="4" fill="var(--{dep})" stroke="var(--surface)" '
                     f'stroke-width="2"><title>{COURT[dep]} — {x:.0f} utilisateurs : {nombre(y)} {unite}</title></circle>')
        fins.append([Y(pts[-1][1]), pts[-1], dep])
    fins.sort()
    for i in range(1, len(fins)):   # étiquettes de fin : écartées d'au moins 16 px, reliées à leur point
        fins[i][0] = max(fins[i][0], fins[i - 1][0] + 16)
    for y_etiquette, (x, y), dep in fins:
        s.append(f'<line x1="{X(x) + 6:.1f}" x2="{L - d + 10}" y1="{Y(y):.1f}" y2="{y_etiquette:.1f}" '
                 f'stroke="var(--axe)" stroke-width="1"/>')
        s.append(f'<text x="{L - d + 14}" y="{y_etiquette + 4:.1f}" class="t" font-size="12">'
                 f'{COURT[dep]} : {nombre(y)}</text>')
    s.append("</svg>")
    fichier.write_text("\n".join(s) + "\n", encoding="utf-8")


# ---------- Commandes ----------

def rapport(serie: str) -> None:
    dossier = RESULTATS / serie
    if not dossier.is_dir():
        raise SystemExit(f"Série introuvable : {dossier}")
    analyses = {dep: analyser_deploiement(dossier, dep) for dep in DEPLOIEMENTS}
    analyses = {dep: lignes for dep, lignes in analyses.items() if lignes}
    if not analyses:
        raise SystemExit(f"Aucun fichier de résultats (vm-<N>.csv ou docker-<N>.csv) dans {dossier}")

    md = [f"# Série « {serie} » : synthèse", "",
          "Généré par `python3 charge/analyser.py rapport " + serie + "` à partir des fichiers bruts de ce dossier. "
          "Chaque chiffre ne porte que sur la fenêtre de mesure de son palier (montée exclue).", ""]
    resume = []
    for dep, lignes in analyses.items():
        config = lire_configuration(dossier, dep)
        sat = saturation(lignes)
        md += [f"## {DEPLOIEMENTS[dep]} ({dep})", "",
               f"Configuration : `{dep}-configuration.txt` — cible {config.get('cible', '?')}, montée {config.get('montee', '?')} s, "
               f"plateau {config.get('plateau', '?')} s, commit {config.get('commit', '?')}.", "",
               "### Côté client", "", tableau_client(lignes), ""]
        causes = [(p["palier"], c) for p in lignes for c in p["causes"]]
        if causes:
            md += ["Principales causes d'erreur :", ""]
            md += [f"- {n} utilisateurs : {texte} ({nb})" for n, (texte, nb) in causes]
            md.append("")
        md += ["### Côté serveur", "", tableau_serveur(dep, lignes), ""]
        meilleur, point = sat["meilleur"], sat["point"]
        md += ["### Saturation", "",
               f"- Débit maximal soutenu (moins de {SEUIL_ERREURS:.0f} % d'erreurs) : **{meilleur['debit_reussi']:.1f} req/s** "
               f"à {meilleur['palier']} utilisateurs (p95 {ms(meilleur['global']['p95'])} ms).",
               f"- Point de saturation : **{point['palier']} utilisateurs**." if point else
               "- Point de saturation : **non atteint** — le débit croît encore au dernier palier : ajouter des paliers "
               "(PALIERS=\"… 300\"), pour les deux déploiements.",
               f"- Ressource la plus chargée à ce palier : {indice_goulot(dep, point or meilleur)} — à confirmer "
               "avec les relevés ci-dessus avant de nommer le goulot d'étranglement.", ""]
        resume.append((dep, lignes, sat))

    if len(analyses) == 2:
        md += synthese_comparee(analyses)
    for nom, titre, unite, cle in (
            ("debit.svg", "Débit de requêtes réussies", "req/s", lambda p: p["debit_reussi"]),
            ("latence-p95.svg", "Latence au 95e centile", "ms", lambda p: p["global"]["p95"]),
            ("erreurs.svg", "Taux d'erreur", "%", lambda p: p["global"]["taux_erreur"])):
        graphique(dossier / nom, titre, f"Série « {serie} », fenêtre de mesure de chaque palier",
                  unite, {dep: [(p["palier"], cle(p)) for p in lignes] for dep, lignes in analyses.items()})
    md += ["## Graphiques", "", "![Débit](debit.svg)", "", "![Latence au 95e centile](latence-p95.svg)", "",
           "![Taux d'erreur](erreurs.svg)", ""]
    (dossier / "synthese.md").write_text("\n".join(md), encoding="utf-8")
    with open(dossier / "synthese.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["deploiement", "utilisateurs", "effectifs", "debit_req_s", "debit_reussi_req_s", "parcours_s",
                    "p50_ms", "p90_ms", "p95_ms", "p99_ms", "taux_erreur_pct"])
        for dep, lignes, _ in resume:
            for p in lignes:
                g = p["global"]
                w.writerow([dep, p["palier"], p["utilisateurs"], f"{p['debit']:.2f}", f"{p['debit_reussi']:.2f}",
                            f"{p['parcours']:.2f}", g["p50"], g["p90"], g["p95"], g["p99"], f"{g['taux_erreur']:.2f}"])
    print(f"Synthèse : {dossier / 'synthese.md'}")
    for dep, lignes, sat in resume:
        point = sat["point"]
        print(f"  {DEPLOIEMENTS[dep]} : débit maximal soutenu {sat['meilleur']['debit_reussi']:.1f} req/s, "
              f"saturation {'à ' + str(point['palier']) + ' utilisateurs' if point else 'non atteinte'}")


def synthese_comparee(analyses: dict[str, list[dict]]) -> list[str]:
    sat = {dep: saturation(lignes) for dep, lignes in analyses.items()}
    communs = sorted(set.intersection(*({p["palier"] for p in l} for l in analyses.values())))
    par_palier = {dep: {p["palier"]: p for p in lignes} for dep, lignes in analyses.items()}
    # « À charge égale » : le plus haut palier commun où les deux déploiements rendent encore le service
    egal = max((n for n in communs if all(par_palier[d][n]["global"]["taux_erreur"] <= SEUIL_ERREURS for d in analyses)),
               default=None)
    ligne = lambda titre, f: f"| {titre} | {f('vm')} | {f('docker')} |"
    md = ["## Tableau de synthèse", "",
          "| Grandeur | Trois machines virtuelles | Trois conteneurs |", "|---|---|---|",
          ligne("Débit maximal soutenu", lambda d: f"{sat[d]['meilleur']['debit_reussi']:.1f} req/s "
                f"({sat[d]['meilleur']['palier']} utilisateurs)"),
          ligne("Charge au point de saturation", lambda d: f"{sat[d]['point']['palier']} utilisateurs" if sat[d]["point"]
                else "non atteinte"),
          ligne(f"Latence au 95e centile, à charge égale ({egal} utilisateurs)" if egal else "Latence au 95e centile, à charge égale",
                lambda d: f"{ms(par_palier[d][egal]['global']['p95'])} ms" if egal else "–"),
          ligne("Goulot d'étranglement identifié", lambda d: "à nommer (indice : "
                + indice_goulot(d, sat[d]["point"] or sat[d]["meilleur"]) + ")"),
          ligne("Temps de démarrage complet", lambda d: repos(d, "demarrage_median_s", "s")),
          ligne("Mémoire consommée au repos", lambda d: repos(d, "memoire_repos_mediane_mo", "Mo")),
          "", "Latence au 95e centile à chaque palier commun :", "",
          table(["Utilisateurs", "3 VM (ms)", "3 conteneurs (ms)", "Conteneurs par rapport aux VM"],
                [[str(n), ms(par_palier["vm"][n]["global"]["p95"]), ms(par_palier["docker"][n]["global"]["p95"]),
                  ecart(par_palier["vm"][n]["global"]["p95"], par_palier["docker"][n]["global"]["p95"])] for n in communs]),
          ""]
    return md


def repos(dep: str, cle: str, unite: str) -> str:
    """Relevé de charge/repos.sh (médiane de trois exécutions), sinon renvoi à l'étape d'origine."""
    valeurs = lire_evenements(RESULTATS / "repos" / f"{dep}.txt")
    if cle in valeurs:
        return f"{valeurs[cle]} {unite} (charge/resultats/repos/{dep}.txt)"
    return "étape 10" if dep == "vm" else "étape 14"


def ecart(a: float, b: float) -> str:
    if not a or math.isnan(a) or math.isnan(b):
        return "–"
    return f"{100 * (b - a) / a:+.0f} %"


def comparer(serie_a: str, serie_b: str) -> None:
    md = [f"# Répétabilité : « {serie_a} » contre « {serie_b} »", "",
          f"Deux exécutions identiques doivent différer de moins de {SEUIL_REPETABILITE:.0f} % ; au-delà, c'est le bruit "
          "du poste qui est mesuré, pas le déploiement.", ""]
    hors_tolerance = 0
    for dep in DEPLOIEMENTS:
        a = {p["palier"]: p for p in analyser_deploiement(RESULTATS / serie_a, dep)}
        b = {p["palier"]: p for p in analyser_deploiement(RESULTATS / serie_b, dep)}
        communs = sorted(set(a) & set(b))
        if not communs:
            continue
        corps = []
        for n in communs:
            ed = 100 * (b[n]["debit_reussi"] - a[n]["debit_reussi"]) / a[n]["debit_reussi"] if a[n]["debit_reussi"] else math.nan
            el = 100 * (b[n]["global"]["p95"] - a[n]["global"]["p95"]) / a[n]["global"]["p95"] if a[n]["global"]["p95"] else math.nan
            hors = abs(ed) > SEUIL_REPETABILITE or abs(el) > SEUIL_REPETABILITE
            hors_tolerance += hors
            corps.append([str(n), f"{a[n]['debit_reussi']:.1f}", f"{b[n]['debit_reussi']:.1f}", f"{ed:+.1f} %",
                          ms(a[n]["global"]["p95"]), ms(b[n]["global"]["p95"]), f"{el:+.1f} %", "**hors tolérance**" if hors else "ok"])
        md += [f"## {DEPLOIEMENTS[dep]}", "",
               table(["Utilisateurs", f"Débit {serie_a}", f"Débit {serie_b}", "Écart débit",
                      f"p95 {serie_a} (ms)", f"p95 {serie_b} (ms)", "Écart p95", "Verdict"], corps), ""]
    fichier = RESULTATS / f"repetabilite-{serie_a}-{serie_b}.md"
    fichier.write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    print(f"\nÉcrit dans {fichier}")
    if hors_tolerance:
        print(f"ATTENTION : {hors_tolerance} palier(s) hors tolérance : stabiliser le poste puis recommencer.")


def resume_palier(fichier: Path, montee: float, plateau: float) -> None:
    p = analyser_palier(fichier, montee, plateau)
    g = p["global"]
    print(f"    {p['utilisateurs']:.0f} utilisateurs : {p['debit_reussi']:.1f} req/s réussies, "
          f"médiane {ms(g['p50'])} ms, p95 {ms(g['p95'])} ms, erreurs {pct(g['taux_erreur'])}"
          + (f" ({p['causes'][0][0]})" if p["causes"] else ""))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sous = parser.add_subparsers(dest="commande", required=True)
    sous.add_parser("rapport").add_argument("serie")
    c = sous.add_parser("comparer")
    c.add_argument("serie_a")
    c.add_argument("serie_b")
    p = sous.add_parser("palier")
    p.add_argument("fichier", type=Path)
    p.add_argument("--montee", type=float, default=30)
    p.add_argument("--plateau", type=float, default=90)
    args = parser.parse_args()
    if args.commande == "rapport":
        rapport(args.serie)
    elif args.commande == "comparer":
        comparer(args.serie_a, args.serie_b)
    else:
        resume_palier(args.fichier, args.montee, args.plateau)


if __name__ == "__main__":
    sys.exit(main())
