# H2S: Studio-, Worker- und Artefaktvertrag — 03.10.2026

Der H2S besitzt jetzt einen eigenen Modellvertrag, vier Düsen (0,2/0,4/0,6/0,8 mm), vier native Prozessgrundlagen, 37 native Filamentgrundlagen, zwei vollformatige Plattenoberflächen und vier getrennte Maschinen-/Soundvorlagen. Die beiden Filamentabschnitte bleiben in den Filamentprofilen. Ausgewählte Profile werden über unveränderte native Basishashes, Payloadbindung, Parametervergleich und ausgeführte Temperaturbefehle nachgewiesen.

## Nachweise im isolierten Kandidaten

- 592 Kombinationen vorgeprüft: 266 zulässig, 212 wegen nativer Düsenbindung und 114 wegen fehlender AMS-Freigabe abgewiesen. Engineering-/Verbundprofile bleiben für die externe Spule verfügbar; die AMS-Freigabe wird nicht durch einen beliebigen Benutzerparameter erweitert.
- 190 native Einzelmaterial-Slices über alle zulässigen Filament-/Düsen-/Oberflächenkombinationen bestanden. Keine Parameterabweichungen oder geprüften nativen Optionswarnungen.
- Zwei echte Mehrmaterial-Slices bestanden: PLA/PLA mit verschiedenen Normal-/Erstschichttemperaturen und PLA/PETG mit gemeinsamem Bettvertrag. Jeweils zwei Materialkanäle, 14 Materialwechsel und 13 Filament-Start-/Endblöcke. Modell, Stützen und Reinigungsturm bleiben innerhalb 340×320 mm.
- Zusätzlich 21 frische A1-Regressionsslices (PLA/PETG/TPU über die sieben A1-Düsenprofile) ohne Parameterabweichungen oder Optionswarnungen; 21/21 Artefaktprüfungen und G-Code-Profilbestätigungen bestanden. Der A1 bestätigt keinen Kammerheizer und lehnt positive Kammertemperaturen ab.
- Alle 192 Archive bestehen die vollständige Direktdruck-Artefaktprüfung. Alle 192 Profile sind aufgrund tatsächlicher Parameter und Temperaturbefehle `gcode_confirmed`; keine Bestätigung allein anhand eines Profilnamens.

Die Prüfung nutzt die installierten nativen Bambu-Quellen. H2S-Filamentdateien enthalten zusätzliche ungenutzte Extrudereinträge; für die einzelne physische Düse wird der erste Eintrag verwendet. Nullable native Rückzugswerte behalten die Maschinenvererbung. Die Kammertemperatur verwendet den tatsächlichen nativen Schlüssel `chamber_temperatures` und wird sowohl im Header als auch anhand M141/M191 geprüft. Beim Materialwechsel bindet der Prüfer M620.10 A1 P und M620.15 C an das nächste ausgewählte Material; das A0-Profil gehört zum bisherigen Material und bestätigt nicht den nächsten Kanal.

## Grenzen und nächste Roadmap-Punkte

Physische H2S-Platten benötigen den geprüften 340×320-mm-Vertrag, Bauraumhöhe 340 mm. Kleinere Platten erhalten keine stillschweigende Freigabe. Unabhängige Hardwaregrenzen bleiben 350 °C Düse, 120 °C Bett und 65 °C Kammer. Falsche Modelle, Düsen, native Grundlagen, Profile über diesen Grenzen und unpassende gemeinsame Bett-/Kammertemperaturen werden abgewiesen. Ein H2S-Header allein erteilt keine H2S-Hardwareautorität.

H2D/H2C mit ihrer tatsächlichen Werkzeugkonfiguration, kleinere physische Platten, weitere AMS-Hardwarefreigaben und reale Druckqualität bleiben separate Abnahmen. Tara besitzt aktuell den A1; diese H2S-Prüfung weist die native Softwarekette nach und behauptet keinen physischen H2S-Druck.

Die Softwareabnahme ist abgeschlossen; die folgenden Nachweise dokumentieren Gate und installierten Stand.

## Ergänzte Startprüfung

Die erste Live-Aktivierung scheiterte an einer älteren statischen Katalogprüfung, die für jedes lokale Profil A1-Felder verlangte. HA-Komponente und Frontend wurden aus dem geprüften Same-Day-Backup wiederhergestellt; Profil-API danach HTTP 200 mit 165 Profilen. Die Katalogprüfung wurde modellabhängig korrigiert: native H2S-Basis, Materialfamilie, AMS-Freigabe und effektive Temperaturparameter werden geprüft. Zusätzlich zum Windows-Gate wurde die vollständige Integration im tatsächlichen HA-Python-Umfeld importiert: 230 statische Profile, kein Importfehler. Das erneute Gesamtgate und die korrigierte Live-Aktivierung sind bestanden.

## Gesamtgate und installierter Stand

Abnahme abgeschlossen: Vollständiges Windows-Gate am 03.10.2026 um 12:44 Uhr (CEST): 1239 Python-Tests plus drei Untertests, 149 Frontend-Tests, Source-Policy, TypeScript, Produktions-/HA-Build und Compile-Prüfung bestanden. Korrigierter Stand nach HA-Konfigurationsprüfung und Neustart aktiv; Profil-API HTTP 200 mit 221 Profilen, darunter 52 H2S-Profile (37 Filamente, vier Düsen, ein Drucker, zwei Platten und acht Prozess-/G-Code-Profile). Zehn Worker-Abhängigkeiten und 26 Bereitstellungsziele per SHA bestätigt. Installierter Worker: 190 H2S- und 21 A1-Slices ohne Parameterverlust oder native Optionswarnungen. Mit dem tatsächlich installierten Prüfcode: 192/192 H2S-Archive (einschließlich zweier Mehrmaterialarchive) und 21/21 frische A1-Archive gültig und durch G-Code bestätigt; zusätzlich 322 frühere A1-Archive geprüft. Fünf manipulierte H2S-Archive werden abgewiesen. Puppet auf Port 5000 liefert die verbundene V6-Oberfläche; dies ersetzt keine interaktive oder physische Druckabnahme.

Same-Day-Backup der korrigierten Bereitstellung: `/var/lib/homeassistant/homeassistant/backups/20261003T104732Z-v6-h2s-studio-worker-contract`. Gate-Bundle-SHA256: `f7bfd148790143c0e9fc735339ebcefe3c05855038fc218de1370418fa8cf1b5`. Die erste Aktivierung wurde wegen der älteren A1-Katalogprüfung zurückgerollt; modellabhängige Prüfung und echter HA-Import sind korrigiert und erneut vollständig geprüft. Lokales Repo und HA-Quellen werden vollständig mit 588 Quelldateien und 598 öffentlichen GitHub-Zielen abgeglichen. Kein Druckerupload, Job-Release oder Druckstart.
