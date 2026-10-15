# Statische Pruefung der Slicing-Ressourcen

Status: lesende Cura-Definitionspruefung implementiert, echte Paketkandidaten
privat untersucht. Noch keine automatische Installation oder Slicing-Freigabe.

## Implementierter Vertrag

cura_definitions.py prueft die beiden flachen Verzeichnisse definitions/ und
extruders/ unter einer Ressourcenwurzel. Es liest ausschliesslich Daten.
Ausdruecke in settings/overrides, G-Code, Plugins und Engines werden nie
ausgewertet oder gestartet.

Geprueft werden regulaere, unverlinkte Dateien mit exakt .def.json als Endung,
eindeutige IDs, JSON ohne doppelte Schluessel oder nichtendliche Zahlen, Schema
als Ganzzahl 2, Metadatentypen, gueltige Eltern-/Extruderreferenzen und passende
Wurzeln. Zyklen, fehlende Referenzen, falsche Drucker-/Extruderwurzeln und
unsichere Pfade scheitern. fdmextruder ist die gueltige Basisausnahme: Sie liegt
unter definitions/ und kann als Standardextruder referenziert werden.

Grenzen: 4096 Dateien, 2 MiB je Datei, 32 MiB insgesamt und 64 Knoten je
Vererbungskette. Root, beide Unterordner und Dateien duerfen keine Symlinks
oder Junctions sein. Der Aufrufer muss den privaten Staging-Baum waehrend der
Pruefung gegen parallele Aenderungen schuetzen. Vor Aktivierung sind die
zurueckgegebenen Datei-SHAs erneut gegen das vertrauenswuerdige Paketmanifest
zu pruefen. Der Checker ersetzt keinen transaktionalen Installer.

Das Ergebnis ist unveraenderlich und enthaelt Pfad, Groesse, SHA, Eltern-ID
und deklarierte Extruderreferenzen. dependencies(printer) liefert eine
konservative Dateimenge einschliesslich Referenzen entlang der Elternketten.
Es berechnet keine wirksamen Cura-Einstellungswerte und emuliert keine
GUI-Metadatenzusammenfuehrung.

Beispiel einer rein lesenden Entwicklerpruefung:

    python Slicer-Server/cura_definitions.py /path/to/resources --printer 101Hero

Das Beispiel startet keinen Slice und trifft keine Aussage zur Eignung eines
Druckers, Materials, Start-/End-G-Codes oder einer tatsaechlichen Konfiguration.

## Echte Paketkandidaten

Am 11.10.2026 wurden diese Archive privat zuerst auf dem PC, danach auf dem
HA-Host per HTTPS ohne Redirects geladen und gegen feste Groessen/SHA geprueft.
Die Metadaten stammen aus dem lokalen Debian-Paketindex. Die offiziellen
Debian-Paketseiten bestaetigen Paketversion und fuer Cura die Bindung an
CuraEngine >= 5.0 und < 5.1. Eine gesonderte vollstaendige
Quell-/Signatur-/Lizenzabnahme ist damit noch nicht erledigt.

| Paket | Groesse | SHA-256 |
| --- | ---: | --- |
| cura 5.0.0-6, all | 26807776 Bytes | ac3650ec34a5a5023a33775b6b8ac9e9ee27aa783550fededa6db171e523cc99 |
| prusa-slicer 2.9.2+dfsg-1, amd64 | 41263096 Bytes | 4ff3972a868621f48adee0e1d6848ce27ada765a2fdc1d0cb87e81026f6c5392 |

Herkunft:
- https://deb.debian.org/debian/pool/main/c/cura/cura_5.0.0-6_all.deb
- https://deb.debian.org/debian/pool/main/s/slic3r-prusa/prusa-slicer_2.9.2+dfsg-1_amd64.deb
- https://packages.debian.org/trixie/cura
- https://packages.debian.org/trixie/prusa-slicer

Es wurde kein Debianpaket installiert. Ein privater, begrenzter Archivleser
hashte die regulaeren Dateien; nur Cura-Definitionen wurden als Daten in einen
neuen Pruefbaum kopiert. Keine Desktopprogramme, Launcher oder GUI wurden
eingerichtet. Die Archive und privaten Vollinventare gehoeren nicht in das
oeffentliche Produktrepository.

