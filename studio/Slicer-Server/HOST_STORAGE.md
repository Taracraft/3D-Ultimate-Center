# Dauerhafter Hostspeicher

Status: Linux-Speicheradapter implementiert und synthetisch geprueft.
Dies ist eine Grundlage des Hostinstallers, noch kein erreichbarer Dienst,
kein HA-Einrichtungsassistent und keine installierbare Enginefreigabe.

## Standardweg und Zuständigkeit

host_storage.provision verwendet standardmaessig
/var/lib/ultimate-slicer-server mit engines, data und profiles. Ein lokaler,
vertrauenswuerdiger Hostadapter muss vorher eine private Steuerablage
ausserhalb dieses Baums bereitstellen. Der Benutzer soll im spaeteren
HA-Assistenten den automatisch verwalteten Speicher bestaetigen koennen.
Ein eigener Pfad ist eine erweiterte lokale Kopplungsoption, kein freies
Feld im Remote-Installervertrag.

provision akzeptiert nur einen direkten vorhandenen Elternpfad unter
lokal erlaubten Wurzeln. Es erzeugt keine fehlenden Zwischenverzeichnisse,
mountet nichts und uebernimmt keine vorhandenen fremden Daten. Bei der
ersten Kopplung muss der Hostadapter den gewollten Datentraeger bestaetigen:
Die automatische Erkennung kann keinen noch nie gebundenen, fehlenden
Wunschdatentraeger erraten. Der Standardweg bindet das aktuell nachgewiesene
dauerhafte Dateisystem. Spaetere Aufrufe muessen genau diese Bindung erfuellen.

Dieser Adapter gilt fuer den verwalteten Linux-Dockerhost. HA OS/Supervisor
braucht einen gesonderten, geprueften Speichervertrag; innerhalb eines
Containers vorhandene Overlaypfade gelten nicht als dauerhafter Hostnachweis.
Es gibt keinen Docker-Socket und keinen privilegierten Container als Abkuerzung.

## Native Pruefung

native_volume liest ausschliesslich /proc/self/mountinfo, Dateimetadaten
und /dev/disk/by-uuid. Es startet keinen Befehl und veraendert keine Mounts.
Die tiefste passende Mountstelle muss zur Geraetenummer des realen Pfads
passen, beschreibbar sein und derzeit ext4 oder xfs verwenden.
Genau ein passendes Blockgeraet mit Dateisystem-UUID ist erforderlich.

Die Bindung enthaelt UUID, Dateisystemwurzel, Mountpunkt und Dateisystemtyp.
Mehrdeutige gestapelte Mounts, fremde untergeordnete Mounts, Symlinks,
unsichere Vorfahren und fehlende UUIDs werden abgewiesen. Temporäre Bereiche
/tmp, /var/tmp, /run, /dev, /proc und /sys bleiben auch dann ausgeschlossen,
wenn darunter ein sonst geeignetes Dateisystem liegt. Netzwerk-, Overlay-,
tmpfs-, Btrfs- und ZFS-Speicher sind aktuell nicht freigegeben.

Nicht betroffene Namespace-Mounts koennen nichtabsolute Kernel-Wurzeln
enthalten. Der Parser akzeptiert diese Eintraege; als Speicherziel werden
sie weiterhin abgewiesen. Eine reale lesende Linux-Probe deckte diesen
Sonderfall auf und ein Regressionstest sichert ihn ab.

## Anlage, Wiederholung und Abbruch

Vor dem ersten Anlegen wird mindestens 256 MiB freier Platz geprueft.
Dies ist nur die Layoutreserve; Download/Aktivierung pruefen ihre eigenen
Paketgroessen. Die gemeinsame nichtblockierende Installationssperre
serialisiert Provisionierung und Installeroperationen.

VOLUME.json liegt privat ausserhalb des Datenbaums. Der dauerhafte Zustand
provisioning wird vor der ersten Layoutaenderung geschrieben. Danach werden
Datentraeger, Verzeichnisse und Bindung nochmals geprueft und ready gesetzt.
Ein Abbruch hinterlaesst eine sichtbare, gesperrte Transaktion. Er verlangt
lokale Abklaerung; automatische Bereinigung, Datenloeschung oder Adoption
gibt es nicht. Wiederholung einer fertigen Anlage erhaelt Nutzerdaten.
Verschwundene Unterverzeichnisse werden dabei nicht still neu erstellt.

VolumeGuard ist als verify_volume des eingeschraenkten Installers verwendbar.
Er prueft die externe Bindung sowie Basis, engines, data und profiles erneut.
Ein Datentraegerwechsel, fehlender Pfad oder veraenderter Beleg liefert false.
Der integrierte synthetische Test initialisiert damit den echten Installerstore.

## Grenzen und weitere Integration

Die neuen Verzeichnisse starten privat (0700) und installer-eigen. Die
nachgelagerte Gruppenfreigabe fuer Daten/Profile ist in RUNTIME_PERMISSIONS.md
beschrieben. Engine-Store und Steuerdaten bleiben privat. Profile-Verbraucher,
Hostkopplung und die vollstaendige Containerinstallation sind weiterhin offen.

Die UUID-Bindung toleriert prinzipiell neue Kernel-Geraetenummern; der
vorhandene Aktivierungsstore prueft zusaetzlich seine numerische Geraetebindung.
Nach einem solchen Neustart kann eine explizite lokale Abklaerung erforderlich
sein. Es gibt keine automatische Neubindung oder Abschwaechung dieser Pruefung.

Rechecks sind keine atomare Mountsperre gegen einen parallel handelnden
privilegierten Administrator. Dauerhafte Erreichbarkeit bei Hardwareausfall,
Backup/Restore, Stromausfall und realem Neustart bleiben Hostabnahmen.

Offen: Supervisoradapter, Hostkopplung/TLS/Tokenrotation, Profildatenanbindung,
Idle/Stop/Start/Health und Dienstrollback, HA-Backendclient und Assistent.
Alle echten Engine-Releases bleiben pending, container_deploy_ready=false.

## Nachweise

26 Speicherfaelle bestehen unter Linux ohne Skip. Gemeinsam mit Installer
und Aktivierung bestehen auf Windows 71 Tests und 20 Untertests; drei
POSIX-Rechtefaelle werden dort ausgelassen. Die reale Linux-Probe erkennt
das ext4-Dateisystem und seine UUID rein lesend; kein Installationslayout,
Container, Dienst, Engine oder echter Job wurde dabei erzeugt/gestartet.
Gesamtgate, Quellabgleich und Rueckweg stehen im privaten Abschlussbeleg.

Technische Referenzen:
- https://www.kernel.org/doc/html/latest/filesystems/proc.html
- https://cgit.freedesktop.org/systemd/systemd/tree/src/udev/rules/60-persistent-storage.rules


## Ergaenzung: implementierte Laufzeitrechte

[RUNTIME_PERMISSIONS.md](RUNTIME_PERMISSIONS.md) beschreibt die nachgelagerte
Freigabe fuer Gruppe65532. Die initialen 0700-Verzeichnisse bleiben der
Ausgangszustand; data/profiles koennen nun nach Volume-/Stillstandspruefung
gezielt root:65532/2770 erhalten. Ein externer Beleg bindet diese Ausnahme.
Vollstaendige Containerinstallation und HA-Assistent bleiben offen.
