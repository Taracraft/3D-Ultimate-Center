# Installation und Komponenten

Das Studio besteht aus einer Home-Assistant-Integration, der Browseroberfläche und einem separaten Slicing-Dienst.

## Home Assistant

Die Integrationsquellen liegen im Repository unter `homeassistant/custom_components/ultimate_3d_studio/`. Die ausführliche [Einrichtung](../../README.md#einrichtung) beschreibt die Integration und die Frontend-Ressource. Eine offizielle HACS-Veröffentlichung des vollständigen Produkts liegt noch nicht vor; die im Repository enthaltenen Quellen richten sich derzeit auch an Entwickler.

## Slicing-Dienst

Für einen externen Slicer werden URL, Secret und ein passendes TLS-Zertifikat in den Integrationsoptionen eingetragen. Die CAD-Oberfläche und die Galerie sind vom Slicing-Dienst getrennt; ein offline gemeldeter Slicer verhindert nicht automatisch jede Modellbearbeitung.

Die [Slicer-Dokumentation](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/wiki) enthält Dockerbau, Verzeichnisse, Engine-Verwaltung und Betrieb. Ein freigegebenes App-Paket mit vollständiger Engine-Laufzeit ist noch nicht veröffentlicht.
