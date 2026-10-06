# Ultimate Studio · Native Bereitstellung und Beta-Freigabe · 05.10.2026

## Tatsächlich behobener Paketierungsfehler

Der neue native Worker verwendet `job_control.py`. Das bisherige `deploy-native-slicer.sh` führte die Datei jedoch nicht in `RUNTIME_FILES` und verlangte zugleich deren bereits vorhandene Zielkopie über `DEPENDENCY-SHA256SUMS`. Die Datei fehlt nach dem gelesenen privaten Livezustand tatsächlich. Ein Erstdeployment des neuen Workers konnte deshalb mit dem bisherigen Skript nicht vollständig erfolgen.

Korrektur ausschließlich am kanonischen Deployskript: `job_control.py` ist jetzt im Installations-, Sicherungs- und Rückwegumfang. Die Supervisor-Datei wird vorab aus dem Quellpaket gegen den bestehenden Prüfsummeneintrag geprüft; alle übrigen zehn nativen Abhängigkeiten müssen weiterhin bereits im Ziel den geprüften Stand haben. Supervisor-Syntax, Manifestformat und doppelte Einträge werden geprüft. Eine reine Supervisoränderung löst ebenfalls den notwendigen Worker-Neustart aus. Alle Runtime-/Unit-Hashes und Abhängigkeiten werden vor einem Kandidatenneustart sowie nach den Healthprüfungen geprüft.

Es wurde kein neuer Nebenweg für die Bereitstellung eingeführt. Die bestehenden Schutzprüfungen für aktive/wartende Jobs und Dispatcher-Lock bleiben erhalten. Die Korrektur betrifft nicht die Abbruchlogik, den Slicer, die Druckdaten oder die Druckersteuerung.

## Tests und Grenzen

26 gezielte Tests führen das tatsächliche Deployskript gegen isolierte synthetische Zielwurzeln aus. Systemd, HTTP und gezielt fehlschlagende Dateikopien sind Testdoubles; niemals werden echte Hostdienste oder Drucker angesprochen. Am Original scheitern 17 Fälle, neun bestehen. Am Kandidaten bestehen alle 26 ohne Auslassung unter Linux/root. Geprüft sind unter anderem erste Installation, Update nur des Supervisors, fehlende/ungültige Dateien, fehlerhafte Manifeste, unverändert verbindliche Zielabhängigkeiten, atomarer Austausch, Hashabweichung, gescheiterter Neustart, Rückweg mit vorher vorhandener beziehungsweise fehlender Datei und aktive Jobs.

Vollständiges PC-Gate am 05.10.2026 um 22:59:29 CEST erfolgreich: 440 Frontendtests, 1.591 Python-/Worker-Tests und 15 Untertests bestanden; Source-Policy, TypeScript, Produktionsbuild, HA-Core-Build, Syntax, Imports und Komponentencompile erfolgreich. Unter Windows wurden 22 neue Linux/root-Bereitstellungsfälle und neun vorhandene Linux-Prozessgruppenfälle ausgelassen, insgesamt 31. Die 22 neuen Laufzeitfälle sind im separaten Linux-Ergebnis mit allen 26 enthalten. Die vier plattformunabhängigen neuen Prüfungen sind bereits in den 1.591 enthalten; Zahlen nicht additiv als neue Gesamtsumme ausgeben. Der Connector-Timeout wurde anhand der realen Abschlussdatei aufgelöst.

Dieser Nachweis ist keine produktive Installation, kein echter Dienstneustart und kein vollständiger System-Restore-Nachweis. Alle elf nativen Abhängigkeitsvorprüfungen passen bei der aktuellen reinen Leseprüfung: zehn vorhandene Zielabhängigkeiten sowie der Supervisor im neuen Quellpaket.

## Quellabgleich und Veröffentlichung

Deployskript und neue Testdatei sind auf PC und HA vollständig gleich und vor der bestehenden Dateiersetzung gesichert. Beide wurden unverändert auf den öffentlichen Arbeitsbranch übertragen. Commit: `36b234f3c34f7bf9964b2484f9eeeb8a53dd7c10`; Pull Request #1 bleibt Entwurf, `main` bleibt unverändert. Der zusätzliche Workflow hat ausschließlich `contents: read`, prüft die gepinnten Quelldateien und verlangt, dass alle 26 synthetischen Linuxfälle ohne Fehler oder Auslassung gelaufen sind. Öffentlicher Lauf `37373691825` war beim letzten Abruf in der Warteschlange; noch kein bestandener GitHub-Lauf aus diesem neuen Commit behauptet.

Hash Deployskript: `5fcb1f8eba35faf5897e21630aa23f42c9fe09ab1dcaa55ffe4905c7835e1697`.
Hash neue Tests: `3c743c46d9e8d795912eca8f0a4d9ebd9f3ba7abb3124c3a3af1ba5642b9cbad`.
Hash Originalskript: `f0c2e35cbec4a1190d518e0ba980887d93614ceae2ac20544c790c3623de5c2d`.

Erweiterter PC-/HA-Abgleich: 681 Dateien des deklarierten Textquell-/kanonischen Deployumfangs per SHA geprüft. Sieben weitere Abweichungen nachgezogen; Workflow separat gleich übernommen. 191 alte generierte `frontend/dist`-Dateien sind nicht kanonischer Auslieferungsumfang. Zwei alte generierte Binär-STLs werden ebenfalls nicht kopiert oder gelöscht, weil die bereits korrigierten Parserprüfungen die Daten unabhängig unter `tmp_path` erzeugen. Der erste breitere Textleseversuch traf auf eine dieser Binärdateien und wurde abgebrochen; erst die nachvollziehbar begrenzte Textquellprüfung ist vollständig bestätigt.

