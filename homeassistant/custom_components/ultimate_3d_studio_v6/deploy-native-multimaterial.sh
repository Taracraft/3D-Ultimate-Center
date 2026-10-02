#!/bin/bash

set +e
set +u
set +o pipefail 2>/dev/null

STAGE="$1"
ROUTER_SHA='be2496b8eca772019ea25696f7ec03857fc387e1414ea991d08268402cbeb597'
PLATE_SHA='a29e778fa907bf5d810a3d5390abf4b900a64f865e779a514fdc85928ae867ec'
MATERIALIZER_SHA='c0ae83b374df0fddcefe24a6741fa66d664f18527236c53ed9a6267d7851f86d'
DISPATCHER_SHA='f6345d104cb2ee16e66c55ff812639526230b26afad289948cafd7d44984a833'

STAMP=$(date +%Y%m%d-%H%M%S)
HA_ROOT='/var/lib/homeassistant/homeassistant'
HA_COMPONENT="$HA_ROOT/custom_components/ultimate_3d_studio_v6"
WORKER='/var/lib/homeassistant/3d-printer-slicing-server'
WORKER_DISPATCHER="$WORKER/dispatch-job.sh"
SOURCE="$STAGE/custom_components/ultimate_3d_studio_v6"
BACKUP="$HA_ROOT/pcc-backups/v6-native-multimaterial/$STAMP"
LOG="$HA_ROOT/pcc-backups/v6-native-multimaterial-deploy-$STAMP.log"
FAILED=0
DEPLOYED=0
ROLLED_BACK=0
CORE_READY=0

mkdir -p "$(dirname "$LOG")"
exec > >(tee -a "$LOG") 2>&1

restart_core() {
    CORE_RESTARTED=0
    if docker inspect homeassistant >/dev/null 2>&1; then
        docker restart homeassistant >/dev/null 2>&1
        if [ "$?" -eq 0 ]; then CORE_RESTARTED=1; fi
    elif command -v ha >/dev/null 2>&1; then
        ha core restart >/dev/null 2>&1
        if [ "$?" -eq 0 ]; then CORE_RESTARTED=1; fi
    fi

    if [ "$CORE_RESTARTED" -ne 1 ]; then
        echo 'Home-Assistant-Core konnte nicht neu gestartet werden.' >&2
        FAILED=1
    fi
}

wait_for_core() {
    CORE_READY=0
    COUNT=1
    while [ "$COUNT" -le 90 ]; do
        STATE='true'
        if docker inspect homeassistant >/dev/null 2>&1; then
            STATE=$(docker inspect -f '{{.State.Running}}' homeassistant 2>/dev/null)
        fi
        CODE=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 3 http://127.0.0.1:8123/api/ 2>/dev/null)
        if [ "$STATE" = 'true' ] && [ -n "$CODE" ] && [ "$CODE" != '000' ]; then
            echo "Home Assistant antwortet wieder mit HTTP $CODE."
            CORE_READY=1
            break
        fi
        sleep 2
        COUNT=$((COUNT + 1))
    done

    if [ "$CORE_READY" -ne 1 ]; then
        echo 'Home Assistant wurde nicht rechtzeitig erreichbar.' >&2
        FAILED=1
    fi
}

backup_file() {
    LIVE_FILE="$1"
    SAVED_FILE="$2"
    mkdir -p "$(dirname "$SAVED_FILE")"
    if [ -e "$LIVE_FILE" ]; then
        cp -a "$LIVE_FILE" "$SAVED_FILE"
        if [ "$?" -ne 0 ]; then FAILED=1; fi
    else
        : > "$SAVED_FILE.missing"
        if [ "$?" -ne 0 ]; then FAILED=1; fi
    fi
}

restore_file() {
    SAVED_FILE="$1"
    LIVE_FILE="$2"
    if [ -f "$SAVED_FILE" ]; then
        cp -a "$SAVED_FILE" "$LIVE_FILE"
    elif [ -f "$SAVED_FILE.missing" ]; then
        rm -f "$LIVE_FILE"
    fi
}

