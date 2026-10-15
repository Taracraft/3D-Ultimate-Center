# Gepruefter Engine-Provenienzstand

Stand: 15.10.2026. Diese Datei dokumentiert ausschliesslich den statisch
geprueften Paket- und Lizenzstand. Sie ist keine Rechtsberatung, keine
Enginefreigabe und keine Betriebsabnahme. Keine Engine wurde fuer diese
Pruefung gestartet. Alle drei Familien bleiben im ausgelieferten Katalog
`pending`; `container_deploy_ready=false`.

## Gepruefte Paketbasis

| Familie / Bestandteil | Paket und Plattform | Archiv SHA-256 | Gepruefter Umfang | Status |
| --- | --- | --- | --- | --- |
| CuraEngine | Debian trixie `cura-engine 1:5.0.0-5`, amd64 | `0b0f7c53ea506001c7b56e83d4f1a2a72e73cd960886622462a1ffb5acb78379` | Programmdatei SHA `fe5de064a0d405135c97d1c1e86c33028c6d5f55956f4dbc9168d406625b10d7`; 8 direkte DT_NEEDED-Eintraege | pending |
| Cura-Ressourcen | Debian trixie `cura 5.0.0-6`, all | `ac3650ec34a5a5023a33775b6b8ac9e9ee27aa783550fededa6db171e523cc99` | 862 ausgewaehlte Dateien, Manifest SHA `1976698ffa7eb6efb9a8fd093238e4a81441bef859e80c456dd8180c0348101e` | pending |
| PrusaSlicer | Debian trixie `prusa-slicer 2.9.2+dfsg-1`, amd64 | `4ff3972a868621f48adee0e1d6848ce27ada765a2fdc1d0cb87e81026f6c5392` | 40 ausgewaehlte Dateien, Manifest SHA `8bd2336dfc66c4a7934ca77c39c2220a9658888d7df866ddd98e0094363d962a`; 42 direkte DT_NEEDED-Eintraege; OCCTWrapper 11 | pending |
| Bambu Studio | offizielles GitHub-Release `v02.07.01.62`, Ubuntu-24.04-AppImage, amd64 | `fa98b608532dfbbbb2b0931483aac41e57fb19c175a2cc7bd7d528d5e0fbb287` | Asset-ID `449304146`, 227047928 Bytes; annotierter Tag `c1b3547ae00b03412e4ba8e7b053481167acdf6a` verweist auf Commit `42d319c6692fa8e64790fddf0cdaafd2a4254bcc`; 118 ausgewaehlte Profilquellen bytegleich zum entpackten Ressourcenbaum | pending |

Archiv- und Dateihashes belegen Integritaet der untersuchten Bytes, nicht ihre
Herkunft oder Freigabe. Der GUI-Umfang des Debian-Pakets `cura` wird nicht
installiert; daraus werden nur begrenzte Datenressourcen untersucht. Der
Prusa-Satz ist trotz CLI-Einstieg nicht headless abgenommen: GUI-Bibliotheken,
OCCT-Ladepfad und Profilrechte bleiben offen.

Die vorhandene Bambu-AppImage ist nun exakt dem offiziellen GitHub-Release
`v02.07.01.62` zugeordnet: Asset-ID, Groesse und SHA-256 stimmen ueberein.
Der offizielle annotierte Tag verweist auf den bereits fuer die Profilquellen
gepinnten Commit; der Tag ist jedoch unsigniert. Die 118 ausgewaehlten
Profilquelldateien stimmen bytegenau mit dem entpackten Ressourcenbaum
ueberein. Dieser Herkunftsschritt beweist weder eine unabhaengige
Herstellersignatur oder reproduzierbare Binaeridentitaet noch die vollstaendige
Bibliotheks-, Plugin-, Notice-, SBOM-, Lizenz- oder Laufzeitclosure.

## Lizenzbelege und Grenzen

- Bambu Studio nennt upstream GNU AGPL Version 3. Das optionale
  Bambu-Netzwerkplugin wird nicht ausgewaehlt oder beigefuegt.
- PrusaSlicer nennt upstream GNU AGPL Version 3. Das Debian-Copyright des
  geprueften Pakets fuehrt daneben mehrere Lizenzen fuer mitgelieferte
  Bestandteile und Profile. Der vollstaendige Notice-Satz muss bei einer
  spaeteren Weitergabe erhalten bleiben.
- CuraEngine deklariert upstream AGPL-3.0. Das Debian-Copyright des konkreten
  Pakets wurde bytegenau gesichert; die komponentenweise Pflichtauswertung ist
  noch nicht rechtlich freigegeben.
- Die ausgewaehlten Cura-Ressourcen enthalten einen Notice-Satz mit Apache-2.0,
  BSD-3-Clause, CC0-1.0 und LGPL-3+-Deklarationen. Rechte einzelner
  Drucker-, Material-, Varianten- und Intentprofile sind weiter zu pruefen.
- Die eigene Lizenz in diesem Verzeichnis gilt nicht fuer diese fremden
  Programme, Bibliotheken oder Profile und schraenkt bestehende MIT-,
  AGPL- oder sonstige Fremdrechte nicht ein.

