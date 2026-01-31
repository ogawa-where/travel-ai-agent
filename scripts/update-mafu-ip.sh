#!/bin/bash
# mafu（オーケストレーターサーバー）のIPアドレスを現在のサーバーのIPに更新するスクリプト

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$PROJECT_ROOT/backend/config/ollama_workers.json"

# 現在のサーバーのIPアドレスを取得
get_local_ip() {
    # 複数の方法でIPアドレスを取得を試みる
    local ip=""

    # 方法1: hostname -I (Linux)
    if command -v hostname &> /dev/null; then
        ip=$(hostname -I 2>/dev/null | awk '{print $1}')
    fi

    # 方法2: ip route (Linux)
    if [ -z "$ip" ] && command -v ip &> /dev/null; then
        ip=$(ip route get 1 2>/dev/null | awk '{print $7; exit}')
    fi

    # 方法3: ifconfig (macOS/Linux)
    if [ -z "$ip" ] && command -v ifconfig &> /dev/null; then
        ip=$(ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep -v '127.0.0.1' | head -1)
    fi

    echo "$ip"
}

# 設定ファイルのmafuのIPを更新
update_mafu_ip() {
    local new_ip="$1"
    local old_ip

    if [ ! -f "$CONFIG_FILE" ]; then
        echo "Error: Config file not found: $CONFIG_FILE"
        exit 1
    fi

    # 現在のmafu（transportation）のIPを取得
    old_ip=$(grep -A2 '"transportation"' "$CONFIG_FILE" | grep '"host"' | grep -oE '([0-9]+\.){3}[0-9]+')

    if [ -z "$old_ip" ]; then
        echo "Error: Could not find transportation host in config"
        exit 1
    fi

    echo "Current mafu IP: $old_ip"
    echo "New mafu IP: $new_ip"

    if [ "$old_ip" = "$new_ip" ]; then
        echo "IP address is already up to date."
        exit 0
    fi

    # バックアップを作成
    cp "$CONFIG_FILE" "$CONFIG_FILE.bak"

    # IPアドレスを置換（transportationのhostのみ）
    # sedを使ってtransportationセクションのhostを更新
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s|\"host\": \"$old_ip:11434\"|\"host\": \"$new_ip:11434\"|g" "$CONFIG_FILE"
    else
        # Linux
        sed -i "s|\"host\": \"$old_ip:11434\"|\"host\": \"$new_ip:11434\"|g" "$CONFIG_FILE"
    fi

    # workersセクションのmafuも更新（descriptionにmafuを含む行の前のhostを更新）
    # より正確な置換のためにjqを使用
    if command -v jq &> /dev/null; then
        local temp_file=$(mktemp)
        jq --arg old "$old_ip" --arg new "$new_ip" '
            .workers = [.workers[] | if .description | contains("mafu") then .host = ($new + ":11434") else . end] |
            .search_routing.transportation.host = ($new + ":11434")
        ' "$CONFIG_FILE" > "$temp_file" && mv "$temp_file" "$CONFIG_FILE"
        echo "Updated using jq"
    fi

    echo "Successfully updated mafu IP from $old_ip to $new_ip"
    echo "Backup saved to: $CONFIG_FILE.bak"
}

# メイン処理
main() {
    local new_ip=""

    # 引数でIPが指定されていればそれを使用、なければ自動検出
    if [ -n "$1" ]; then
        new_ip="$1"
    else
        new_ip=$(get_local_ip)
    fi

    if [ -z "$new_ip" ]; then
        echo "Error: Could not determine IP address"
        echo "Usage: $0 [IP_ADDRESS]"
        exit 1
    fi

    # IPアドレスの形式を検証
    if ! [[ "$new_ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "Error: Invalid IP address format: $new_ip"
        exit 1
    fi

    update_mafu_ip "$new_ip"
}

main "$@"
