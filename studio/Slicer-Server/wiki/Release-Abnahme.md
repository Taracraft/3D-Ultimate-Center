# Release-Abnahme

Vor dem oeffentlichen Release muessen folgende Nachweise zusammenpassen:

1. Kanonische Quellen, Docker-Kontext und HACS-Paket sind klar abgegrenzt.
2. Container startet auf einem frischen Linux-Testhost ohne Entwicklungs-PC.
3. Rechte, Netzwerkisolation, Secret-/TLS-Schutz, Abbruch und Neustart funktionieren.
4. Engine, Profile und Bibliotheken haben belegte Herkunft und passende Lizenzen.
5. Ein ausdruecklich freigegebener echter Slice bestaetigt die unterstuetzte Plattform.
6. Erstinstallation, Update, Datenmigration und Restore sind nachvollziehbar getestet.
7. Home-Assistant-Verbindung und private Pilotinstallation sind abgenommen.
8. Oeffentliche Quellen, Historie und Artefakte sind auf private Daten und Lizenzumfang geprueft.
9. README, Installation und Wiki stimmen mit dem veroeffentlichten Image ueberein.
10. GitHub-CI ist gruen; benoetigte Branch-Aenderungen sind verlustfrei in main enthalten.

Das Wiki wird aus den versionierten Texten exportiert und nach dem Upload zurueckgelesen. Anschliessend werden die Links vom Repo-README und von den Releasehinweisen geprueft. Ein lokaler Wiki-Ordner allein gilt nicht als veroeffentlichtes GitHub-Wiki.

Branches werden erst nach bestaetigtem main und gesichertem Rueckweg entfernt. Gepruefte Quellen, geladene Laufzeit und veroeffentlichte Artefakte sind jeweils getrennte Nachweise.
