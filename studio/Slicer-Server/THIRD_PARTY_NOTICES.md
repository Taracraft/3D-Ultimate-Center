# Lizenzgrenzen des Slicer-Servers

Die Datei LICENSE gilt nur fuer neu geschriebene eigene Dateien in diesem
Bereich. Der erzeugte Ordner payload wird aus bestehenden Studio-Quellen
zusammengestellt und dadurch NICHT neu lizenziert. Sein Manifest traegt
license_scope=inherited-unresolved, bis Herkunft und Rechte pro Datei
abgeschlossen sind. Ein erfolgreiches SHA-Ergebnis ist keine Lizenzfreigabe.

| Bestandteil | Lizenz / Status | Veroeffentlichung |
|---|---|---|
| Neuer Docker-Pruefcode und neue Dokumentation in Slicer-Server | Eigene Privatnutzungs-Lizenz, keine Quellcodeaenderungen | Rechteumfang vor Release pruefen |
| Bestehender Studio-/Worker-Code im Payload | Bisheriger Lizenz- und Urheberstatus bleibt bestehen | Dateibezogene Herkunftspruefung offen |
| Bereits unter MIT publizierte Fassungen | MIT-Rechte und Copyright-Hinweise bleiben erhalten | Keine rueckwirkende Rechteentziehung |
| Python-Basisimage und Betriebssystem | Lizenzen der konkreten Imagebestandteile | Digest, Paketliste und Hinweise vor Release erfassen |
| Bambu Studio Programm/Engine | Upstream LICENSE: GNU AGPL Version 3 | Engine-Binaerdatei nicht enthalten; abgeleitete Profildaten gesondert unten |
| Bambu-Netzwerkplugin, weitere Engines und Profile | Jeweilige Rechte gesondert pruefen | Keine automatische Beschaffung oder Beigabe |

Die Engine ist im ersten Docker-Kontext bewusst nicht enthalten. Das ist noch
keine rechtliche Bewertung einer spaeteren Kopplung von Engine und Server.
Rechte an Maschinen-/Materialprofilen und erforderlichen Laufzeitbibliotheken
muessen ebenso belegt sein wie Rechte am Engine-Programm.

Ein oeffentliches GitHub-Repository kann nach GitHubs Bedingungen angesehen und
geforkt werden. Die gewuenschte Nutzungsbeschraenkung ist eine Lizenzbedingung,
keine technische Sperre gegen das Bearbeiten heruntergeladener Dateien.

## Quellen

- https://github.com/bambulab/BambuStudio/blob/master/LICENSE
- https://opensource.org/license/mit
- https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository

Stand der Quellenpruefung: 10.10.2026. Diese Datei ersetzt keine rechtliche
Pruefung des konkreten Releases.

## Gepruefter Provenienzstand vom 14.10.2026

Der reproduzierbare, fail-closed Pruefstand ist in [ENGINE_PROVENANCE.md](ENGINE_PROVENANCE.md) festgehalten. Geprueft wurden die Debian-Pakete cura-engine 1:5.0.0-5, cura 5.0.0-6 und prusa-slicer 2.9.2+dfsg-1 sowie ihre eingefrorenen Archive, ausgewaehlten Ressourcen und direkten ELF-Abhaengigkeiten.

Dieser Nachweis ist **keine** Rechts-, Release- oder Laufzeitfreigabe. Bambu Studio, PrusaSlicer und CuraEngine bleiben im Katalog pending. AGPL-Pflichten, die mehrlizenzierte Cura-Ressourcenauswahl, vollstaendige Quellrevisionen, transitive Bibliotheken, Profile, Plugins und SBOM muessen vor einer Veroeffentlichung geschlossen und unabhaengig geprueft werden.

## Mitgelieferte Payload-Nachweise (14.10.2026)

licenses/MIT-Studio.txt bewahrt den historischen Studio-MIT-Text samt
Copyright bytegenau. licenses/AGPL-BambuStudio.txt enthaelt den unveraenderten
Upstream-Lizenztext der gepinnten BambuStudio-Revision
42d319c6692fa8e64790fddf0cdaafd2a4254bcc (Tag v02.07.01.62, unsigniert).
Beide Texte sind eigenstaendige Lizenzhinweise und fallen nicht unter die
Privatnutzungsbeschraenkung fuer neues eigenes Material.

