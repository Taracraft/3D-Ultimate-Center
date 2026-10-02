#!/bin/bash

set +e
set +u
set +o pipefail 2>/dev/null

STAGE="$1"
EXPECTED_DISPATCHER_SHA='4370d40b8e9c4b40115d6281460e86a30842b870905189de9b1a92a68733dda4'
WORKER='/var/lib/homeassistant/3d-printer-slicing-server'
SOURCE="$STAGE/custom_components/ultimate_3d_studio_v6/dispatch-job-options.sh"
TARGET="$WORKER/dispatch-job.sh"
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP="/var/lib/homeassistant/homeassistant/pcc-backups/v6-worker-artifact-fix/$STAMP"
LOG="/var/lib/homeassistant/homeassistant/pcc-backups/v6-worker-artifact-fix-$STAMP.log"
FAILED=0
INSTALLED=0

mkdir -p "$(dirname "$LOG")" "$BACKUP"
exec > >(tee -a "$LOG") 2>&1

echo '============================================================'
echo 'V6 WORKER-ARTEFAKT-HOTFIX'
echo '============================================================'
echo "Quelle:     $SOURCE"
echo "Dispatcher: $TARGET"
echo "Backup:     $BACKUP"
echo "Log:        $LOG"

if [ -z "$STAGE" ] || [ ! -f "$SOURCE" ]; then
    echo 'Die geprüfte Dispatcherquelle fehlt.' >&2
    FAILED=1
fi
if [ ! -d "$WORKER" ] || [ ! -f "$TARGET" ]; then
    echo 'Der aktive Slicing-Worker oder Dispatcher fehlt.' >&2
    FAILED=1
fi

if [ "$FAILED" -eq 0 ]; then
    ACTIVE_JOB=$(find "$WORKER/data/jobs" -maxdepth 1 -type f \( -name '*.queued.json' -o -name '*.slicing.json' \) -print -quit 2>/dev/null)
    if [ -n "$ACTIVE_JOB" ]; then
        echo 'Es läuft oder wartet ein Sliceauftrag. Es wurde nichts verändert.' >&2
        echo "$ACTIVE_JOB"
        FAILED=1
    fi
fi

if [ "$FAILED" -eq 0 ]; then
    SOURCE_SHA=$(sha256sum "$SOURCE" 2>/dev/null | awk '{print $1}')
    if [ "$SOURCE_SHA" != "$EXPECTED_DISPATCHER_SHA" ]; then
        echo 'Die Dispatcher-Prüfsumme stimmt nicht.' >&2
        echo "Erwartet: $EXPECTED_DISPATCHER_SHA" >&2
        echo "Ist:      $SOURCE_SHA" >&2
        FAILED=1
    fi
fi

if [ "$FAILED" -eq 0 ]; then
    sh -n "$SOURCE"
    if [ "$?" -ne 0 ]; then
        echo 'Die Dispatcher-Shellsyntax ist ungültig.' >&2
        FAILED=1
    fi
fi

if [ "$FAILED" -eq 0 ]; then
    cp -a "$TARGET" "$BACKUP/dispatch-job.sh"
    if [ "$?" -ne 0 ]; then
        echo 'Backup des Dispatchers fehlgeschlagen.' >&2
        FAILED=1
    fi
fi

if [ "$FAILED" -eq 0 ]; then
    install -m 0755 "$SOURCE" "$TARGET"
    if [ "$?" -ne 0 ]; then
        echo 'Installation des Dispatchers fehlgeschlagen.' >&2
        FAILED=1
    else
        INSTALLED=1
    fi
fi

if [ "$FAILED" -eq 0 ]; then
    TARGET_SHA=$(sha256sum "$TARGET" 2>/dev/null | awk '{print $1}')
    sh -n "$TARGET"
    SYNTAX_RC=$?
    if [ "$TARGET_SHA" != "$EXPECTED_DISPATCHER_SHA" ] || [ "$SYNTAX_RC" -ne 0 ]; then
        echo 'Live-Prüfung des neuen Dispatchers fehlgeschlagen.' >&2
        echo "Live-SHA: $TARGET_SHA" >&2
        FAILED=1
    fi
fi

if [ "$FAILED" -ne 0 ] && [ "$INSTALLED" -eq 1 ] && [ -f "$BACKUP/dispatch-job.sh" ]; then
    echo 'Rollback des Dispatchers wird ausgeführt.'
    install -m 0755 "$BACKUP/dispatch-job.sh" "$TARGET"
    echo 'Vorheriger Dispatcher wurde wiederhergestellt.'
fi

if [ "$FAILED" -eq 0 ]; then
    LAST_JOB_ID=$(jq -r '.job_id // empty' "$WORKER/last_job.json" 2>/dev/null)
    if [ -n "$LAST_JOB_ID" ]; then
        JOB_OUTPUT="$WORKER/data/output/$LAST_JOB_ID"
        echo "Letzter Job: $LAST_JOB_ID"
        if [ -d "$JOB_OUTPUT" ]; then
            ROOT_GCODE=$(find "$JOB_OUTPUT" -maxdepth 1 -type f -name '*.gcode' -size +0c | sort | head -n 1)
            if [ -z "$ROOT_GCODE" ]; then
                NESTED_GCODE=$(find "$JOB_OUTPUT" -maxdepth 4 -type f -name '*.gcode' -size +0c | sort | head -n 1)
                if [ -n "$NESTED_GCODE" ]; then
                    cp -f "$NESTED_GCODE" "$JOB_OUTPUT/plate_1.gcode"
                    chmod 0644 "$JOB_OUTPUT/plate_1.gcode"
                    echo "Letztes Artefakt repariert: $JOB_OUTPUT/plate_1.gcode"
                else
                    echo 'Der letzte Job enthält keine auffindbare G-Code-Datei.'
                    find "$JOB_OUTPUT" -maxdepth 4 -type f -printf '%p %s Bytes\n' 2>/dev/null | sort
                fi
            else
                if [ "$ROOT_GCODE" != "$JOB_OUTPUT/plate_1.gcode" ]; then
                    cp -f "$ROOT_GCODE" "$JOB_OUTPUT/plate_1.gcode"
                fi
                chmod 0644 "$JOB_OUTPUT/plate_1.gcode"
                echo "Letztes Artefakt ist verfügbar: $JOB_OUTPUT/plate_1.gcode"
            fi
        fi
    fi

    /bin/sh "$WORKER/refresh-state.sh"
    echo 'Workerstatus wurde aktualisiert.'
fi

if [ "$FAILED" -eq 0 ]; then
    echo '============================================================'
    echo 'HOTFIX ERFOLGREICH'
    echo '============================================================'
    echo "Dispatcher-SHA: $EXPECTED_DISPATCHER_SHA"
    echo "Backup:         $BACKUP"
    echo "Log:            $LOG"
else
    echo '============================================================'
    echo 'HOTFIX FEHLGESCHLAGEN'
    echo '============================================================'
    echo "Log: $LOG"
fi

echo 'Terminal bleibt offen.'

[ "$FAILED" -eq 0 ]