check_hash() {
    EXPECTED_HASH="$1"
    CHECK_FILE="$2"
    ACTUAL_HASH=$(sha256sum "$CHECK_FILE" 2>/dev/null | awk '{print $1}')
    if [ "$ACTUAL_HASH" != "$EXPECTED_HASH" ]; then
        echo "SHA-256 stimmt nicht: $CHECK_FILE" >&2
        echo "Erwartet: $EXPECTED_HASH" >&2
        echo "Ist:      $ACTUAL_HASH" >&2
        FAILED=1
    else
        echo "SHA OK: $CHECK_FILE"
    fi
}

rollback() {
    if [ "$DEPLOYED" -eq 1 ] && [ "$ROLLED_BACK" -eq 0 ]; then
        ROLLED_BACK=1
        echo '============================================================'
        echo 'ROLLBACK'
        echo '============================================================'
        restore_file "$BACKUP/ha/slicer_backend_router.py" "$HA_COMPONENT/slicer_backend_router.py"
        restore_file "$BACKUP/ha/slicer_plate_views_v2.py" "$HA_COMPONENT/slicer_plate_views_v2.py"
        restore_file "$BACKUP/worker/materialize-bambu-multimaterial.py" "$WORKER/materialize-bambu-multimaterial.py"
        restore_file "$BACKUP/worker/dispatch-job.sh" "$WORKER_DISPATCHER"
        chmod 755 "$WORKER_DISPATCHER" "$WORKER/materialize-bambu-multimaterial.py" 2>/dev/null
        echo 'Vorheriger Stand wurde wiederhergestellt.'
        RESTART_FAILURE_STATE=$FAILED
        FAILED=0
        restart_core
        wait_for_core
        FAILED=$RESTART_FAILURE_STATE
        echo "Rollback abgeschlossen: $BACKUP"
    fi
}

echo '============================================================'
echo 'V6 NATIVER MEHRFARBEN-DEPLOY'
echo '============================================================'
echo "Quelle:     $SOURCE"
echo "HA-Modul:   $HA_COMPONENT"
echo "Worker:     $WORKER"
echo "Dispatcher: $WORKER_DISPATCHER"
echo "Backup:     $BACKUP"
echo "Log:        $LOG"

if [ -z "$STAGE" ]; then
    echo 'Staging-Verzeichnis fehlt.' >&2
    FAILED=1
fi
if [ ! -d "$SOURCE" ]; then
    echo "Quellverzeichnis fehlt: $SOURCE" >&2
    FAILED=1
fi
if [ ! -d "$HA_COMPONENT" ]; then
    echo "Home-Assistant-Komponente fehlt: $HA_COMPONENT" >&2
    FAILED=1
fi
if [ ! -d "$WORKER" ]; then
    echo "Worker-Verzeichnis fehlt: $WORKER" >&2
    FAILED=1
fi
if [ ! -f "$WORKER_DISPATCHER" ]; then
    echo "Aktiver Dispatcher fehlt: $WORKER_DISPATCHER" >&2
    FAILED=1
fi
if [ ! -f "$WORKER/server.py" ]; then
    echo "Worker-Server fehlt: $WORKER/server.py" >&2
    FAILED=1
fi

if [ "$FAILED" -eq 0 ]; then
    ACTIVE_JOBS=$(find "$WORKER/data/jobs" -maxdepth 1 -type f \( -name '*.queued.json' -o -name '*.slicing.json' \) -print -quit 2>/dev/null)
    if [ -n "$ACTIVE_JOBS" ]; then
        echo 'Es läuft oder wartet ein Sliceauftrag. Es wurde nichts verändert.' >&2
        echo "$ACTIVE_JOBS"
        FAILED=1
    fi
fi

if [ "$FAILED" -eq 0 ]; then
    check_hash "$ROUTER_SHA" "$SOURCE/slicer_backend_router.py"
    check_hash "$PLATE_SHA" "$SOURCE/slicer_plate_views_v2.py"
    check_hash "$MATERIALIZER_SHA" "$SOURCE/materialize-bambu-multimaterial.py"
    check_hash "$DISPATCHER_SHA" "$SOURCE/dispatch-job-options.sh"
