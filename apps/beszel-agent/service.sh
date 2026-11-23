binary="$payload/beszel-agent"

start_service() {
    public_key=${beszel_public_key:-}
    hub_url=${beszel_hub_url:-}
    token=${beszel_token:-}
    listen_port=${beszel_listen_port:-}

    case "$public_key" in
        *[![:space:]]*) ;;
        *) fail '请在应用设置中填写 Beszel Hub 公钥。' ;;
    esac

    if [ -n "$hub_url" ] || [ -n "$token" ]; then
        case "$hub_url" in
            *[[:space:]]*) fail '请填写完整的 HTTP 或 HTTPS Hub 地址。' ;;
            http://[!/?#]*|https://[!/?#]*) ;;
            *) fail '请填写完整的 HTTP 或 HTTPS Hub 地址。' ;;
        esac
        case "$token" in
            ''|*[[:space:]]*) fail '请填写 Hub 提供的连接 Token。' ;;
        esac
        export BESZEL_AGENT_HUB_URL="$hub_url" BESZEL_AGENT_TOKEN="$token"
    else
        [ -n "$listen_port" ] || fail '请填写 Hub 地址和 Token，或设置 SSH 监听端口。'
        unset BESZEL_AGENT_HUB_URL BESZEL_AGENT_TOKEN HUB_URL TOKEN
    fi

    if [ -n "$listen_port" ]; then
        case "$listen_port" in
            *[!0-9]*|??????*) fail 'SSH 监听端口必须为 1 到 65535 之间的整数。' ;;
        esac
        if [ "$listen_port" -lt 1 ] || [ "$listen_port" -gt 65535 ]; then
            fail 'SSH 监听端口必须为 1 到 65535 之间的整数。'
        fi
        export BESZEL_AGENT_DISABLE_SSH=false BESZEL_AGENT_LISTEN="$listen_port" BESZEL_AGENT_NETWORK=tcp
    else
        export BESZEL_AGENT_DISABLE_SSH=true
    fi

    export BESZEL_AGENT_KEY="$public_key" BESZEL_AGENT_DATA_DIR="$TRIM_PKGVAR"
    cd "$TRIM_PKGVAR" || return 1
    launch
}
