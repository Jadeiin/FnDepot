binary="$payload/slskd"

start_service() {
    credentials="$TRIM_PKGETC/credentials"
    if [ ! -r "$credentials" ]; then
        fail '请先在应用设置中填写 slskd 和 Soulseek 的登录信息。'
    fi
    {
        IFS= read -r SLSKD_USERNAME &&
        IFS= read -r SLSKD_PASSWORD &&
        IFS= read -r SLSKD_SLSK_USERNAME &&
        IFS= read -r SLSKD_SLSK_PASSWORD
    } < "$credentials" || fail 'slskd 登录配置不完整，请在应用设置中重新保存。'
    export SLSKD_USERNAME SLSKD_PASSWORD SLSKD_SLSK_USERNAME SLSKD_SLSK_PASSWORD

    cd "$payload" || return 1
    launch --app-dir "$TRIM_PKGVAR" --http-port "${TRIM_SERVICE_PORT:-5030}"
}
