# Betrieb, Updates und Wiederherstellung

## Geltungsbereich

Dieser Betriebsvertrag beschreibt die Anforderungen an die Betriebsfreigabe.
Der [Docker-Dienstkandidat](RUNTIME_INSTALLATION.md) startet bereits API,
Worker und Telemetrie mit expliziten Daten-Mounts. Sein Standardbefehl bleibt
der Quell-Preflight. Engine und produktive Bestandsmigration sind noch offen.

## Persistente Daten

| Bereich | Inhalt | Vorgesehener Zugriff |
|---|---|---|
| Programm/Image | API, Worker, Hilfscode | Nur lesbar |
| Engine | Gepruefte Binaerdateien und zugehoerige Ressourcen | Nur lesbar |
| Konfiguration | API-Secret, Adresse, TLS-Schluessel | Eingeschraenkte Dateirechte |
| Profile | Eigene Drucker-/Material-/Prozessoptionen | Kontrolliert beschreibbar |
| Jobs und Ergebnisse | Modelle, Jobstatus, G-Code, Historie | Beschreibbar, separat sichern |
| Temporaere Dateien | Laufzeitlocks und Zwischendateien | Lebenszyklus genau festlegen |

Secrets stehen weder im Image noch in oeffentlichen Compose-Dateien. Logs und
Diagnoseexporte duerfen keine Authentifizierungsheader oder TLS-Schluessel
enthalten. Eine Datensicherung kann private Modelle und Secrets enthalten und
braucht entsprechende Zugriffsrechte.

## Vor einem Update

1. Aktuelles Image samt Digest, Metadaten und Konfiguration erfassen.
2. Neuen Auftragseingang kontrolliert anhalten und aktive Jobs beenden lassen.
3. Auch freigegebene wartende Auftraege inventarisieren; ein Neustart darf sie
   nicht unbemerkt in einem anderen Laufzeitstand ausfuehren.
4. Persistente Daten konsistent sichern und die Sicherung zuruecklesen.
5. Releasehinweise auf API-, Profil- und Datenschemaaenderungen pruefen.
6. Vorheriges Image und die dazu passende Datensicherung erreichbar halten.

## Update und Rueckweg

Nur einen geprueften Image-Digest einsetzen. API und Worker muessen zum selben
freigegebenen Paketstand gehoeren. Nach dem Wechsel werden Prozesse, Health,
Authentifizierung, TLS, API-Kompatibilitaet, Profile und Bestandsjobs geprueft.
Ein erfolgreicher Containerstart allein ist keine Betriebsabnahme.

Bei Fehlern zuerst neue Auftraege verhindern, dann den Fehlerzustand sichern.
Anschliessend das passende alte Image und bei Bedarf die dazugehoerige
Datensicherung gemeinsam wiederherstellen. Ein alter Worker darf keine
unbekannten neuen Jobdaten blind verarbeiten.

## Abbruch und Wiederanlauf

Ein Cancel-Auftrag muss ueber die authentifizierte API laufen. Nur der
zugehoerige Supervisor beendet seine eigene Prozessgruppe. Teilweise erzeugte
Druckartefakte eines abgebrochenen Jobs duerfen nicht als fertiges Ergebnis
erscheinen. Nach Container- oder Hostausfall muessen verwaiste slicing-Zustaende
erkannt werden; kein automatisches Ueberschreiben oder erneutes Slicing.

Die [synthetische Container-Abnahme](CONTAINER_TESTING.md) belegt kontrollierten
SIGTERM-Abbruch, bereinigte Nachfahren und Teilartefakte sowie eine Sperre bei
verwaisten slicing-Markern. Produktive API-/Telemetrie-Steuerung, Anchor-Ausfall,
Crash/Restore und persistente Datenvolumes sind weiterhin nicht abgenommen.

## Diagnose

Fuer einen Fehlerbericht genuegen in der Regel Image-Digest, Softwareversion,
API-Protokoll, Architektur, Fehlercode und bereinigte Logauszuege. Rohdateien aus
Konfiguration, Uploads oder Backups nicht ungeprueft veroeffentlichen.

## Entfernen

Das Entfernen eines Containers darf Profile, Modelle und Auftragshistorie nicht
automatisch loeschen. Volumes werden nur durch eine bewusste eigene Loeschaktion
entfernt. Die spaetere Deinstallationsanleitung muss Containerentfernung und
Datenloeschung getrennt beschreiben.

## Frueher Startabbruch

Vor der Startfreigabe muss der Worker seine installierten Signalhandler ueber die
Bereitschaftsleitung bestaetigen. Stop vor Bereitschaft wird als Ablehnungstoken
uebertragen. Timeout oder Prozessende vor Bereitschaft bedeuten
Wiederherstellungsbedarf: keinen Folgejob starten, queued-Daten erhalten und den
kanonischen Jobzustand pruefen. Der synthetische Linux/amd64-Nachweis deckt diese
drei Startfehler ab, ersetzt aber keine produktive API-, Telemetrie-, Engine-,
Anchor-Ausfall- oder Restore-Abnahme.