fi

if [ "$FAILED" -eq 0 ]; then
    python3 -m py_compile \
        "$SOURCE/slicer_backend_router.py" \
        "$SOURCE/slicer_plate_views_v2.py" \
        "$SOURCE/materialize-bambu-multimaterial.py"
    if [ "$?" -ne 0 ]; then FAILED=1; fi

    sh -n "$SOURCE/dispatch-job-options.sh"
    if [ "$?" -ne 0 ]; then FAILED=1; fi
fi

if [ "$FAILED" -eq 0 ]; then
    echo 'Quellprüfung erfolgreich.'
    backup_file "$HA_COMPONENT/slicer_backend_router.py" "$BACKUP/ha/slicer_backend_router.py"
    backup_file "$HA_COMPONENT/slicer_plate_views_v2.py" "$BACKUP/ha/slicer_plate_views_v2.py"
    backup_file "$WORKER/materialize-bambu-multimaterial.py" "$BACKUP/worker/materialize-bambu-multimaterial.py"
    backup_file "$WORKER_DISPATCHER" "$BACKUP/worker/dispatch-job.sh"
fi

if [ "$FAILED" -eq 0 ]; then
    DEPLOYED=1
    install -m 0644 "$SOURCE/slicer_backend_router.py" "$HA_COMPONENT/slicer_backend_router.py"
    if [ "$?" -ne 0 ]; then FAILED=1; fi
    install -m 0644 "$SOURCE/slicer_plate_views_v2.py" "$HA_COMPONENT/slicer_plate_views_v2.py"
    if [ "$?" -ne 0 ]; then FAILED=1; fi
    install -m 0755 "$SOURCE/materialize-bambu-multimaterial.py" "$WORKER/materialize-bambu-multimaterial.py"
    if [ "$?" -ne 0 ]; then FAILED=1; fi
    install -m 0755 "$SOURCE/dispatch-job-options.sh" "$WORKER_DISPATCHER"
    if [ "$?" -ne 0 ]; then FAILED=1; fi
fi

if [ "$FAILED" -eq 0 ]; then
    check_hash "$ROUTER_SHA" "$HA_COMPONENT/slicer_backend_router.py"
    check_hash "$PLATE_SHA" "$HA_COMPONENT/slicer_plate_views_v2.py"
    check_hash "$MATERIALIZER_SHA" "$WORKER/materialize-bambu-multimaterial.py"
    check_hash "$DISPATCHER_SHA" "$WORKER_DISPATCHER"
fi

if [ "$FAILED" -eq 0 ]; then
    python3 -m py_compile \
        "$HA_COMPONENT/slicer_backend_router.py" \
        "$HA_COMPONENT/slicer_plate_views_v2.py" \
        "$WORKER/materialize-bambu-multimaterial.py"
    if [ "$?" -ne 0 ]; then FAILED=1; fi

    sh -n "$WORKER_DISPATCHER"
    if [ "$?" -ne 0 ]; then FAILED=1; fi
fi

if [ "$FAILED" -eq 0 ]; then
    echo 'Live-Dateien geprüft. Home Assistant Core wird neu gestartet ...'
    restart_core
    if [ "$FAILED" -eq 0 ]; then wait_for_core; fi
fi

if [ "$FAILED" -ne 0 ]; then
    rollback
    echo '============================================================'
    echo 'DEPLOY FEHLGESCHLAGEN'
    echo '============================================================'
    echo "Log: $LOG"
else
    DEPLOYED=0
    echo '============================================================'
    echo 'DEPLOY ERFOLGREICH'
    echo '============================================================'
    echo "Backup: $BACKUP"
    echo "Log:    $LOG"
    echo 'Neue Sliceaufträge verwenden ausschließlich den nativen Linux-Worker.'
fi

echo 'Terminal bleibt offen.'

[ "$FAILED" -eq 0 ]
