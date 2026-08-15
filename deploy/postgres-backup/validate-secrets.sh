#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
    echo "usage: validate-secrets.sh <file> <name> <minimum-length>" >&2
    exit 64
fi

secret_file=$1
secret_name=$2
minimum_length=$3

if [[ ! -f "$secret_file" || ! -r "$secret_file" ]]; then
    echo "required secret file is missing or unreadable: ${secret_name}" >&2
    exit 78
fi

secret_value=$(<"$secret_file")
normalized=$(printf '%s' "$secret_value" | tr '[:upper:]' '[:lower:]')

if [[ ${#secret_value} -lt $minimum_length ]]; then
    echo "required secret is too short: ${secret_name}" >&2
    exit 78
fi

case "$normalized" in
    *placeholder*|*required*|*change-this*|*example*|*password*)
        echo "placeholder secret is forbidden: ${secret_name}" >&2
        exit 78
        ;;
esac