Offizielle Quellen:

- https://github.com/bambulab/BambuStudio/releases/tag/v02.07.01.62
- https://github.com/bambulab/BambuStudio/blob/42d319c6692fa8e64790fddf0cdaafd2a4254bcc/LICENSE
- https://github.com/bambulab/BambuStudio/blob/master/LICENSE
- https://github.com/prusa3d/PrusaSlicer/blob/master/LICENSE
- https://github.com/Ultimaker/CuraEngine
- https://packages.debian.org/trixie/cura-engine
- https://packages.debian.org/trixie/cura
- https://packages.debian.org/trixie/prusa-slicer

## Fail-closed Abschlusskriterien

Eine Familie darf erst aus `pending` wechseln, wenn fuer genau einen
unveraenderlichen linux/amd64-Paketsatz alle folgenden Punkte belegt sind:

1. Quellrevision und Paketursprung unabhaengig verifiziert; Signatur- oder
   gleichwertiger vertrauenswuerdiger Herkunftsnachweis dokumentiert.
2. Vollstaendige Lizenztexte, Copyright-Hinweise, Quellbereitstellungspflichten
   und SBOM fuer Programme, Bibliotheken, Ressourcen und Profile abgeschlossen.
3. Vollstaendige transitive Bibliotheks- und ABI-Closure im Zielimage,
   einschliesslich Prusa-OCCTWrapper-Ladepfad.
4. Ressourcen-, Material-, Varianten-, Intent- und Profilkompatibilitaet fuer
   die beworbenen Druckermodelle geprueft; ausgeschlossene Cura-Definitionen
   bleiben ausgeschlossen.
5. Reproduzierbarer Paketbau mit festem Manifest sowie autorisierte reale
   Linux-Start-, Profil- und Slice-Abnahme.

Bis dahin bleiben Downloadfreigabe, Katalogrelease, Imagefreigabe und
Produktivbetrieb gesperrt.

## Ergaenzende native Bibliotheksinventur vom 15.10.2026

Rein lesend wurden CuraEngine, PrusaSlicer, dessen OCCTWrapper und das
entpackte Bambu-Programm als vier ELF-Einstiege untersucht. `readelf -d`
liefert die direkten DT_NEEDED-/RPATH-/RUNPATH-Angaben; der vorhandene
linux/amd64-Hostcache von `ldconfig -p` liefert moegliche Bibliotheksdateien.
Der rekursiv untersuchte Host-Kandidatengraph umfasst **292 ELF-Dateien**,
**216 Debian-Pakete** mit exakten Binaer-/Quellpaketversionen und **216
Copyright-Dateien** mit Dateigroesse und SHA-256. Fuer diesen Graph wurden
keine fehlenden oder mehrfachen Hostcache-Kandidaten gefunden.
Der private strukturierte Inventarnachweis hat SHA-256
`aff23c053edc6af1b325e4544d2b3100a86a11be6b676e4c25882a897f78d443`.

Dieser Befund ist eine native Bestandsaufnahme, **keine vollstaendige
Zielimage-SBOM oder Loaderabnahme**. RPATH/RUNPATH sind erfasst, aber ihre
tatsaechliche Aufloesung, AppImage-eigene Bibliotheksauswahl und per dlopen
geladene Plugins sind damit nicht bewiesen. Ebenso sind die Copyright-
Dateihashes keine komponentenweise abgeschlossene Lizenzpflichtenpruefung.
Es wurde keine Engine gestartet und nichts installiert oder aktualisiert.

Fuer die noch offene Engine-Gesamtclosure werden in einem gemeinsamen Satz
benoetigt: unveraenderliche Archiv-/Quellreferenzen, alle tatsaechlich
ausgelieferten Dateien und Lizenzen, gebundene Ressourcen-/Profilketten,
vollstaendiges Zielimage-Paketinventar, dynamische Pluginpfade und echte
autorisierte Installations-/Laufzeit-/Restore-Ergebnisse. Alle drei
Katalogfamilien bleiben bis zu diesem gemeinsamen Nachweis `pending`.

## Zielimage-Inventarvertrag vom 15.10.2026

TARGET_IMAGE_REFERENCE.json fuehrt die 40 expliziten Debian-Paketnamen des
Dockerfiles sortiert und eindeutig. Die Referenz ist an den geprueften
Dockerfile-Hash und den privaten nativen Bibliotheksbefund
aff23c053edc6af1b325e4544d2b3100a86a11be6b676e4c25882a897f78d443
gebunden. Fuer 39 Bibliothekspakete liegt darin die konkrete Hostzuordnung vor;
jq 1.7.1-6+deb13u4 wurde separat lesend mit Copyright-SHA
0640a24687148cb525f6e917f982846c7d6682ccb13b939383d7bb596e7b29f5
belegt. Diese Angaben sind eine Vergleichsreferenz, kein Zielimage-Lock.

