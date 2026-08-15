#!/usr/bin/env bash
set -euo pipefail

dr_init_enabled=${DCIM_DR_INIT_ENABLED:-false}
case "$dr_init_enabled" in
    true)
        ;;
    false)
        exit 0
        ;;
    *)
        echo "DCIM_DR_INIT_ENABLED must be true or false" >&2
        exit 64
        ;;
esac

replication_secret=${REPLICATION_PASSWORD_FILE:?REPLICATION_PASSWORD_FILE is required}
/usr/local/bin/validate-secrets.sh "$replication_secret" replication_password 32
replication_password=$(<"$replication_secret")

psql --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --set=replication_password="$replication_password" <<'EOSQL'
SELECT format(
    'CREATE ROLE dcim_replication WITH REPLICATION LOGIN PASSWORD %L',
    :'replication_password'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dcim_replication')
\gexec
ALTER ROLE dcim_replication WITH REPLICATION LOGIN PASSWORD :'replication_password';
SELECT pg_create_physical_replication_slot('dcim_standby_slot')
WHERE NOT EXISTS (SELECT 1 FROM pg_replication_slots WHERE slot_name = 'dcim_standby_slot');
EOSQL

printf '%s\n' 'host replication dcim_replication all scram-sha-256' >>"$PGDATA/pg_hba.conf"

stanza=${PGBACKREST_STANZA:-dcim}
/usr/local/bin/pgbackrest-wrapper --stanza="$stanza" stanza-create
/usr/local/bin/pgbackrest-wrapper --stanza="$stanza" check
