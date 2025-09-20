#!/bin/bash

# #############################################################################
#
# This script backs up the 'uploads' directory and the SQLite '.db' files
# from the remote server to new, timestamped directories on the local machine.
#
# It creates two main folders: 'uploads' and 'db' to store the backups.
#
# Usage:
#   ./backup_uploads.sh
#
# #############################################################################

# --- Configuration ---
REMOTE_USER="sasanktumpati"
REMOTE_HOST="34.4.25.238"

# -- Source Directories on the Server --
REMOTE_UPLOADS_DIR="/home/sasanktumpati/learn-kuch-bhi-back/generated_scenes"   # Trailing slash is important!
# REMOTE_DB_DIR="/home/jagat/portal/databases/" # Trailing slash is important!
# REMOTE_SESS_DIR="/home/jagat/portal/instance/" # Trailing slash is important!


# --- Script Logic ---

# 1. Get the current directory of the script
BACKUP_ROOT_DIR=$(pwd)

# 2. Define parent directories for each backup type
UPLOADS_PARENT_DIR="${BACKUP_ROOT_DIR}/server/generated_scenes"
# DB_PARENT_DIR="${BACKUP_ROOT_DIR}/db"
# SESS_PARENT_DIR="${BACKUP_ROOT_DIR}/instance"

# 3. Create parent directories if they don't exist
mkdir -p "${UPLOADS_PARENT_DIR}"
# mkdir -p "${DB_PARENT_DIR}"

# 4. Create a timestamp for the backup folder name
# Format: ddmmyyyy_HHMMSS (e.g., 13082025_122600)
TIMESTAMP=$(date +"%d%m%Y_%H%M%S")

# 5. Define full destination path for the current backup
LOCAL_UPLOADS_DEST_DIR="${UPLOADS_PARENT_DIR}/uploads_${TIMESTAMP}"
LOCAL_DB_DEST_DIR="${DB_PARENT_DIR}/db_${TIMESTAMP}"
LOCAL_SESS_DEST_DIR="${SESS_PARENT_DIR}/session_${TIMESTAMP}"



# --- Execute Backups ---

# 6. Backup the 'uploads' directory
echo "----------------------------------------------------"
echo "Starting 'uploads' backup..."
echo "  Source: ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_UPLOADS_DIR}"
echo "  Destination: ${LOCAL_UPLOADS_DEST_DIR}"
/usr/bin/rsync -avzr "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_UPLOADS_DIR}" "${LOCAL_UPLOADS_DEST_DIR}"
echo "'uploads' backup complete!"
echo "----------------------------------------------------"


# # 7. Backup the database files
# echo "Starting database files backup..."
# echo "  Source: ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DB_DIR}"
# echo "  Destination: ${LOCAL_DB_DEST_DIR}"
# rsync -avzr "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DB_DIR}" "${LOCAL_DB_DEST_DIR}"
# echo "Database files backup complete!"
# echo "----------------------------------------------------"

# # 7. Backup the database files
# echo "Starting instance files backup..."
# echo "  Source: ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_SESS_DIR}"
# echo "  Destination: ${LOCAL_SESS_DEST_DIR}"
# rsync -avzr "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_SESS_DIR}" "${LOCAL_SESS_DEST_DIR}"
# echo "Instance files backup complete!"
# echo "----------------------------------------------------"
