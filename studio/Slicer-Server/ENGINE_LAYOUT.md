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