target_image_sbom.py nimmt spaeter ausschliesslich ein unveraenderlich
referenziertes Basisimage, eine konkrete Image-ID, die vollstaendige
fuenfspaltige Debian-Inventur und die Copyright-Datei jedes installierten
Pakets entgegen. Es speichert Binaer-/Quellpaketversion, Architektur und
Copyright-SHA, lehnt Duplikate, Links, fehlende Pflichtpakete und unklare
Identitaeten ab und kann den gespeicherten Beleg erneut pruefen. Das Werkzeug
startet weder Docker noch eine Engine und greift nicht auf das Netzwerk zu.
Ohne echte Zielimage-Ausgabe bleiben transitive Loader-/Plugin-Closure,
Paketnotice-Auswertung und reproduzierbarer Imagebau not_run; alle Releases
bleiben pending.

## Releasebuild-Referenz fuer Bambu Studio vom 15.10.2026

`BAMBU_BUILD_REFERENCE.json` bindet das beobachtete Ubuntu-24.04-Asset
zusätzlich an die oeffentliche Hersteller-CI. Der Release-Lauf
`27620769802` fuer Commit
`42d319c6692fa8e64790fddf0cdaafd2a4254bcc` verwendete den erfolgreichen
Ubuntu-24.04-Abhaengigkeitscache aus Lauf `26758993674`. Dessen Quellcommit
`3f126b717ed1f10fee0f32f05ed9731808d0c8bb` und der Releasecommit besitzen
denselben Git-Tree `deps`:
`55fa5b72f8b4e210516fe623cc204a4236a2b6a7`.

Das wxWidgets-Rezept ist Git-Blob
`c47db9b6b3d0ec245a45fd62dad9c8306bcf841c` und nennt beweglich
`GIT_TAG master`. Fuer den Zeitraum vom letzten vorherigen wxWidgets-Commit
bis zum Ende des Herstellerlaufs enthaelt die oeffentliche Master-Historie nur
den signaturverifizierten Commit
`a9d946902685b9946d8775f07d2a73a9b5bef394` mit Tree
`2e0f6c33ecbc235fccbbe54d3deb4e5e8e0aa2ee`. Die historische Auswahl ist
deshalb eng begruendet, bleibt aber als Ableitung gekennzeichnet: Cachebytes
und Joblogs sind nicht mehr abrufbar. Der zugehoerige Lizenztext ist
`docs/licence.txt`, Git-Blob
`0a25857e6c88e66a3c92e9db5573efb8c9d27a58` (wxWindows Library Licence 3.1).

Belegt sind Runner-Label `ubuntu-24.04`, Ninja, die Aufrufe
`BuildLinux.sh -ur`, `-dfr` und `-isfr`, GTK3, statische Studio-Bindung
und Releaseflags. Nicht belegt sind dagegen die konkrete Runner-Imageversion,
Compiler-/CMake-/Ninja-Versionen und apt-Paketversionen; das Debian-Paketrezept
ist zwar durch Blob `f76d5e0acc3e6ad5933dd7683c2292bf16ff4493` gebunden,
pinnt aber keine Versionen. Damit ist die Herstellerbinaerdatei weiterhin
nicht reproduziert. Zielimage-, Loader-, Plugin-, Ressourcen-, Notice-,
Lizenz- und reale Linuxabnahme bleiben offen. Katalog und
`container_deploy_ready=false` bleiben unveraendert fail closed.


## Statischer FFmpeg-Buildvertragsbefund vom 15.10.2026

Die gepruefte Originalrevision BambuStudio 42d319c6692fa8e64790fddf0cdaafd2a4254bcc
setzt im CMake-Rezept deps/FFMPEG/FFMPEG.cmake zwar die lokalen Zeichenketten
--enable-gpl und --enable-nonfree in _extra_cmd. Der tatsaechliche
CONFIGURE_COMMAND verwendet _extra_cmd aber nicht und uebergibt die beiden
Schalter auch nicht unmittelbar. Das Standard-CMake-Flag DEP_BUILD_FFMPEG ist
ON, kann durch den historischen, nicht archivierten Cache jedoch abweichen.

Diese Quellenanalyse ist weder der effektive FFmpeg-Konfigurationsausdruck des
Hersteller-Builds noch eine Lizenz- oder Weitergabefreigabe fuer die Binaerdatei.
Dafuer werden tatsaechliche Konfigurationsbelege, enthaltene Bibliotheken und
Plugins sowie die zugehoerigen Rechte und Quellen benoetigt. Der Befund darf
nicht als bestaetigtes aktives --enable-nonfree und auch nicht als
Lizenzunbedenklichkeit ausgegeben werden.

Die 27 bereits gepinnten externen Quellarchiv-Kandidaten wurden gegen ihren
Notice-Index zugeordnet; alle 302 unterschiedlichen archivierten Notice-Texte
wurden erneut auf Laenge und SHA-256 geprueft. Ein gesicherter Notice-Text
beweist noch keine vollstaendige komponentenbezogene Lizenzpruefung. Keine
Archive neu bezogen, keine Engine ausgefuehrt, keine Laufzeit geaendert.
Freigaben fuer alle drei Enginefamilien und den Container bleiben pending.