Der öffentliche Quellvergleich gegen den vorigen Commit `2dd2947...` ergab 150 abweichende Zielpfade mit insgesamt 2.640.882 Bytes einschließlich Dokumentation und gebautem JavaScript. Die hier neu veröffentlichten zwei Code-/Testpfade sind darin enthalten. Das ist noch kein vollständiger öffentlicher Abgleich. Vollständige Liste und Pfadzuordnung liegen privat in `public-remaining-diff.json` im Sicherungsverzeichnis; vor Fortsetzung gegen den neuen Branchkopf auffrischen.

## Zusätzlicher offener Freigabeblocker für einen Neuaufbau

Der bestehende öffentliche `scripts/rebuild-homeassist.sh` am Ausgangscommit `2dd2947...` ist kein freigegebener Installationsweg für morgen: Er kopiert auch die ausgeschlossene alte `printer_control_center`-Komponente, entfernt pauschal fast alle Inhalte des Slicerwurzelverzeichnisses außer `data`, `run` und `config.json`, installiert `prusa-slicer` und startet Dienste vor abschließender Prüfung. Vor einem echten Neuaufbau ist ein getrennt geprüfter, nicht destruktiver nativer Bambu-Installationsvertrag erforderlich. Dieses alte Skript wurde NICHT ausgeführt oder verändert.

## Verbindliche verbleibende Abnahmereihenfolge

1. GitHub-Lauf und Ergebnisartefakt der Paketierungskorrektur auslesen. Restlichen vollständigen Quellabgleich einschließlich Worker-Quelldateien und reproduzierbaren Builds abschließen; öffentliches Pfadlayout erhalten.
2. Vor produktiver Aktivierung Druck-/Slicezustand neu prüfen. Getrennte HA-/Frontend- und native Workerbereitstellung nach vollständigem Gate, Same-Day-Backup und verifiziertem Rückweg. Danach laufende Integration, APIs, ausgelieferte Hashes und Worker-Capabilities bestätigen.
3. Echte Materialvorschau einschließlich Mehrschichtfällen, 95-Prozent-Popup, mobile Navigation bis zum letzten Tab, Kamera ohne Aus-/Einblenden, Scroll/Touch, Profilwerte und Galerie-/CAD-Datensicherheit tatsächlich abnehmen. MakerWorld-401/Berechtigung und echter Import bleiben offen.
4. Namensmigration, privates Prüfdashboard, vollständiger Rückweg-/Wiederanlaufnachweis und sauberer Linux-Neuaufbauvertrag nachführen. Beta nicht allein wegen des Termins entfernen.

Die Firmen-VM bleibt heute unverändert. Am 06.10. gilt weiterhin: Firmen-WAF, vorhandenes Wildcard-Zertifikat lokal und HTTPS, eigener Keycloak/Realm mit dauerhaften Konten, erst danach ChatGPT-MCP-Verbindung und Studio. Private HA-VM und separate KI-VM nicht verwechseln.

## Nachweise und Fortsetzung

Sicherung auf PC und privater HA: `backups/20261005-native-deploy-supervisor`. Enthalten: vollständiges Original, exaktes reversibles Delta in `verification.json`, vollständige neue PC-Gatedatei auf HA, Quellvergleich und ergänzende Arbeitsstände. Rücknahme ausschließlich bei exakt passendem Nachherhash, danach Vorherhash prüfen; keine Folgeänderungen überschreiben.

Die stündliche Fortsetzung ist ab 05.10.2026 23:28 Europe/Berlin eingerichtet und läuft ohne Enddatum bis zu Taras Stopp, soweit die jeweiligen Werkzeuge verfügbar sind. Sie ersetzt keine pausenlose Sitzung. Keine produktiven Dateien ausgetauscht, kein echter Dienstneustart, kein Slice, keine Auftragsfreigabe und keine Druckeraktion in diesem Abschnitt.


### Abschlussnachtrag: GitHub-Lifecycle-Prüfung bestanden

Der öffentliche Job isolated-deployment-lifecycle im Lauf 37373691825 ist erfolgreich abgeschlossen. Das heruntergeladene Artefakt 11370564597 wurde unabhängig per SHA-256 9c366ead5c61b7ab9525ded21ed312ead5276e0f576288e33db537d10df24835 geprüft. JUnit bestätigt 26 Tests, null Fehler, null Auslassungen; commit.txt bindet das Ergebnis an 36b234f3c34f7bf9964b2484f9eeeb8a53dd7c10, source.sha256 bestätigt die beiden PC-/HA-Quellhashes. Dies sind dieselben 26 gezielten Fälle, kein zusätzlicher unabhängiger Gesamtbestand. Die vorherige Warteschlangenmeldung ist damit aufgelöst.

Produktive Aktivierung und vollständiger öffentlicher Abgleich bleiben offen. Beim sauberen Linux-Neuaufbau außerdem die öffentliche Aufteilung slicing-server/ und deployment/systemd/ in einen tatsächlich vollständigen nativen Installationskandidaten überführen; die synthetischen Lifecycle-Tests ersetzen diese Paketvollständigkeitsprüfung nicht.
