# Engine-Speicher im Docker-Kandidaten

Der lesende Pfadvertrag sowie der persistente Store-/Aktivierungsvertrag sind
implementiert. Echte Installation, Herkunfts- und Profilpruefung sind weiterhin
offen; `container_deploy_ready=false` bleibt.

## Feste Containerpfade

`SLICER_ENGINE` bezeichnet auf dem Docker-Host den gesamten Engine-Speicher.
Compose bindet ihn fuer API und Worker nur lesend nach `/engine` ein.

| Engine-ID | Programm im Container | Ressourcen |
| --- | --- | --- |
| bambu_studio | /engine/bambu_studio/bin/bambu-studio | /engine/bambu_studio/resources/profiles |
| prusaslicer | /engine/prusaslicer/bin/prusa-slicer | Vollstaendiger gepruefter Prusa-Ressourcenumfang, noch offen |
| curaengine | /engine/curaengine/bin/CuraEngine | Passende Definitionen/Vererbungen, noch offen |

Die bisherige Bambu-Extraktionswurzel direkt unter `/engine` ist nicht mehr
das Layout dieses Kandidaten. Bestehende native Engineverzeichnisse werden
nicht verschoben. Eine kuenftige Migration muss einen neuen Speicher aufbauen,
vorhandene Ressourcen pruefen und den Rueckweg erhalten.

## Gemeinsame Erkennung und Aufruf

`container_engines.py` prueft nur Dateien und startet keine Engine. Dispatcher
und Telemetrie verwenden denselben Vertrag. Erlaubt sind ausschliesslich die
drei festen Engine-IDs und die obigen Programme. Fehlende Dateien, Verzeichnisse
statt Programmen, fehlende Ausfuehrbarkeit sowie Symlinks/Junctions an Speicher,
Enginewurzel, bin-Verzeichnis oder Programm werden abgewiesen. Es gibt im
Container keinen Rueckfall auf PATH, /usr/bin oder eine andere Engine.

Die Telemetrie meldet nur akzeptierte Programme. `available=true` bedeutet
hier ausschliesslich vorhandener, ausfuehrbarer Programmeinstieg; es ist keine
Profil-, Herkunfts-, Plugin- oder Slicing-Abnahme. Ohne gepruefte Versionsmetadaten
lautet die Version `unknown`; es wird keine alte Version erfunden. Ein leerer
Speicher startet API/Worker weiterhin mit Zustand `degraded`.

Bambu-API und Worker verwenden dieselbe Ressourcenwurzel. Die nativen
Host-Standardpfade und ihre bisherige Isolation bleiben erhalten. Jeder
Container-Engineaufruf durchlaeuft weiterhin die unabhaengige Kernelpruefung.

## Vertrag fuer den kommenden Installer

- Nur der Installer darf den Engine-Speicher beschreiben; API/Worker erhalten
  ihn lesend. Keine Installation in das Daten-/Uploadverzeichnis.
- Engine-ID und Einstieg kommen aus einem kuratierten Katalog, nicht aus
  frei eingegebenen Befehlen oder einem heruntergeladenen Startskript.
- Herkunft, Digest, Lizenz, Plattform, Bibliotheken und Ressourcen pro Artefakt
  pruefen. Prusa kann weitere dynamisch geladene Module benoetigen; das
  CuraEngine-Paket allein liefert keine Druckerdefinitionen.
- Vor Austausch Worker anhalten und laufende Auftraege ausschliessen; eine
  freigegebene Generation samt Ressourcen vollstaendig bereitstellen.
  Kein Austausch einzelner Dateien unter einem laufenden Worker.
- Gepruefte alte Generation fuer Wiederherstellung behalten. Das konkrete
  [Transaktions-/Aktivierungsprotokoll](PACKAGE_ACTIVATION.md) ist implementiert;
  Compose-/HA-Anbindung und echte Upgrade-/Restore-Abnahme bleiben offen.
- Diese Pfadpruefung ersetzt weder Digestpruefung noch einen Schutz vor einem
  privilegierten Hostprozess, der einen lesenden Mount von aussen veraendert.

Die Einrichtung beginnt spaeter im [HA-Assistenten](HA_INSTALLATION_PLAN.md).
Der Pfadvertrag ist eine Grundlage dafuer, keine fertige Installation.


## Enginearchive an die festen Container-Ressourcenpfade gebunden

