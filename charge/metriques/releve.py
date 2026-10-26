"""Relevés pendant un palier : une ligne CSV « source,service,mesure,valeur » par mesure et par intervalle,
sur la sortie standard (l'horodatage est ajouté par l'hôte, charge/commun.sh : horodater).

Unités : cpu_pct en pourcentage d'un cœur (200 = deux cœurs pleins, comme « docker stats ») ;
mémoire et entrées-sorties en octets ; les mesures « _cumul » sont des compteurs, dont l'analyse prend l'écart.

    python3 releve.py hote --duree 125 --intervalle 5
        l'hôte (WSL) : processeur et mémoire totaux, JMeter, et chaque VM VirtualBox vue de l'hôte
    python3 releve.py docker --duree 125 --intervalle 5 --docker docker --compose avec-docker
        chaque conteneur (docker stats) et l'état de MySQL
    sudo python3 - systemd --machine vm-donnees --duree 125 --intervalle 5 < releve.py
        DANS une VM : la machine, chaque service systemd (cgroups) et l'état de MySQL s'il y tourne

Bibliothèque standard uniquement : le même fichier tourne sur l'hôte et dans les VM, sans rien installer.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

# État de MySQL : connexions ouvertes et entrées-sorties de la base, mêmes compteurs dans les deux déploiements
MYSQL_STATUS = {
    "Threads_connected": "connexions",
    "Threads_running": "connexions_actives",
    "Max_used_connections": "connexions_max",
    "Innodb_data_read": "innodb_lu_octets_cumul",
    "Innodb_data_written": "innodb_ecrit_octets_cumul",
    "Questions": "requetes_sql_cumul",
}
MYSQL_QUERY = "SHOW GLOBAL STATUS WHERE Variable_name IN ({})".format(
    ",".join(f"'{name}'" for name in MYSQL_STATUS))


def sortie(source: str, service: str, mesure: str, valeur) -> None:
    if isinstance(valeur, float):
        valeur = f"{valeur:.2f}"
    print(f"{source},{service},{mesure},{valeur}", flush=True)


def mysql_status(commande: list[str], cwd: str | None = None) -> dict[str, int]:
    try:
        texte = subprocess.run(commande, capture_output=True, text=True, timeout=10, cwd=cwd).stdout
    except (OSError, subprocess.TimeoutExpired):
        return {}
    valeurs = {}
    for ligne in texte.splitlines():
        nom, _, valeur = ligne.partition("\t")
        if nom in MYSQL_STATUS and valeur.strip().isdigit():
            valeurs[MYSQL_STATUS[nom]] = int(valeur)
    return valeurs


# ---------- Linux : /proc ----------

def cpu_total() -> tuple[float, float]:
    """(temps occupé, temps total) en secondes, tous cœurs confondus."""
    with open("/proc/stat") as f:
        champs = [int(v) for v in f.readline().split()[1:]]
    tick = os.sysconf("SC_CLK_TCK")
    inactif = champs[3] + champs[4]   # idle + iowait
    total = sum(champs[:8])           # sans guest (déjà compté dans user)
    return (total - inactif) / tick, total / tick


def iowait() -> float:
    with open("/proc/stat") as f:
        return int(f.readline().split()[5]) / os.sysconf("SC_CLK_TCK")


def memoire_utilisee() -> int:
    infos = {}
    with open("/proc/meminfo") as f:
        for ligne in f:
            cle, valeur = ligne.split(":", 1)
            infos[cle] = int(valeur.split()[0]) * 1024
    return infos["MemTotal"] - infos["MemAvailable"]


def disques() -> tuple[int, int]:
    """Octets lus et écrits depuis le démarrage, sur les disques physiques (sda, vda, nvme…)."""
    lus = ecrits = 0
    with open("/proc/diskstats") as f:
        for ligne in f:
            champs = ligne.split()
            if re.fullmatch(r"(sd[a-z]+|vd[a-z]+|xvd[a-z]+|nvme\d+n\d+)", champs[2]):
                lus += int(champs[5]) * 512
                ecrits += int(champs[9]) * 512
    return lus, ecrits


def processus_hote() -> dict[str, tuple[float, int]]:
    """JMeter et chaque VM VirtualBox : nom -> (temps CPU en s, mémoire résidente en octets)."""
    tick = os.sysconf("SC_CLK_TCK")
    page = os.sysconf("SC_PAGE_SIZE")
    trouves: dict[str, tuple[float, int]] = {}
    for pid in filter(str.isdigit, os.listdir("/proc")):
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                argv = f.read().decode(errors="replace").split("\0")
            if any(a.endswith("ApacheJMeter.jar") for a in argv):
                nom = "jmeter"
            elif os.path.basename(argv[0]) == "VBoxHeadless":
                # VBoxManage startvm lance « VBoxHeadless --comment vm-metier --startvm <uuid> … »
                option = "--comment" if "--comment" in argv else "--startvm"
                nom = argv[argv.index(option) + 1]
            else:
                continue
            with open(f"/proc/{pid}/stat") as f:
                champs = f.read().rsplit(")", 1)[1].split()
            cpu = (int(champs[11]) + int(champs[12])) / tick
            rss = int(champs[21]) * page
        except (OSError, IndexError, ValueError):
            continue
        avant = trouves.get(nom, (0.0, 0))
        trouves[nom] = (avant[0] + cpu, avant[1] + rss)
    return trouves


# ---------- Modes ----------

def mode_hote(args) -> None:
    coeurs = os.cpu_count() or 1
    sortie("hote", "machine", "coeurs", coeurs)
    precedent_cpu = cpu_total()
    precedents: dict[str, float] = {}
    fin = time.monotonic() + args.duree
    while time.monotonic() < fin:
        time.sleep(args.intervalle)
        occupe, total = cpu_total()
        delta = total - precedent_cpu[1]
        if delta > 0:
            sortie("hote", "machine", "cpu_pct", 100 * coeurs * (occupe - precedent_cpu[0]) / delta)
        precedent_cpu = (occupe, total)
        sortie("hote", "machine", "mem_octets", memoire_utilisee())
        for nom, (cpu, rss) in processus_hote().items():
            if nom in precedents:
                sortie("hote", nom, "cpu_pct", 100 * (cpu - precedents[nom]) / args.intervalle)
            precedents[nom] = cpu
            sortie("hote", nom, "mem_octets", rss)


UNITES = {"b": 1, "kb": 1e3, "mb": 1e6, "gb": 1e9, "tb": 1e12, "kib": 1024, "mib": 1024**2, "gib": 1024**3, "tib": 1024**4}


def octets(texte: str) -> int:
    m = re.fullmatch(r"\s*([\d.]+)\s*([a-zA-Z]*)\s*", texte)
    if not m:
        return 0
    return int(float(m.group(1)) * UNITES.get(m.group(2).lower() or "b", 1))


def mode_docker(args) -> None:
    mysql = [args.docker, "compose", "exec", "-T", "mysql", "sh", "-c",
             f'MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" -N -B -e "{MYSQL_QUERY}"']
    fin = time.monotonic() + args.duree
    while time.monotonic() < fin:
        debut = time.monotonic()
        # « docker stats » mesure lui-même le processeur sur un court intervalle (environ 1 s)
        texte = subprocess.run([args.docker, "stats", "--no-stream", "--format", "{{json .}}"],
                               capture_output=True, text=True, cwd=args.compose).stdout
        for ligne in texte.splitlines():
            try:
                stats = json.loads(ligne)
            except json.JSONDecodeError:
                continue
            nom = stats.get("Name", "")
            if not nom.startswith(f"{args.projet}-"):
                continue
            try:
                cpu = float(stats.get("CPUPerc", "").rstrip("%"))
            except ValueError:
                continue   # conteneur arrêté (« -- »)
            sortie("docker", nom, "cpu_pct", cpu)
            sortie("docker", nom, "mem_octets", octets(stats.get("MemUsage", "0B").split("/")[0]))
            lus, _, ecrits = stats.get("BlockIO", "0B / 0B").partition("/")
            sortie("docker", nom, "disque_lu_octets_cumul", octets(lus))
            sortie("docker", nom, "disque_ecrit_octets_cumul", octets(ecrits))
        for mesure, valeur in mysql_status(mysql, cwd=args.compose).items():
            sortie("docker", "mysql", mesure, valeur)
        time.sleep(max(0.0, args.intervalle - (time.monotonic() - debut)))


CGROUPS = "/sys/fs/cgroup/system.slice"


def lire_cgroup(dossier: str) -> tuple[float, int, int, int] | None:
    """(temps CPU en s, mémoire hors cache inactif, octets lus, octets écrits) d'un service systemd."""
    try:
        with open(f"{dossier}/cpu.stat") as f:
            cpu = next(int(l.split()[1]) for l in f if l.startswith("usage_usec")) / 1e6
    except (OSError, StopIteration):
        return None
    memoire = lus = ecrits = 0
    try:
        with open(f"{dossier}/memory.current") as f:
            memoire = int(f.read())
        with open(f"{dossier}/memory.stat") as f:
            inactif = next((int(l.split()[1]) for l in f if l.startswith("inactive_file ")), 0)
        memoire -= inactif   # même calcul que « docker stats »
    except (OSError, ValueError):
        pass
    try:
        with open(f"{dossier}/io.stat") as f:
            for ligne in f:
                for champ in ligne.split()[1:]:
                    cle, _, valeur = champ.partition("=")
                    if cle == "rbytes":
                        lus += int(valeur)
                    elif cle == "wbytes":
                        ecrits += int(valeur)
    except OSError:
        pass
    return cpu, memoire, lus, ecrits