Cura: 6541 regulaere Dateien im Originalarchiv; davon 482 Eintraege in
definitions/ und 407 in extruders/. Die weiteren Qualitaets-, Material-,
Varianten- und Intentdaten sind dadurch noch nicht validiert.

Prusa: 1122 regulaere Dateien, 37 INI-Dateien. Das CLI-Binary hat SHA
7beaf8cc8861dcb97803da73222bdee358992e02c13a8e2b6212ae4809c121d2
und entspricht dem bisherigen Bibliothekskandidaten. OCCTWrapper.so hat SHA
f69d7bcb154189a1023314fbb28961553651c987b2cc62e275e9ad29df804bc9.
Das Vorhandensein des Moduls belegt noch keinen funktionierenden dlopen-Pfad
im neuen Engineverzeichnis. Lizenzdateien wurden inventarisiert; Lizenz-
und Ressourcenpruefung bleiben eigene Abnahmen.

## Befund am unveraenderten Cura-Paket

Der vollstaendige Originalbestand besteht unsere strenge Pruefung nicht:
- Fuenf Dateien enthalten doppelte JSON-Schluessel: SV02, hms434, tronxy_x,
  uni_base und zav_base. Bei drei Dateien sind Werte widerspruechlich,
  beispielsweise Temperatur, Beschleunigungs-/Jerk- oder Retraktionswerte.
- Drei Tizyx-Extruderdateien enden auf .def.JSON. Das entspricht unter Linux
  nicht dem exakten .def.json-Vertrag; zwei Druckerdefinitionen referenzieren
  diese Dateien.

Die Pruefung wurde nicht gelockert, kein letzter Wert stillschweigend als
richtig ausgewaehlt und kein Herstellerdokument umgeschrieben. In einem
separaten privaten Kandidaten wurden die fuenf mehrdeutigen Definitionen,
die zwei betroffenen Tizyx-Drucker und alle abhaengigen Definitionen
ausgeschlossen: insgesamt 25 Definitionsdateien plus drei nichtkanonische
Extruderdateien. Die Originale und fehlgeschlagenen Pruefstaende sind erhalten.

Der Kandidat umfasst 861 bytegetreu erhaltene Dateien: 457 unter definitions/,
404 unter extruders/, 859 Elternverweise und 430 Extruderreferenzen.
Gesamtgroesse 1880577 Bytes. Die Abhaengigkeitspruefung besteht auf Windows
und Linux. Dies ist eine eingeschraenkte, noch nicht freigegebene Auswahl;
ausgeschlossene Drucker duerfen spaeter nicht als unterstuetzt angeboten werden.
Korrekturen oder Ersatzprofile benoetigen eine eigene nachvollziehbare Abnahme.

Die Datei-/Archiv-/Kurationsmanifeste sind in kanonischer JSON-Darstellung
zwischen PC und HA identisch. Windows-/Linux-Zeilenenden der ersten privaten
Berichte unterschieden sich; die Nutzdaten waren identisch. Die Originalberichte
bleiben erhalten, normalisierte Nachweise sind separat gespeichert.

## Tests und offene Arbeit

Gezielt: 60 PC-Tests und 100 Subtests bestanden, drei Windows-Symlink-Skips.
Linux: alle 35 neuen Pruefungen einschliesslich Symlinks bestanden.
Die echte Datenpruefung umfasst die Sperre des Originalbestands und die
vollstaendige Abhaengigkeitspruefung der getrennten Auswahl. Sie startet
keine echte Engine. Gesamtgate, finale Quell-SHAs und Rueckwege stehen im
privaten Blockcheckpoint.

Weiter offen: komplette Profile/Materialien/Varianten, Prusa-Ressourcen- und
Pluginpfade, Bambu-Paketkuratierung, verifizierte Quellrevisionen, Lizenzen,
SBOM, reproduzierbare headless Paketsaetze, begrenzter Download/Extraktion,
persistenter Speicher und transaktionale Aktivierung. Danach HA-Assistent
und autorisierte Neuinstallations-/Slicing-/Restore-Abnahmen.

Der ausgelieferte engine_catalog.json bleibt fuer alle drei Familien pending.
Runtimeimage und native Installation werden durch diesen Schritt nicht
veraendert; container_deploy_ready=false bleibt.