PAYLOAD_PROVENANCE.json ordnet alle 19 Laufzeit-/Profildateien ihren
Quellpfaden, aktuellen SHA-256 und historischen Gitobjekten zu. 14 Dateien
sind Laufzeitcode, drei sind Engineprofil-Referenzdeskriptoren und zwei
enthalten aus Upstream-Profilen abgeleitete Defaults. Die Herkunft der
54 direkt verwendeten Profile und 118 rekursiven Upstream-JSON-Dateien ist
mit Commit, Gitblob und SHA dokumentiert. Die Provenienzdatei beschreibt Identitaeten. Seit W84 liegen die 118
zugehoerigen JSON-Originalquellen separat in PROFILE_SOURCE_BUNDLE.json bei.
Dies ist nicht die vollstaendige korrespondierende Engine-Quelle.

Bearbeitung: 46 ausgewaehlte Filamentwerte entsprechen den aufgeloesten
Upstream-Werten; 12 Prozessfelder verwenden jeweils das erste Element des
Upstream-Vektors. In den beiden Maschinen-G-Code-Vorlagen ersetzen Marker
die separat gespeicherten Soundabschnitte. Wiedereinsetzen der Sounds
rekonstruiert die vollstaendigen Upstream-Vorlagen bytegenau. Kein G-Code
wurde fuer diesen Nachweis ausgefuehrt.

Die Lizenztexte und Provenienzdatei liegen im vorbereiteten Kontext, im
deterministischen Testarchiv und laut Dockerfile auch im spaeteren Image.
Manifest und festgelegte Lizenz-SHAs pruefen die Texte; Payload-Hashes binden
den Herkunftsnachweis an die tatsaechlichen Quellen. Fehlende/geaenderte
Lizenztexte oder veraltete Payload-Zuordnung sperren die Paketbildung.

Der mitgelieferte AGPL-Text setzt den zuvor offenen Status nicht automatisch
auf freigegeben: konkrete Rechte an Profilen, korrespondierende Quellen,
Bearbeitungs-/Kombinationspflichten und Lizenzkompatibilitaet bleiben vor
Weitergabe zu pruefen. license_scope=inherited-unresolved bleibt erhalten;
publication_approved=false und container_deploy_ready=false bleiben gesetzt.
Neue eigene Einschraenkungen gelten nicht fuer fremde oder frueher wirksam
lizenzierte Bestandteile. Ein echter Imagebuild wurde hier nicht ausgefuehrt.

Gepinnte Referenz:
https://github.com/bambulab/BambuStudio/blob/42d319c6692fa8e64790fddf0cdaafd2a4254bcc/LICENSE

## Ausgewaehlte Profilquellen offline nachvollziehen (W84)

PROFILE_SOURCE_BUNDLE.json enthaelt 118 unveraenderte Original-JSON-Texte
aus der oben gepinnten BambuStudio-Revision, einschliesslich der rekursiv
benoetigten Eltern-/Include-Dateien fuer die 54 geprueften Profile.
Originalbytes, SHA-256, Gitblob-Identitaeten und Auswahlpfade bleiben
nachpruefbar. Das ist Fremdmaterial unter vorbehaltener konkreter
Rechtepruefung; die eigene Privatnutzungslizenz wird darauf nicht angewandt.
Der vollstaendige Upstream-AGPL-Text bleibt unter licenses beigefuegt.

verify_profile_sources.py prueft die bekannte Quellbeigabe rein offline:
Originalbytes/Gitobjekte, beide Include-Reihenfolgen, 54 aufgeloeste Hashes,
ausgewaehlte Filamentwerte, 12 Prozessprojektionen und acht Rekonstruktionen
der Maschinen-Start-/Endvorlagen mit den separat gespeicherten Sounds.
Der Verifikator interpretiert JSON-Daten; er fuehrt keinen Profilcode,
G-Code, Materializer, Worker oder Engine aus und veraendert keine Quelle.

Die Beigabe deckt genau diese Profil-/Include-Auswahl ab. Sie ersetzt weder
die vollstaendige korrespondierende Engine-Quelle noch die konkrete
Lizenz-/Kombinationspruefung, Bibliotheks-/Plugin-SBOM oder reale
Linux-/Docker-/TLS-/Upgrade-/Restore-Abnahmen. Freigabeflags bleiben falsch.
