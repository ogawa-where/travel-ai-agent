#!/usr/bin/env bash
# OSRM 初回データ準備スクリプト
# 日本の地図データをダウンロードし、OSRM用に前処理する
#
# 使用方法:
#   ./scripts/setup-osrm.sh
#
# 前提条件:
#   - Docker がインストール済み
#   - docker compose が利用可能
#   - 十分なディスク容量（日本データ: ~1.5GB PBF, 処理後 ~3GB）

set -euo pipefail

DATA_DIR="./osrm-data"
PBF_FILE="japan-latest.osm.pbf"
PBF_URL="https://download.geofabrik.de/asia/${PBF_FILE}"
OSRM_IMAGE="osrm/osrm-backend:latest"

echo "=== OSRM データ準備スクリプト ==="

# 1. データディレクトリ作成
mkdir -p "${DATA_DIR}"

# 2. PBFダウンロード（未取得の場合のみ）
if [ ! -f "${DATA_DIR}/${PBF_FILE}" ]; then
    echo "[1/4] 日本の地図データをダウンロード中..."
    wget -O "${DATA_DIR}/${PBF_FILE}" "${PBF_URL}"
else
    echo "[1/4] PBFファイルは既に存在します: ${DATA_DIR}/${PBF_FILE}"
fi

# 3. OSRM前処理（extract → partition → customize）
echo "[2/4] osrm-extract 実行中..."
docker run --rm -v "$(pwd)/${DATA_DIR}:/data" "${OSRM_IMAGE}" \
    osrm-extract -p /opt/car.lua "/data/${PBF_FILE}"

echo "[3/4] osrm-partition 実行中..."
docker run --rm -v "$(pwd)/${DATA_DIR}:/data" "${OSRM_IMAGE}" \
    osrm-partition "/data/japan-latest.osrm"

echo "[4/4] osrm-customize 実行中..."
docker run --rm -v "$(pwd)/${DATA_DIR}:/data" "${OSRM_IMAGE}" \
    osrm-customize "/data/japan-latest.osrm"

echo ""
echo "=== 前処理完了 ==="
echo ""
echo "処理済みデータを Docker ボリュームにコピーするには:"
echo "  docker volume create osrm_data"
echo "  docker run --rm -v osrm_data:/data -v \$(pwd)/${DATA_DIR}:/src alpine sh -c 'cp /src/japan-latest.osrm* /data/'"
echo ""
echo "または docker-compose.yml の osrm ボリュームを直接マウントに変更:"
echo "  volumes:"
echo "    - ./osrm-data:/data"
