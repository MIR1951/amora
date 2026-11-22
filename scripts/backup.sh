#!/bin/sh
# Baza va taom rasmlarining zaxira nusxasi.
#
#   ./scripts/backup.sh                 # nusxa olish (standart joy: ./backups)
#   BACKUP_DIR=/var/backups/amora KEEP_DAYS=30 ./scripts/backup.sh
#
# Har kuni o'zi ishlashi uchun (crontab -e):
#   30 3 * * * cd /root/amora && ./scripts/backup.sh >> /var/log/amora-backup.log 2>&1
#
# Nusxalar shu serverning o'zida turadi: disk buzilsa ular ham yo'qoladi. Shuning uchun papkani
# boshqa joyga ham ko'chirib turing (rclone, restic yoki oddiy scp). Tiklash: README, "Zaxira nusxa".
set -eu

cd "$(dirname "$0")/.."
BACKUP_DIR="${BACKUP_DIR:-$PWD/backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
STAMP="$(date +%Y%m%d-%H%M%S)"

umask 077
mkdir -p "$BACKUP_DIR"

# Avval vaqtinchalik nomga yoziladi: yarim yozilgan fayl tayyor nusxa bo'lib ko'rinmasin
docker compose exec -T db pg_dump -U amora -Fc amora > "$BACKUP_DIR/db-$STAMP.dump.tmp"
mv "$BACKUP_DIR/db-$STAMP.dump.tmp" "$BACKUP_DIR/db-$STAMP.dump"

docker compose exec -T api tar -czf - -C /srv/amora/media . > "$BACKUP_DIR/media-$STAMP.tgz.tmp"
mv "$BACKUP_DIR/media-$STAMP.tgz.tmp" "$BACKUP_DIR/media-$STAMP.tgz"

# Eskilari faqat yangisi muvaffaqiyatli olingandan keyin o'chiriladi
find "$BACKUP_DIR" -maxdepth 1 -type f \( -name 'db-*.dump' -o -name 'media-*.tgz' -o -name '*.tmp' \) \
  -mtime "+$KEEP_DAYS" -delete

echo "$(date '+%F %T') zaxira nusxa olindi: $BACKUP_DIR/db-$STAMP.dump, media-$STAMP.tgz"
