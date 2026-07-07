#!/bin/bash

# --- Configuration ---
# [Local Source]
LOCAL_HOST="127.0.0.1"
LOCAL_DB="crawler_sentiment_analysis"
LOCAL_TABLE="article_dataset"
LOCAL_USER="root"
LOCAL_PASS="rootpass"

# [Remote Target]
REMOTE_HOST="34.22.104.188"
REMOTE_PORT="3306"
REMOTE_DB="crawler_sentiment_analysis"
REMOTE_TABLE="article_dataset_local" # 여기에 넣을 예정
REMOTE_USER="root"
REMOTE_PASS="rootpass"

DUMP_FILE="migration_dump.sql"

# --- Step 1: Dump Local Table ---
# --no-create-info: CREATE TABLE 문 제외 (이미 Target에 테이블이 있거나, 데이터만 넣을 때 유용)
# --complete-insert: 컬럼명을 명시하여 INSERT 문 생성 (테이블 구조가 약간 달라도 안전)
# --skip-extended-insert: 가독성을 위해 한 줄씩 Insert (대용량이면 제거하여 속도 향상)
echo ">>> [1/3] Dumping table '${LOCAL_TABLE}' from Local..."
mysqldump -u "${LOCAL_USER}" -p"${LOCAL_PASS}" -h "${LOCAL_HOST}" \
  --no-create-info \
  --complete-insert \
  --single-transaction \
  "${LOCAL_DB}" "${LOCAL_TABLE}" > "${DUMP_FILE}"

# --- Step 2: Rename Table in SQL File ---
# sed를 사용하여 INSERT INTO `source_table` 구문을 INSERT INTO `target_table_v2`로 변경
echo ">>> [2/3] Renaming table to '${REMOTE_TABLE}' in dump file..."
# Mac/Linux 호환성을 위해 sed 문법 주의 (Linux 기준)
sed -i "s/\`${LOCAL_TABLE}\`/\`${REMOTE_TABLE}\`/g" "${DUMP_FILE}"

# --- Step 3: Import to Remote Server ---
echo ">>> [3/3] Importing to Remote Server (${REMOTE_HOST})..."
mysql -h "${REMOTE_HOST}" -P "${REMOTE_PORT}" -u "${REMOTE_USER}" -p"${REMOTE_PASS}" \
  "${REMOTE_DB}" < "${DUMP_FILE}"

echo ">>> Migration Complete!"
# rm "${DUMP_FILE}" # (Optional) 임시 파일 삭제