Die geprueften Debianquellen von PrusaSlicer 2.9.2 setzen Ressourcen auf
/usr/share/PrusaSlicer und das OCCT-Modul auf einen FHS-Libpfad. Der gepackte
Baum unter /engine/prusaslicer wird durch Verschieben des Programms allein
nicht automatisch gefunden. Die originale CLI-Setupquelle ist SHA256
20d84887cf8c26fb39464e53326efab3e103b3c6ce78987fed717984585ccc77;
der zugehoerige Debian-OCCT-Patch ist SHA256
16ee540e5de01db21e89b78696d8e8a24a7d18c122c1441a8a9398338aeabcb2.

container_engines.py erzeugt deshalb ausschliesslich beim expliziten Imagebau
zwoelf feste relative Pfadverbindungen: sieben Prusa-Ressourcenverzeichnisse,
Font-README, zwei Systemfont-Verweise, OCCTWrapper und Cura-Ressourcen.
Die Enginegeneration bleibt unveraendert read-only unter /engine. Keine
Programmdatei wird nach /usr/bin verlinkt; kein nativer Slicer wird installiert.
Vorhandene andere Dateien/Verzeichnisse/Links werden nie ersetzt. Wiederholte
Vorbereitung akzeptiert nur exakt passende Verbindungen. Import und normaler
Engine-Lookup erzeugen keine Pfade. Der Dockerfile baut und prueft diese
Verbindungen vor USER65532; keine Engine wird dabei ausgefuehrt.

Die beiden bisher fehlenden Prusa-Fontverweise werden im Image auf die
Debianpakete fonts-noto-core und fonts-noto-cjk gerichtet. Es werden keine
Schriftdateien vom privaten Host kopiert, in Quellarchive aufgenommen oder
angehaengt. Die real aufgeloesten Zielpakete bleiben durch das Bildinventar zu
belegen. Der SBOM-Referenzvertrag umfasst nun42 Pflichtpakete und ist an den
neuen Dockerfile-Hash gebunden, weiterhin keine Version-/Imagefreigabe.

CuraEngine 5.0.0 liest CURA_ENGINE_SEARCH_PATH (gepruefte Originalquelle
src/communication/CommandLine.cpp SHA256
f5729d67bfcd9a2db3e9bddfc7ad36250ecf52b7ff3109284354427895ac32a7).
Der Dockerfile setzt diesen Pfad fest auf die definitions-/extruders-Bereiche
der gewaelten Cura-Enginegeneration, ohne geerbten Suchpfad anzuhaengen.
Die bestehende kernelgepruefte Netzwerkisolation bleibt unveraendert.

Quelle, Imagebauvertrag, Dateisystemtests und Paketreferenz bilden einen
zusammenhaengenden Block. Eine erfolgreiche Linkpruefung ist KEIN Nachweis
eines gebauten Images, geladenen Plugins, vollstaendigen ABI oder Slices.
Drei urspruengliche Enginearchive und Hostkanalkandidat bleiben unveraendert;
Katalogfreigabe und Hostintegration werden dadurch nicht behauptet. Kein
Eine Paketprüfung startet keine Engine und verändert keinen laufenden Dienst.


## OpenCASCADE-Laufzeit für den Prusa-STEP-Import

Der mitgelieferte `OCCTWrapper.so` benötigt acht `libTK*.so.7.8`-Bibliotheken.
Eine vorhandene Wrapper-Datei oder ihre korrekte FHS-Verknüpfung allein genügt
nicht. Der Docker-Bau installiert deshalb ausdrücklich die sechs OCCT-7.8-
Paketfamilien Foundation, Modeling Data, Modeling Algorithms, Visualization,
OCAF und Data Exchange. Sie sind Bestandteil der erforderlichen SBOM-Paketliste.
Es wird kein zusätzlicher nativer PrusaSlicer und kein zweiter Slicer installiert.

Ein isoliertes Image mit diesen Paketen bestand die statische Prüfung der
Plugin-Abhängigkeiten und GNU-Symbolversionen. Das ist kein ausgeführter STEP-
Import, kein Slice und keine gesamte Runtime- oder Lizenzfreigabe. Versionen,
Quellen und Copyright-Hinweise der zusätzlichen transitiven Systempakete gehören
zur jeweiligen realen Image-Lieferung. Der Bambu-spezifische Bibliothekspfad
bleibt ausschließlich an dessen bestehenden Dispatcher-Aufrufen gesetzt; er
wird nicht global auf Prusa/Cura übertragen.
