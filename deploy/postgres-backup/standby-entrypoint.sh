#!/usr/bin/env bash
set -euo pipefail

if [[ $(id -u) -eq 0 ]]; then
    mkdir -p "$PGDATA"
    chown postgres:postgres "$PGDATA"
    exec gosu postgres "$0" "$@"
fi

replication_secret=${REPLICATION_PASSWORD_FILE:?REPLICATION_PASSWORD_FILE is required}
/usr/local/bin/validate-secrets.sh "$replication_secret" replication_password 32

primary_host=${PRIMARY_HOST:-postgres-primary}
primary_port=${PRIMARY_PORT:-5432}
replication_slot=${REPLICATION_SLOT:-dcim_standby_slot}

if [[ ! "$primary_host" =~ ^[A-Za-z0-9][A-Za-z0-9.-]{0,252}$ ]]; then
    echo "PRIMARY_HOST is invalid" >&2
    exit 64
fi
if [[ ! "$primary_port" =~ ^[0-9]{1,5}$ ]] || ((primary_port < 1 || primary_port > 65535)); then
    echo "PRIMARY_PORT is invalid" >&2
    exit 64
fi
if [[ ! "$replication_slot" =~ ^[a-z0-9_]{1,63}$ ]]; then
    echo "REPLICATION_SLOT is invalid" >&2
    exit 64
fi

if [[ ! -s "$PGDATA/PG_VERSION" ]]; then
    if find "$PGDATA" -mindepth 1 -maxdepth 1 -print -quit | grep -q .; then
        echo "standby data directory must be empty before base backup" >&2
        exit 78
    fi

    pgpass_file=$(mktemp)
    trap 'rm -f "$pgpass_file"' EXIT
    umask 077
    printf '%s:%s:*:dcim_replication:%s\n' \
        "$primary_host" "$primary_port" "$(<"$replication_secret")" >"$pgpass_file"
    export PGPASSFILE=$pgpass_file

    attempts=0
    until pg_isready --host="$primary_host" --port="$primary_port" --username=dcim_replication; do
        attempts=$((attempts + 1))
        if [[ $attempts -ge 30 ]]; then
            echo "primary did not become ready for standby bootstrap" >&2
            exit 75
        fi
        sleep 2
    done

    pg_basebackup \
        --host="$primary_host" \
        --port="$primary_port" \
        --username=dcim_replication \
        --pgdata="$PGDATA" \
        --wal-method=stream \
        --slot="$replication_slot" \
        --write-recovery-conf \
        --checkpoint=fast \
        --progress
fi

exec docker-entrypoint.sh postgres -c config_file=/etc/postgresql/postgresql-standby.conf
