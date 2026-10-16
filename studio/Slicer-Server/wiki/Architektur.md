# Architektur

Die HTTP-API nimmt Anfragen entgegen und verwaltet Aufträge. Der Worker verarbeitet sie in einem getrennten, netzwerklosen Container. Engine- und Profilverzeichnisse werden schreibgeschützt eingebunden. Konfiguration, Eingaben und Ergebnisse bleiben außerhalb des Images.

Die Compose-Datei trennt Initialisierung, API und Worker. Der Docker-Socket gehört nicht in diese Laufzeitcontainer. Details stehen in [Laufzeitkonfiguration](../RUNTIME_INSTALLATION.md) und [Berechtigungen](../RUNTIME_PERMISSIONS.md).
