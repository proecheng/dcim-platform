ARG POSTGRES_BASE_IMAGE=public.ecr.aws/docker/library/postgres:16.15-bookworm@sha256:60f4761b9035e0b8d5218f701a8c3382f641bf12b1604822574cf5be3baeb537
ARG DEBIAN_MIRROR=http://deb.debian.org/debian
ARG DEBIAN_SECURITY_MIRROR=http://deb.debian.org/debian-security
ARG PGDG_MIRROR=http://apt.postgresql.org/pub/repos/apt

FROM ${POSTGRES_BASE_IMAGE} AS builder

USER root

ARG DEBIAN_MIRROR
ARG DEBIAN_SECURITY_MIRROR
ARG PGDG_MIRROR
ARG TIMESCALEDB_VERSION=2.29.1
ARG TIMESCALEDB_COMMIT=bdc46d313480287d2c21aa50abf405a1493a1769
ARG TIMESCALEDB_SHA256=B0054B6D399268E8ABFE4C64DB846EC843AE93A1CBBA5D5F1811E9198F666212
ARG PGBACKREST_VERSION=2.59.0
ARG PGBACKREST_SHA256=faaf8faa14a6392279654ee216a493fcd07b0c513af4b55fe34faec062cb8875
ARG PGBACKREST_SOURCE_URL=https://github.com/pgbackrest/pgbackrest/releases/download/release/2.59.0/pgbackrest-2.59.0.tar.gz

RUN set -eux; \
    case "$DEBIAN_MIRROR" in http://*|https://*) ;; *) exit 64 ;; esac; \
    case "$DEBIAN_SECURITY_MIRROR" in http://*|https://*) ;; *) exit 64 ;; esac; \
    case "$PGDG_MIRROR" in http://*|https://*) ;; *) exit 64 ;; esac; \
    sed -ri \
        -e "s#http://deb.debian.org/debian-security#${DEBIAN_SECURITY_MIRROR}#g" \
        -e "s#http://deb.debian.org/debian#${DEBIAN_MIRROR}#g" \
        -e "s#http://apt.postgresql.org/pub/repos/apt#${PGDG_MIRROR}#g" \
        /etc/apt/sources.list.d/debian.sources \
        /etc/apt/sources.list.d/pgdg.list; \
    apt-get update \
    && apt-get install -y --no-install-recommends \
        bison \
        build-essential \
        ca-certificates \
        cmake \
        curl \
        flex \
        libbz2-dev \
        libcurl4-openssl-dev \
        libkrb5-dev \
        liblz4-dev \
        libpq-dev \
        libssh2-1-dev \
        libssl-dev \
        libxml2-dev \
        libyaml-dev \
        libzstd-dev \
        meson \
        ninja-build \
        pkg-config \
        postgresql-server-dev-16 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL "https://github.com/timescale/timescaledb/archive/${TIMESCALEDB_COMMIT}.tar.gz" \
        -o /tmp/timescaledb.tar.gz \
    && echo "${TIMESCALEDB_SHA256}  /tmp/timescaledb.tar.gz" | sha256sum -c - \
    && mkdir /tmp/timescaledb \
    && tar -xzf /tmp/timescaledb.tar.gz -C /tmp/timescaledb --strip-components=1 \
    && cd /tmp/timescaledb \
    && ./bootstrap -DREGRESS_CHECKS=OFF -DWARNINGS_AS_ERRORS=OFF \
    && cmake --build build --parallel \
    && DESTDIR=/opt/timescaledb cmake --install build

RUN case "$PGBACKREST_SOURCE_URL" in https://*) ;; *) exit 64 ;; esac \
    && curl -fsSL --retry 5 --retry-delay 2 --retry-all-errors --connect-timeout 30 \
        "${PGBACKREST_SOURCE_URL}" \
        -o /tmp/pgbackrest.tar.gz \
    && echo "${PGBACKREST_SHA256}  /tmp/pgbackrest.tar.gz" | sha256sum -c - \
    && mkdir /tmp/pgbackrest \
    && tar -xzf /tmp/pgbackrest.tar.gz -C /tmp/pgbackrest --strip-components=1 \
    && meson setup /tmp/pgbackrest/build /tmp/pgbackrest --buildtype=release \
    && ninja -C /tmp/pgbackrest/build \
    && DESTDIR=/opt/pgbackrest meson install -C /tmp/pgbackrest/build

FROM ${POSTGRES_BASE_IMAGE}

LABEL org.opencontainers.image.title="DCIM PostgreSQL disaster recovery image" \
      org.opencontainers.image.version="16.15-ts2.29.1-pgb2.59.0" \
      org.opencontainers.image.base.digest="sha256:60f4761b9035e0b8d5218f701a8c3382f641bf12b1604822574cf5be3baeb537"

USER root

ARG DEBIAN_MIRROR
ARG DEBIAN_SECURITY_MIRROR
ARG PGDG_MIRROR

