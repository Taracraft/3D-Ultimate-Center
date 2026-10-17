# Build und Tests

Die Slicer-Quellen werden mit Python-Tests und einer eigenen GitHub-Actions-Pipeline geprüft. Der Build-Kontext übernimmt eine festgelegte Auswahl der benötigten Dateien. Damit lassen sich Quellumfang und Paketaufbau nachvollziehen. Ein erfolgreicher Build ist jedoch weder ein Nachweis vollständiger Engines noch eine bestätigte Installation.

## Voraussetzungen

Arbeite aus einem eindeutig benannten Repository-Stand. Die Python-Abhängigkeiten stehen in `requirements-test.txt`. Für den Imagebau sind zusätzlich die Voraussetzungen des [Docker-Schnellstarts](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/DOCKER_QUICKSTART.md) zu beachten. Welche Dateien zum Quellpaket gehören, beschreibt [Quellcode und Verzeichnisse](Quellumfang.md).

## Quellen und Tests prüfen

Führe die Prüfungen aus dem Repository-Wurzelverzeichnis aus:

```sh
python3 Slicer-Server/build_repository.py --verify .
python3 Slicer-Server/verify_profile_sources.py --source-root .
python3 -m pytest -q tests
```

Der erste Aufruf prüft den vorgesehenen Repository-Aufbau, der zweite die Profilquellen. Die Tests ergänzen diese Prüfungen für die von ihnen erfassten Verhaltensweisen. Halte zu einem Ergebnis den tatsächlich geprüften Commit, den genauen Aufruf und den beobachteten Ausgang fest. Ordne einen Pipeline-Erfolg immer dem zugehörigen Commit zu.

Für den Imagebau und isolierte Laufzeitprüfungen gelten die jeweiligen Anleitungen. Übernimm keine frei gewählten Build-Dateien oder nicht dokumentierten Laufzeitparameter in einen vermeintlich vergleichbaren Nachweis.

## Ergebnis richtig bewerten

Ein grüner Testlauf gilt für seinen konkreten Prüfbereich. Er bestätigt nicht automatisch vollständige Bedienabläufe, reale Engine-Ausführung, Hardwareverhalten, die Home-Assistant-Installation oder mobile Ansichten. Das Prüfimage kann Quellen und Systempakete kontrollieren; es enthält keine Slicing-Engines.

## Fehler behandeln

Bei einem Fehler zunächst den geprüften Stand und die Eingabedateien festhalten. Unterscheide ein falsches Arbeitsverzeichnis, fehlende Abhängigkeiten, eine abweichende Datei und einen tatsächlichen Testfehler. Korrigiere die Ursache und wiederhole die betroffene Prüfung mit dokumentierter Zuordnung. Ein veränderter Erwartungswert allein ist kein Beleg für eine behobene Regression.

Die [Container-Tests](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/CONTAINER_TESTING.md) beschreiben den isolierten Prüfweg. Das [Handbuch](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/HANDBUCH.md) ordnet die Prüfungen in den Betrieb ein. Der [Entwicklungsstand](Entwicklungsstand.md) zeigt, welche Laufzeitbestandteile verfügbar sind und welche Nachweise noch ausstehen.
