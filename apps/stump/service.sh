binary="$payload/stump_server"

start_service() {
    export STUMP_CONFIG_DIR="$TRIM_PKGVAR/config"
    export STUMP_CLIENT_DIR="$payload/client"
    export STUMP_PDFIUM_PATH="$payload/runtime/lib/libpdfium.so"
    export STUMP_PORT="${TRIM_SERVICE_PORT:-10801}"

    cd "$payload" || return 1
    launch
}
