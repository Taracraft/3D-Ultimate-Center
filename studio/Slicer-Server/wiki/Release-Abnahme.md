# Gemeinsame Abschluss- und Release-Abnahme

Stand: 15.10.2026. Diese Matrix fasst den gesamten verbleibenden Abschluss
zusammen. Sie ist keine Produktivfreigabe. Quelllieferung, reales Zielsystem,
geladene HA-Oberflaeche und veroeffentlichtes Release sind getrennte Staende.

| Bereich | Bereits belegt | Noch erforderlicher Abschluss |
| --- | --- | --- |
| Vollstaendige Quellen | Eigenstaendige Komponentenprojektion, Manifest, eigene Linux-CI, native/Docker-/Testpaketbauer und Offline-Profilquellen | Aktuelle Commit-/Manifestidentitaet bei jeder neuen Lieferung erneut pruefen |
| Herkunft und Rechte | Offizielle Bambu-AppImage exakt zugeordnet; voller Bambu-Quellcommit und externe Rezeptarchive privat hashgeprueft; 118 Profilquelldateien bytegleich; Hersteller-CI und unveraenderter deps-Tree an den abgeleiteten wxWidgets-Commit gebunden; Debian-Paketarchive statisch untersucht | Historische Cachebytes und Werkzeugversionen fehlen; Herstellerbinaerdatei reproduzieren und vollstaendige dateibezogene Quellen-/Lizenz-/Notice-/SBOM-Pflichten fuer die konkrete Auslieferung schliessen |
| Bibliotheken und Plugins | Native Hostinventur: 292 ELF-Dateien, 216 genaue Debian-Pakete und Copyright-Dateihashes; fail-closed Zielimage-Inventarvertrag fuer 40 explizite Docker-Pakete | Tatsaechliches vollstaendiges Zielimage-Inventar erfassen und Loader-/Plugin-/Ressourcenumfang messen; Referenz und Hostinventur genuegen nicht |
| Frisches Linux und Docker | Kontext-/Integritaets-/Clean-Host-/Compose-Vertraege, synthetische Tests und offline pruefbarer SBOM-Erfasser | Neuer unabhaengiger Host ohne nativen Altbestand; fester Basisdigest, Image-ID und kompletter Paket-/Copyright-Beleg; echter Imagebuild/Erststart |
| Rechte und Isolation | Fail-closed Pruefcode fuer Benutzer, Mounts, Prozesse, Netzwerk und Wartung | Laufende Zielcontainer, Image-ID, UID65532, Mountrechte, Read-only-Root, CapDrop und NoNewPrivileges messen |
| Authentifizierung und TLS | API-/Client-/Secret-/TLS-Vertraege und begrenzte Pruefwerkzeuge | Echte getrennte Gegenstellen; gueltiges Zertifikat sowie falsche CA, falsches Secret, Timeout/DNS/Offline pruefen |
| Neustart und Persistenz | Dauerhafte Initialisierung, Journale und synthetische Fehlerfaelle | Container- und Hostneustart mit unveraenderten Daten-/Profildigests messen |
| Upgrade und Rueckweg | Transaktionale Staging-/Aktivierungs-/Rollback-Vertraege | Zwei reale gepinnte Staende; Teilfehler, Wartung, Rollback und getrenntes Resume pruefen |
| Backup und Restore | Datenerhaltende Vertraege und Verifier | Vollstaendige private Sicherung in ein neues Ziel zurueckspielen; Quell-/Restore-Digests vergleichen |
| Hostkanal und HA | Gepinnter Unix-Transport, Endpoint-/Peer-/Tokenpruefungen; isolierte HA-Flow-/Speichertests | Unterstuetzte Supervisor-/Mountprovisionierung und SO_PEERCRED beider Enden auch nach Neustart belegen; erst dann sichtbare Installerverdrahtung |
| HACS und Oberflaeche | Reproduzierbarer Paket-/Asset-/Importvertrag; dokumentierte Studiofunktionen und echte CAD-Originalbilder | Frische separate HA-/HACS-Installation, geladene Assets, Optionen, Upgrade/Reload/Unload und Datenbestand abnehmen |
| Privater Pilot | Gepruefte Quellkandidaten und Rueckwegvertraege | Erst nach Linux/Engine/HA/HACS: Tagesbackup, aktuelle Livehashes und echte Sicht-/Betriebsabnahme |
| Public Release und Wiki | Versionierte Anleitungen/Wiki-Quellen und gepruefte Git-Quelllieferung | Gesamte Freigabematrix, Rechte-/Datenschutzreview, passende Releaseartefakte und tatsaechlicher Wiki-Upload mit Readback |

## Eine geordnete Ausfuehrung

1. Aktuelle Quellen, Manifest, CI und alle Paket-/Asset-SHAs zusammen pinnen.
2. Herkunft/Rechte, komplette Engine-/Profil-/Plugin-/Bibliotheksauswahl und
   reproduzierbares Zielimage schliessen.
3. Auf dem sauberen separaten Testserver Installation, Isolation, TLS,
   Neustart/Persistenz, Upgrade, Rollback und Backup/Restore messen.
4. Den unterstuetzten Hostkanal sowie echte HA-/HACS-Installation abnehmen.
5. Erst danach privaten Pilot und oeffentliches Release abschliessen.

Der [Linux-Testserververtrag](../LINUX_TEST_SERVER_RUNBOOK.md) ist fuer
Messungen massgeblich. Die Evidence-Vorlage beginnt mit `not_run`;
fehlende Messungen werden nicht aus synthetischen Tests ergaenzt.
Der Arbeitsplatz-Testserver bleibt MCP-frei; nur bereinigte manuelle
Ergebnisse werden zurueckgegeben. Das bestehende native Live-System wird
fuer diesen Abschluss nicht in einen Compose-Mischbetrieb umgebaut.

Ein echter Slice benoetigt einen gesonderten konkreten Auftrag. Ein
Druckstart ist davon getrennt und benoetigt die vorgesehene zweistufige
Freigabe. HAOS-Migration bleibt ein eigener ausdruecklicher Auftrag.

## Gemeinsamer Abschlussbeleg

Zu jedem realen Ergebnis gehoeren Datum, konkrete Software-/OS-/Architektur,
Commit-/Archiv-/Image-/Assetidentitaet, Voraussetzungen, beobachtetes
Ergebnis und bereinigte Belege. Keine Secrets, privaten Modelle, Rohlogs
oder standortspezifischen Zugangsdaten in Issues oder Wiki kopieren.

Ein Screenshot nimmt nur den nachgewiesenen geladenen Build ab. Die
bestehenden Originalbilder dienen der Anleitung und sind kein Nachweis
einer neu ausgerollten Version. Quell-CI, Paketbau, Installation und
Produktivfreigabe bleiben gesondert erkennbar.

Das Wiki wird aus den versionierten Texten exportiert und nach Upload
zurueckgelesen; anschliessend werden README-/Release-Links geprueft.
Ein lokaler Wiki-Ordner ist kein veroeffentlichter Wiki-Tab.
`production_approved=false` und `container_deploy_ready=false` bleiben
bis zum echten Gesamtabschluss erhalten.
