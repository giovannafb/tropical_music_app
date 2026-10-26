#!/usr/bin/env bash
# Installe l'injecteur sur l'hôte (Ubuntu / WSL), hors du projet et sans sudo :
# Java (Eclipse Temurin, JRE) et Apache JMeter, dans ~/.musicapp-charge. Archives vérifiées par leur empreinte.
#
#   bash charge/installer.sh
. "$(dirname "${BASH_SOURCE[0]}")/commun.sh"

case "$(uname -m)" in
  x86_64) ARCH=x64 ;;
  aarch64) ARCH=aarch64 ;;
  *) erreur "processeur non prévu : $(uname -m)" ;;
esac
mkdir -p "$OUTILS/cache"

etape "Java $JAVA_VERSION (Eclipse Temurin, JRE)"
if [ -x "$JAVA_DIR/bin/java" ]; then
  ok "déjà installé"
else
  # Métadonnées officielles d'Adoptium : lien de l'archive et son empreinte SHA-256
  read -r lien empreinte < <(curl -fsSL "https://api.adoptium.net/v3/assets/latest/$JAVA_VERSION/hotspot?architecture=$ARCH&image_type=jre&os=linux&vendor=eclipse" \
    | python3 -c 'import json, sys; p = json.load(sys.stdin)[0]["binary"]["package"]; print(p["link"], p["checksum"])')
  archive="$OUTILS/cache/$(basename "$lien")"
  [ -f "$archive" ] || curl -fL --retry 3 -o "$archive" "$lien"
  echo "$empreinte  $archive" | sha256sum -c --quiet - || { rm -f "$archive"; erreur "archive Java corrompue (supprimée, relancer)"; }
  tmp="$(mktemp -d "$OUTILS/java.XXXXXX")"
  tar -xzf "$archive" -C "$tmp"
  mv "$tmp"/* "$JAVA_DIR"
  rmdir "$tmp"
  ok "$("$JAVA_DIR/bin/java" -version 2>&1 | head -1)"
fi

etape "Apache JMeter $JMETER_VERSION"
if [ -x "$JMETER_HOME/bin/jmeter" ]; then
  ok "déjà installé"
else
  # Miroir rapide d'Apache (version courante), sinon les archives (lentes, mais toutes les versions).
  # L'empreinte vient toujours du site d'Apache.
  nom="apache-jmeter-$JMETER_VERSION.tgz"
  archive="$OUTILS/cache/$nom"
  if [ ! -f "$archive" ]; then
    curl -fL --retry 3 -o "$archive" "https://dlcdn.apache.org/jmeter/binaries/$nom" \
      || curl -fL --retry 3 -o "$archive" "https://archive.apache.org/dist/jmeter/binaries/$nom"
  fi
  empreinte="$(curl -fsSL "https://archive.apache.org/dist/jmeter/binaries/$nom.sha512" | awk '{print $1}')"
  echo "$empreinte  $archive" | sha512sum -c --quiet - || { rm -f "$archive"; erreur "archive JMeter corrompue (supprimée, relancer)"; }
  tar -xzf "$archive" -C "$OUTILS"
  ok "installé dans $JMETER_HOME"
fi

etape "Vérification"
version="$(cd "$OUTILS" && jmeter_cli --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+$' | head -1)"   # jmeter.log écrit dans $OUTILS
[ "$version" = "$JMETER_VERSION" ] || erreur "JMeter ne démarre pas (bash -x $JMETER_HOME/bin/jmeter --version)"
ok "JMeter $version avec $("$JAVA_DIR/bin/java" -version 2>&1 | head -1)"
ok "Étape suivante : bash charge/valider.sh docker (ou vm)"
info "Interface graphique, pour construire ou déboguer le plan uniquement :"
info "  JAVA_HOME=$JAVA_DIR $JMETER_HOME/bin/jmeter -t charge/plan/musicapp.jmx"
