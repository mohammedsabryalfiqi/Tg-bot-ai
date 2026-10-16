import sqlite3
import zipfile

from scripts.backup_data import create_backup


def test_backup_includes_primary_and_admin_databases_and_uploads(tmp_path):
    storage = tmp_path / "storage"
    storage.mkdir()
    for name, content in (("smartel.db", "root"), ("smartel.tenant-501.db", "admin")):
        conn = sqlite3.connect(storage / name)
        conn.execute("CREATE TABLE sample(value TEXT)")
        conn.execute("INSERT INTO sample VALUES(?)", (content,))
        conn.commit()
        conn.close()
    upload = storage / "uploads" / "tenant-501" / "offer.pdf"
    upload.parent.mkdir(parents=True)
    upload.write_bytes(b"private tenant upload")

    archive = create_backup(storage, tmp_path / "external-backups")
    with zipfile.ZipFile(archive) as zf:
        assert "smartel.db" in zf.namelist()
        assert "smartel.tenant-501.db" in zf.namelist()
        assert zf.read("uploads/tenant-501/offer.pdf") == b"private tenant upload"
        admin_db = tmp_path / "admin-copy.db"
        admin_db.write_bytes(zf.read("smartel.tenant-501.db"))
    conn = sqlite3.connect(admin_db)
    assert conn.execute("SELECT value FROM sample").fetchone()[0] == "admin"
    conn.close()
