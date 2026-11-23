binary="$payload/Kavita"

start_service() {
    config="$TRIM_PKGVAR/config"
    runtime="$TRIM_PKGTMP/kavita-runtime"
    mkdir -p "$config" || return 1
    if [ ! -f "$config/appsettings.json" ] && [ ! -f "$config/appsettings-init.json" ]; then
        cp "$payload/config/appsettings-init.json" "$config/" || return 1
    fi

    # Kavita loads its assets and writable config relative to its working directory.
    rm -rf "$runtime" || return 1
    mkdir "$runtime" || return 1
    for asset in "$payload"/*; do
        if [ "${asset##*/}" != config ]; then
            ln -s "$asset" "$runtime/${asset##*/}" || return 1
        fi
    done
    ln -s "$config" "$runtime/config" || return 1
    cd "$runtime" || return 1
    launch
}
