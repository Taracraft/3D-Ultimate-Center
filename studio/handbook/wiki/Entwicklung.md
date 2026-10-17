# Entwicklung

Die Studio-Quellen verbinden ein TypeScript-Frontend mit der Python-Integration und gemeinsam verwendeten Slicer-Modulen. Im öffentlichen Gesamtrepository liegt der Produktbereich unter `studio/`. Beginne eine Änderung mit dem betroffenen Arbeitsablauf: Welche Eingabe löst sie aus, welche Komponenten tragen die Daten weiter und welches Ergebnis muss erhalten bleiben?

## Voraussetzungen

Verwende einen nachvollziehbaren Checkout und die zum Repository passenden Node- und Python-Abhängigkeiten. Lies vor dem Start die Architektur und die CI-Abhängigkeiten. Plattformabhängige Tests benötigen ihre vorgesehene Umgebung. Ein unter Windows übersprungener POSIX-Fall gilt nicht automatisch als unter Linux bestanden.

## Einen Beitrag nachvollziehbar vorbereiten

1. Ermittle die führende Quelldatei und die betroffenen Schnittstellen. Generierte Dateien sind keine geeignete Grundlage für eine dauerhafte Korrektur.
2. Beschreibe den beobachteten Fehler mit Eingaben und erwarteter Wirkung. Sichere einen geeigneten Ausgangsstand.
3. Ergänze bei einer Verhaltensänderung einen gezielten Nachweis, der den betroffenen Vertrag prüft.
4. Korrigiere den Ablauf und prüfe die relevanten Nachbarfälle, insbesondere Objekt-, Material-, Platten- und Auftragsidentität.
5. Führe die vorgesehenen Build- und Testprüfungen aus. Bei gemeinsam verwendeten Slicer-Modulen prüfe auch das Komponentenpaket.
6. Dokumentiere Ergebnis, Plattformgrenzen und nötige weitergehende Prüfungen.

Die bestehenden Entwicklungsbefehle umfassen `npm ci`, `npm run typecheck`, `npm test` und die Python-Testausführung. Arbeitsverzeichnis und Abhängigkeiten müssen zum jeweiligen Checkout passen; nutze dafür die [CI-Abhängigkeiten](https://github.com/Taracraft/3D-Ultimate-Center/blob/main/studio/CI_DEPENDENCIES.md).

## Ergebnisse richtig einordnen

Automatisierte Tests und ein erfolgreicher Build liefern konkrete Quellnachweise. Eine echte Home-Assistant-Installation, Engine-Ausführung, mobile Bedienung und physischer Druck sind zusätzliche Prüfebenen. Berichte deshalb, was tatsächlich ausgeführt wurde und welche Grenzen simuliert oder noch offen sind. Veränderte Quellen, veröffentlichte Pakete und eine geladene Laufzeit können unterschiedliche Stände haben.

Bei einem Testfehler prüfe zuerst Umgebung, Versionen und die relevante Änderung. Ändere erwartete Hashwerte oder Aussagen erst nach einem begründeten Vergleich. Das erwartete Ergebnis eines Beitrags sind verständliche Quellen, passende Nachweise und eine reproduzierbare Build-Zuordnung. Das [Handbuch](https://github.com/Taracraft/3D-Ultimate-Center/blob/main/studio/README.md) erklärt die Anwenderabläufe; die [Architektur](https://github.com/Taracraft/3D-Ultimate-Center/blob/main/studio/ARCHITECTURE.md) beschreibt die technischen Grenzen.
