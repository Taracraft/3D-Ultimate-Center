# Docker-Migration

## Entscheidung

Slicer-Server wird der eigene Bereich im vorhandenen Monorepo. Docker Compose
wird der regulaere Installationsweg fuer einen Linux-Host. Langfristiger
Release-Branch bleibt main. Bestehende Quellstaende werden verlustfrei
uebernommen; Home Assistant und Slicer bleiben getrennte Auslieferungsziele.

## Arbeitspakete und Abnahme

| Schritt | Ergebnis | Abnahme | Stand |
|---|---|---|---|
| 1. Paketgrenze | Expliziter Docker-Kontext, keine privaten Laufzeitdaten | SHA-Closure, negative Kontexttests | Implementiert, Quellpruefung |
| 2. Laufzeit entkoppeln | Zehn gemeinsame Hilfsdateien mit eindeutiger Quellautoritaet | Alle HA-/Worker-Verbraucher und Pakettests | Offen |
| 3. Containerbetrieb | API, Worker und Telemetrie ohne Host-systemd | Job-Abbruch, Neustart, keine verwaisten Prozesse | Dienstkandidat, TLS, Stop/Neustart, synthetischer Anchor-Ausfall und Restore geprueft |
| 4. Engine und Plattform | Vollstaendige Engine-/Profil-/Bibliotheksclosure | Herkunft, Lizenzen, Linux/amd64, echter freigegebener Slice | Offen |
| 5. Installation | Geprueftes Image und Betriebs-Compose | Frischer Host, TLS, HA-Verbindung, Rechte | Installerkern inkl. Erstinstallations-Rollback synthetisch integriert; HA-Flow und reale Abnahme offen |
| 6. Datenuebernahme | Bestehende Profile, Auftraege und Historie erhalten | Inventar, Idle-Zustand, Backup, Restore | Offen |
| 7. Dokumentation | README, Installation, Betrieb und GitHub-Wiki | Befehle gegen freigegebenes Image nachgestellt | In Arbeit |
| 8. Veroeffentlichung | Image, HACS und Repo mit nachvollziehbaren Releases | Lizenz-/Secretreview, CI, Pilot | Offen |
| 9. Git-Konsolidierung | Alle benoetigten Aenderungen in main | Commitvergleich und gesicherter Rueckweg | Danach |

## Laufzeitentwurf, noch keine Betriebsfreigabe

Die API braucht Netzwerkzugang fuer die authentifizierte Home-Assistant-
Verbindung. Der eigentliche Slicing-Prozess soll ohne ausgehenden Netzwerkzugang
laufen. Ein moegliches Compose-Layout trennt deshalb API und Worker und verbindet
sie nur ueber die bestehenden kontrollierten Jobdateien.

Die aktuelle Abbruchlogik verifiziert Prozessidentitaeten ueber /proc.
Getrennte PID-Namensraeume duerfen deshalb nicht ungeprueft eingefuehrt werden.
Zu pruefen sind ein kontrolliert gemeinsamer PID-Namensraum oder ein
angepasster, nachweisbarer Besitzervertrag. API-Anfragen duerfen weiterhin
keine beliebigen Prozess-IDs signalisieren.

Der aktuelle Dispatcher verwendet unshare. Docker-Standardprofile erlauben
nicht automatisch verschachtelte User-/Netzwerk-Namespaces. Ein pauschales
privileged, host networking oder das Abschalten des Seccomp-Schutzes ist kein
Ersatz fuer die Abnahme. Fuer einen Worker mit network_mode=none braucht der
Dispatcher einen ausdruecklichen und negativ getesteten Isolationsvertrag.

Host-systemd-Timer werden durch einen ueberwachten Container-Lebenszyklus ersetzt.
Doppelte Dispatcher, ueberlappende Telemetrie-Schreibvorgaenge und verlorene
SIGTERM-Signale muessen ausgeschlossen werden. SIGTERM darf einen laufenden
Job kontrolliert beenden; ein erzwungener Abbruch muss anschliessend als
wiederherstellungsbeduerftiger Zustand erkennbar bleiben.

## Erhalt des Bestands

Bisherige native Quellen, Units und Installer werden bei diesem Schritt nicht
verschoben oder geloescht. Der Docker-Kontext nimmt nur Programmpayloads auf,
keine Units, Rootinstaller oder Standortkonfigurationen. Erst nach gepruefter
Migration wird ueber die dauerhafte Rolle des nativen Installers entschieden.

Datenvolumes haben einen eigenen Versions-/Migrationsvertrag. Das Zuruecksetzen
eines Image-Digests allein ist kein Daten-Rollback. Jede nicht abwaertskompatible
Migration verlangt Sicherung, getestetes Restore und dokumentierte Reihenfolge.

## Technische Quellen

- https://docs.docker.com/reference/compose-file/services/
- https://docs.docker.com/compose/intro/features-uses/
- https://docs.docker.com/engine/security/seccomp/

Diese Quellen erklaeren Docker-Funktionen. Sie belegen nicht, dass der aktuelle
Slicer bereits als Container abgenommen wurde.

## Gepruefter Container-Zwischenstand

Die [synthetische Container-Abnahme](CONTAINER_TESTING.md) belegt den gemeinsamen
PID-Namensraum bei getrennten Netzwerken, beobachtbare Besitzeridentitaet,
SIGTERM-Abbruch und blockierten Wiederanlauf verwaister Jobs. Der Kernelvertrag
und die Supervisor-Ueberwachung liegen in Slicer-Server. Der native Dispatcher
nutzt im Container jetzt einen Kernel-geprueften Exec-Adapter; ausserhalb des
Containers bleibt die unshare-Strecke erhalten.
API-/Telemetrie-Lebenszyklus, Engine und Crash/Restore bleiben offen.

## Startfreigabe im Container

Die Supervisor-Huelle und der kanonische Jobcontroller besitzen jetzt eine
Bereitschafts-/Freigabe-Handschlagfolge. Ein Stop vor installierten Signalhandlern
wird als Ablehnungstoken zugestellt; ausbleibende Bereitschaft und vorzeitiges
Ende verlangen Wiederherstellung und lassen den queued-Zustand erhalten.
Drei synthetische Linux/amd64-Faelle wurden im Quell-Preflight-Image bestanden,
ohne den Dispatcher zu starten. Die produktive API-/Telemetrie-Anbindung,
Anchor-Ausfall, Crash/Restore, Engine und Datenvolumes bleiben offen.

## Docker-Dienstkandidat

Siehe [Installation und Abnahmegrenzen](RUNTIME_INSTALLATION.md). API, Worker,
Telemetrie und Compose sind implementiert. Die synthetischen Dienst- und
Restore-Tests ersetzen keine Engine-/Cross-Host-/Bestandsabnahme.

## Authentifizierter Erstinstallations-Zwischenstand (12.10.2026)

Der bestehende lokale Installer kann nach initialize und stage eine fehlende
aktive Generation ueber das dauerhafte FirstInstall-Journal aktivieren. Resume
und Rueckweg zu fehlendem ACTIVE bleiben request- und principalgebunden; ein
Adapterneustart ist synthetisch abgedeckt. Normale Upgrades verwenden weiter
den bisherigen Lifecycle. Der Transportvertrag wurde nicht erweitert.

Damit ist nur der Quellverbund geschlossen. HA-Backendclient/Handoff, echte
Linux-Dienstprovisionierung, TLS, Enginepakete und Lizenzen, Neuinstallation,
Upgrade/Restore und Pilot bleiben offen. container_deploy_ready=false.