RUN set -eux; \
    case "$DEBIAN_MIRROR" in http://*|https://*) ;; *) exit 64 ;; esac; \
    case "$DEBIAN_SECURITY_MIRROR" in http://*|https://*) ;; *) exit 64 ;; esac; \
    case "$PGDG_MIRROR" in http://*|https://*) ;; *) exit 64 ;; esac; \
    sed -ri \
        -e "s#http://deb.debian.org/debian-security#${DEBIAN_SECURITY_MIRROR}#g" \
        -e "s#http://deb.debian.org/debian#${DEBIAN_MIRROR}#g" \
        -e "s#http://apt.postgresql.org/pub/repos/apt#${PGDG_MIRROR}#g" \
        /etc/apt/sources.list.d/debian.sources \
        /etc/apt/sources.list.d/pgdg.list; \
    apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        libbz2-1.0 \
        libcurl4 \
        liblz4-1 \
        libssh2-1 \
        libssl3 \
        libxml2 \
        libyaml-0-2 \
        libzstd1 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p \
        /etc/pgbackrest \
        /usr/local/share/dcim-dr \
        /var/lib/dcim-dr-status \
        /var/lib/pgbackrest \
        /var/log/pgbackrest \
        /var/spool/pgbackrest \
    && chown -R postgres:postgres \
        /var/lib/dcim-dr-status \
        /var/lib/pgbackrest \
        /var/log/pgbackrest \
        /var/spool/pgbackrest

COPY --from=builder /opt/timescaledb/ /
COPY --from=builder /opt/pgbackrest/ /
COPY deploy/postgres-backup/pgbackrest.conf /etc/pgbackrest/pgbackrest.conf
COPY deploy/postgres-backup/postgresql-primary.conf /etc/postgresql/postgresql-primary.conf
COPY deploy/postgres-backup/postgresql-standby.conf /etc/postgresql/postgresql-standby.conf
COPY deploy/postgres-backup/postgresql-restore.conf /etc/postgresql/postgresql-restore.conf
COPY deploy/postgres-backup/validate-secrets.sh /usr/local/bin/validate-secrets.sh
COPY deploy/postgres-backup/pgbackrest-wrapper /usr/local/bin/pgbackrest-wrapper
COPY deploy/postgres-backup/backup-job.sh /usr/local/bin/backup-job.sh
COPY deploy/postgres-backup/backup-scheduler.sh /usr/local/bin/backup-scheduler.sh
COPY deploy/postgres-backup/backup-healthcheck.sh /usr/local/bin/backup-healthcheck.sh
COPY deploy/postgres-backup/retention-guard.sh /usr/local/bin/retention-guard.sh
COPY deploy/postgres-backup/status-snapshot.sh /usr/local/bin/status-snapshot.sh
COPY deploy/postgres-backup/wal-continuity-check.sh /usr/local/bin/wal-continuity-check.sh
COPY deploy/postgres-backup/postgres-status.sql /usr/local/share/dcim-dr/postgres-status.sql
COPY deploy/postgres-backup/restore-job.sh /usr/local/bin/restore-job.sh
COPY deploy/postgres-backup/restore-entrypoint.sh /usr/local/bin/restore-entrypoint.sh
COPY deploy/postgres-backup/restore-healthcheck.sh /usr/local/bin/restore-healthcheck.sh
COPY deploy/postgres-backup/restore-validate.sh /usr/local/bin/restore-validate.sh
COPY deploy/postgres-backup/database-consistency.sql /usr/local/share/dcim-dr/database-consistency.sql
COPY deploy/postgres-backup/timescaledb-status.sql /usr/local/share/dcim-dr/timescaledb-status.sql
COPY deploy/postgres-backup/expected-schema-tables.txt /usr/local/share/dcim-dr/expected-schema-tables.txt
COPY deploy/postgres-backup/init-primary.sh /docker-entrypoint-initdb.d/20-dcim-replication.sh
COPY deploy/postgres-backup/standby-entrypoint.sh /usr/local/bin/standby-entrypoint.sh

RUN chmod 0755 \
        /usr/local/bin/validate-secrets.sh \
        /usr/local/bin/pgbackrest-wrapper \
        /usr/local/bin/backup-job.sh \
        /usr/local/bin/backup-scheduler.sh \
        /usr/local/bin/backup-healthcheck.sh \
        /usr/local/bin/retention-guard.sh \
        /usr/local/bin/status-snapshot.sh \
        /usr/local/bin/wal-continuity-check.sh \
        /usr/local/bin/restore-job.sh \
        /usr/local/bin/restore-entrypoint.sh \
        /usr/local/bin/restore-healthcheck.sh \
        /usr/local/bin/restore-validate.sh \
        /usr/local/bin/standby-entrypoint.sh \
        /docker-entrypoint-initdb.d/20-dcim-replication.sh \
    && bash -n \
        /usr/local/bin/validate-secrets.sh \
        /usr/local/bin/pgbackrest-wrapper \
        /usr/local/bin/backup-job.sh \
        /usr/local/bin/backup-scheduler.sh \
        /usr/local/bin/backup-healthcheck.sh \
        /usr/local/bin/retention-guard.sh \
        /usr/local/bin/status-snapshot.sh \
        /usr/local/bin/wal-continuity-check.sh \
        /usr/local/bin/restore-job.sh \
        /usr/local/bin/restore-entrypoint.sh \
        /usr/local/bin/restore-healthcheck.sh \
        /usr/local/bin/restore-validate.sh \
        /usr/local/bin/standby-entrypoint.sh \
        /docker-entrypoint-initdb.d/20-dcim-replication.sh

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["postgres"]