def services_systemd() -> dict[str, str]:
    """Nom de l'unité -> dossier du cgroup, pour chaque service de system.slice (y compris musicapp-api@…)."""
    trouves = {}
    for racine, dossiers, _ in os.walk(CGROUPS):
        for d in dossiers:
            if d.endswith(".service"):
                trouves[d[: -len(".service")]] = os.path.join(racine, d)
    return trouves


def mode_systemd(args) -> None:
    m = args.machine
    coeurs = os.cpu_count() or 1
    sortie(m, "machine", "coeurs", coeurs)
    avec_mysql = shutil.which("mysql") is not None and os.path.isdir(f"{CGROUPS}/mysql.service")
    mysql = ["mysql", "-N", "-B", "-e", MYSQL_QUERY]   # root, par le socket local (auth_socket)
    precedent_cpu, precedent_wait = cpu_total(), iowait()
    precedents: dict[str, float] = {}
    fin = time.monotonic() + args.duree
    while time.monotonic() < fin:
        time.sleep(args.intervalle)
        occupe, total = cpu_total()
        attente = iowait()
        delta = total - precedent_cpu[1]
        if delta > 0:
            sortie(m, "machine", "cpu_pct", 100 * coeurs * (occupe - precedent_cpu[0]) / delta)
            sortie(m, "machine", "iowait_pct", 100 * coeurs * (attente - precedent_wait) / delta)
        precedent_cpu, precedent_wait = (occupe, total), attente
        sortie(m, "machine", "mem_octets", memoire_utilisee())
        lus, ecrits = disques()
        sortie(m, "machine", "disque_lu_octets_cumul", lus)
        sortie(m, "machine", "disque_ecrit_octets_cumul", ecrits)
        for nom, dossier in services_systemd().items():
            mesures = lire_cgroup(dossier)
            if mesures is None:
                continue
            cpu, memoire, lus, ecrits = mesures
            if nom in precedents and cpu >= precedents[nom]:   # sinon : service relancé, compteur remis à zéro
                sortie(m, nom, "cpu_pct", 100 * (cpu - precedents[nom]) / args.intervalle)
            precedents[nom] = cpu
            sortie(m, nom, "mem_octets", memoire)
            if lus or ecrits:
                sortie(m, nom, "disque_lu_octets_cumul", lus)
                sortie(m, nom, "disque_ecrit_octets_cumul", ecrits)
        if avec_mysql:
            for mesure, valeur in mysql_status(mysql).items():
                sortie(m, "mysql", mesure, valeur)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=["hote", "docker", "systemd"])
    parser.add_argument("--duree", type=float, required=True, help="durée du relevé (s)")
    parser.add_argument("--intervalle", type=float, default=5, help="période (s)")
    parser.add_argument("--machine", default="", help="systemd : nom de la VM")
    parser.add_argument("--docker", default="docker", help="docker : commande de la CLI (docker ou docker.exe)")
    parser.add_argument("--compose", default=".", help="docker : dossier du fichier de composition")
    parser.add_argument("--projet", default="musicapp", help="docker : nom du projet compose")
    args = parser.parse_args()
    try:
        {"hote": mode_hote, "docker": mode_docker, "systemd": mode_systemd}[args.mode](args)
    except (KeyboardInterrupt, BrokenPipeError):
        sys.exit(0)


if __name__ == "__main__":
    main()
