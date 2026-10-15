# Betriebsgröße und Engine-Bestand – Beobachtung vom 15.10.2026

Diese Bestandsaufnahme ist rein lesend. Sie beschreibt eine existierende
native Installation, nicht den Inhalt eines Git-Klons und nicht den Nachweis
einer neuen reproduzierbaren oder freigegebenen Engine-Auslieferung.

## Woraus die rund 10,45 GB bestehen

Gemessen wurden belegte Bytes mit `du -x -B1`; gerundete GB sind dezimal.

| Kategorie | Beobachtete belegte Bytes | Ca. GB | Gehört in Git? |
| --- | ---: | ---: | --- |
| Daten | 7.264.915.456 | 7,265 | Nein: installationsspezifische Modelle, Aufträge und Ergebnisse privat sichern |
| Laufverzeichnisse | 1.798.168.576 | 1,798 | Nein: Betriebszustand und temporäre Artefakte |
| Validierung | 602.972.160 | 0,603 | Nein: Ergebnisse einer konkreten Installation |
| Lokaler Engine-Ordner | 784.703.488 | 0,785 | Nicht als ungeprüfte Binärkopie in den Quellverlauf |
| Gesamter Slicer-Baum | 10.453.995.520 | 10,454 | Produktquellen, Abhängigkeiten und private Daten getrennt behandeln |

Weitere kleinere Ordner sowie Dateien direkt an der Betriebswurzel erklären
den Rest. Global installierte Systempakete und Bibliotheken liegen teilweise
außerhalb dieses Baums. Die Tabellenwerte sind keine vollständige System- oder
Backup-Größenbilanz und auch keine unkomprimierten Git-Quelldateigrößen.

## Beobachtete Engine-Artefakte

| Engine | Tatsächlich beobachtet | SHA-256 des beobachteten Artefakts |
| --- | --- | --- |
| Bambu Studio | AppImage, 227.047.928 Bytes, zusätzlich entpackter Programm-/Ressourcenbaum; exakt dem offiziellen Ubuntu-24.04-Asset 449304146 des Releases `v02.07.01.62` zugeordnet | `fa98b608532dfbbbb2b0931483aac41e57fb19c175a2cc7bd7d528d5e0fbb287` |
| CuraEngine | Debian-Paketversion `1:5.0.0-5`, Programm unter `/usr/bin/CuraEngine` | `fe5de064a0d405135c97d1c1e86c33028c6d5f55956f4dbc9168d406625b10d7` |
| PrusaSlicer | Debian-Paketversion `2.9.2+dfsg-1`, Programm unter `/usr/bin/prusa-slicer` | `7beaf8cc8861dcb97803da73222bdee358992e02c13a8e2b6212ae4809c121d2` |

Das beobachtete Betriebssystem meldet Debian GNU/Linux 13, trixie. Die Paket-
versionen sind lokale Beobachtungen, keine Empfehlung aktueller Releases.
Die Dateihashes identifizieren vorhandene Bytes. Fuer die Bambu-AppImage stimmen
SHA-256 und Groesse mit dem offiziellen GitHub-Release-Asset ueberein; dessen
annotierter Tag verweist auf Commit
`42d319c6692fa8e64790fddf0cdaafd2a4254bcc`, ist aber unsigniert. Alle 118
ausgewaehlten Profilquellen stimmen bytegleich mit dem entpackten
Ressourcenbaum ueberein. Das ersetzt keine unabhaengige Signatur,
reproduzierbare Binaerpruefung oder Distributionsberechtigung. Keine Engine
wurde für diese Inventur gestartet; es wurde kein Modell geslicet.

## Was für eine vollständige Engine-Auslieferung zusätzlich fehlt

1. Fuer Bambu Studio die nun identifizierte Release-/Commit-Zuordnung durch
   vollstaendige Notice-, korrespondierende Quell-, Signatur- oder
   gleichwertige Herkunfts- und Lizenznachweise schliessen; fuer die anderen
   Familien ihre jeweiligen unveraenderlichen Artefakte ebenso abschliessen.
2. Zielarchitektur, ELF-/ABI-/Bibliotheksumfang und dynamische Plugins prüfen.
3. Vollständige Maschinen-, Prozess-, Filament- und Ressourcenketten prüfen;
   bei Cura genügt das Engine-Binary ohne passende Definitionen nicht.
4. In den dokumentierten neuen Engine-Speicher transaktional bereitstellen,
   ohne den bestehenden nativen Engine-Ordner zu verschieben.
5. Unabhängigen echten Linux-/Engine-/Upgrade-/Restore-Nachweis erbringen.

Bis dahin bleibt `engine_catalog.json` mit leeren freigegebenen Releases
korrekt. Die nun verifizierte AppImage-Zuordnung ist kein Anlass, die offenen
Lizenz-, SBOM-, Laufzeit- und Freigabenachweise zu überspringen.

## Buildreferenz ohne Betriebsfreigabe

Der beobachtete Bambu-Bestand ist nun zusaetzlich an den Hersteller-CI-Lauf
`27620769802`, dessen unveraenderten `deps`-Tree und den daraus abgeleiteten
wxWidgets-Commit `a9d946902685b9946d8775f07d2a73a9b5bef394` gebunden.
Die maschinenlesbaren Einzelheiten stehen in
`BAMBU_BUILD_REFERENCE.json`. Wegen fehlender historischer Cachebytes,
abgelaufener Joblogs und unversionierter Runner-/Compiler-/apt-Werkzeuge ist
dies keine reproduzierte Herstellerbinaerdatei. Am beobachteten Live-Bestand
wurde nichts geaendert; keine Engine wurde gestartet.
