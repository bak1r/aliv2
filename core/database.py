"""ALI v2 SQLite Data Layer — Relational database for all legal tools."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "ali.db"

_local = threading.local()


class AliDB:
    """Thread-safe SQLite database for Ali v2 legal assistant."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = str(db_path or DB_PATH)
        # Ensure data directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ── Connection Management ──────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        # Check if existing connection points to a different DB (e.g. test isolation)
        if hasattr(_local, "conn") and _local.conn is not None:
            if getattr(_local, "conn_path", None) != self.db_path:
                try:
                    _local.conn.close()
                except Exception:
                    pass
                _local.conn = None
        if not hasattr(_local, "conn") or _local.conn is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            _local.conn = conn
            _local.conn_path = self.db_path
        return _local.conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript(_SCHEMA)
        conn.commit()

    # ── Müvekkil ───────────────────────────────────────────────────

    def muvekil_ekle(self, ad: str, telefon: str = "", email: str = "",
                     adres: str = "", tc_no: str = "", notlar: str = "") -> int:
        conn = self._get_conn()
        cur = conn.execute(
            "INSERT INTO muvekkiller (ad, telefon, email, adres, tc_no, notlar) VALUES (?,?,?,?,?,?)",
            (ad, telefon, email, adres, tc_no, notlar),
        )
        conn.commit()
        return cur.lastrowid

    def muvekil_bul(self, arama: str) -> list[dict]:
        conn = self._get_conn()
        q = f"%{arama}%"
        rows = conn.execute(
            "SELECT * FROM muvekkiller WHERE ad LIKE ? OR telefon LIKE ? OR tc_no LIKE ? ORDER BY ad",
            (q, q, q),
        ).fetchall()
        return [dict(r) for r in rows]

    def muvekil_detay(self, muvekil_id: int) -> dict | None:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM muvekkiller WHERE id=?", (muvekil_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["davalar"] = [dict(r) for r in conn.execute(
            "SELECT * FROM davalar WHERE muvekil_id=?", (muvekil_id,)).fetchall()]
        result["vekaletler"] = [dict(r) for r in conn.execute(
            "SELECT * FROM vekaletler WHERE muvekil_id=?", (muvekil_id,)).fetchall()]
        result["notlar"] = [dict(r) for r in conn.execute(
            "SELECT * FROM notlar WHERE muvekil_id=?", (muvekil_id,)).fetchall()]
        return result

    def muvekil_guncelle(self, muvekil_id: int, **kwargs) -> bool:
        allowed = {"ad", "telefon", "email", "adres", "tc_no", "notlar"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            return False
        updates["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [muvekil_id]
        conn = self._get_conn()
        conn.execute(f"UPDATE muvekkiller SET {set_clause} WHERE id=?", values)
        conn.commit()
        return True

    def muvekil_listele(self) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM muvekkiller ORDER BY ad").fetchall()
        return [dict(r) for r in rows]

    def muvekil_bul_by_ad(self, ad: str) -> dict | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM muvekkiller WHERE LOWER(ad)=LOWER(?)", (ad,)).fetchone()
        return dict(row) if row else None

    # ── Dava ───────────────────────────────────────────────────────

    def dava_ekle(self, muvekil_id: int | None, dava_no: str, mahkeme: str = "",
                  dava_turu: str = "", durum: str = "aktif", ozet: str = "",
                  notlar: str = "") -> int:
        conn = self._get_conn()
        cur = conn.execute(
            "INSERT INTO davalar (muvekil_id, dava_no, mahkeme, dava_turu, durum, ozet, notlar) "
            "VALUES (?,?,?,?,?,?,?)",
            (muvekil_id, dava_no, mahkeme, dava_turu, durum, ozet, notlar),
        )
        conn.commit()
        return cur.lastrowid

    def dava_bul(self, arama: str) -> list[dict]:
        conn = self._get_conn()
        q = f"%{arama}%"
        rows = conn.execute(
            "SELECT d.*, m.ad as muvekil_adi FROM davalar d "
            "LEFT JOIN muvekkiller m ON d.muvekil_id=m.id "
            "WHERE d.dava_no LIKE ? OR d.mahkeme LIKE ? OR d.ozet LIKE ? OR m.ad LIKE ? "
            "ORDER BY d.created_at DESC",
            (q, q, q, q),
        ).fetchall()
        return [dict(r) for r in rows]

    def dava_detay(self, dava_id: int) -> dict | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT d.*, m.ad as muvekil_adi, m.telefon as muvekil_telefon "
            "FROM davalar d LEFT JOIN muvekkiller m ON d.muvekil_id=m.id WHERE d.id=?",
            (dava_id,),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["durusmalar"] = [dict(r) for r in conn.execute(
            "SELECT * FROM durusmalar WHERE dava_id=? ORDER BY tarih", (dava_id,)).fetchall()]
        result["tebligatlar"] = [dict(r) for r in conn.execute(
            "SELECT * FROM tebligatlar WHERE dava_id=? ORDER BY created_at DESC", (dava_id,)).fetchall()]
        result["masraflar"] = [dict(r) for r in conn.execute(
            "SELECT * FROM masraflar WHERE dava_id=? ORDER BY tarih DESC", (dava_id,)).fetchall()]
        result["vekaletler"] = [dict(r) for r in conn.execute(
            "SELECT * FROM vekaletler WHERE dava_id=? ORDER BY created_at DESC", (dava_id,)).fetchall()]
        result["zaman_kayitlari"] = [dict(r) for r in conn.execute(
            "SELECT * FROM zaman_kayitlari WHERE dava_id=? ORDER BY baslangic DESC", (dava_id,)).fetchall()]
        result["notlar"] = [dict(r) for r in conn.execute(
            "SELECT * FROM notlar WHERE dava_id=? ORDER BY created_at DESC", (dava_id,)).fetchall()]
        result["hazirlik_maddeleri"] = [dict(r) for r in conn.execute(
            "SELECT * FROM hazirlik_maddeleri WHERE dava_id=? ORDER BY id", (dava_id,)).fetchall()]
        # Totals
        masraf_row = conn.execute(
            "SELECT COALESCE(SUM(tutar),0) as toplam FROM masraflar WHERE dava_id=?", (dava_id,)).fetchone()
        result["toplam_masraf"] = masraf_row["toplam"] if masraf_row else 0
        zaman_row = conn.execute(
            "SELECT COALESCE(SUM(sure_dakika),0) as toplam FROM zaman_kayitlari WHERE dava_id=?",
            (dava_id,)).fetchone()
        result["toplam_sure_dakika"] = zaman_row["toplam"] if zaman_row else 0
        return result

    def dava_guncelle(self, dava_id: int, **kwargs) -> bool:
        allowed = {"muvekil_id", "dava_no", "mahkeme", "dava_turu", "durum", "ozet", "notlar"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            return False
        updates["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [dava_id]
        conn = self._get_conn()
        conn.execute(f"UPDATE davalar SET {set_clause} WHERE id=?", values)
        conn.commit()
        return True

    def dava_listele(self, durum: str | None = None) -> list[dict]:
        conn = self._get_conn()
        if durum:
            rows = conn.execute(
                "SELECT d.*, m.ad as muvekil_adi FROM davalar d "
                "LEFT JOIN muvekkiller m ON d.muvekil_id=m.id WHERE d.durum=? ORDER BY d.created_at DESC",
                (durum,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT d.*, m.ad as muvekil_adi FROM davalar d "
                "LEFT JOIN muvekkiller m ON d.muvekil_id=m.id ORDER BY d.created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def dava_bul_by_no(self, dava_no: str) -> dict | None:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM davalar WHERE dava_no=?", (dava_no,)).fetchone()
        return dict(row) if row else None

    # ── Duruşma ────────────────────────────────────────────────────

    def durusma_ekle(self, dava_id: int | None, tarih: str, saat: str = "",
                     mahkeme: str = "", salon: str = "", notlar: str = "",
                     durum: str = "bekliyor") -> int:
        conn = self._get_conn()
        cur = conn.execute(
            "INSERT INTO durusmalar (dava_id, tarih, saat, mahkeme, salon, notlar, durum) "
            "VALUES (?,?,?,?,?,?,?)",
            (dava_id, tarih, saat, mahkeme, salon, notlar, durum),
        )
        conn.commit()
        return cur.lastrowid

    def yaklasan_durusmalar(self, gun: int = 7) -> list[dict]:
        conn = self._get_conn()
        bugun = datetime.now().strftime("%Y-%m-%d")
        son_gun = (datetime.now() + timedelta(days=gun)).strftime("%Y-%m-%d")
        rows = conn.execute(
            "SELECT du.*, d.dava_no, d.mahkeme as dava_mahkeme, m.ad as muvekil_adi "
            "FROM durusmalar du "
            "LEFT JOIN davalar d ON du.dava_id=d.id "
            "LEFT JOIN muvekkiller m ON d.muvekil_id=m.id "
            "WHERE du.tarih >= ? AND du.tarih <= ? AND du.durum='bekliyor' "
            "ORDER BY du.tarih, du.saat",
            (bugun, son_gun),
        ).fetchall()
        return [dict(r) for r in rows]

    def durusma_guncelle(self, durusma_id: int, **kwargs) -> bool:
        allowed = {"tarih", "saat", "mahkeme", "salon", "notlar", "durum"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            return False
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [durusma_id]
        conn = self._get_conn()
        conn.execute(f"UPDATE durusmalar SET {set_clause} WHERE id=?", values)
        conn.commit()
        return True

    def durusma_sil(self, durusma_id: int) -> bool:
        conn = self._get_conn()
        cur = conn.execute("DELETE FROM durusmalar WHERE id=?", (durusma_id,))
        conn.commit()
        return cur.rowcount > 0

    def durusma_listele(self, dava_id: int | None = None) -> list[dict]:
        conn = self._get_conn()
        if dava_id:
            rows = conn.execute(
                "SELECT du.*, d.dava_no FROM durusmalar du "
                "LEFT JOIN davalar d ON du.dava_id=d.id "
                "WHERE du.dava_id=? ORDER BY du.tarih DESC, du.saat DESC",
                (dava_id,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT du.*, d.dava_no FROM durusmalar du "
                "LEFT JOIN davalar d ON du.dava_id=d.id "
                "ORDER BY du.tarih DESC, du.saat DESC").fetchall()
        return [dict(r) for r in rows]

    def durusma_bul_by_dava_no(self, dava_no: str) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT du.*, d.dava_no FROM durusmalar du "
            "LEFT JOIN davalar d ON du.dava_id=d.id "
            "WHERE d.dava_no=? ORDER BY du.tarih DESC",
            (dava_no,)).fetchall()
        return [dict(r) for r in rows]

    # ── Tebligat ───────────────────────────────────────────────────

    def tebligat_ekle(self, dava_id: int | None, tebligat_turu: str = "normal",
                      gonderim_tarihi: str = "", teblig_tarihi: str = "",
                      yasal_sure_gun: int | None = None, son_gun: str = "",
                      durum: str = "bekliyor", notlar: str = "") -> int:
        conn = self._get_conn()
        cur = conn.execute(
            "INSERT INTO tebligatlar (dava_id, tebligat_turu, gonderim_tarihi, teblig_tarihi, "
            "yasal_sure_gun, son_gun, durum, notlar) VALUES (?,?,?,?,?,?,?,?)",
            (dava_id, tebligat_turu, gonderim_tarihi, teblig_tarihi,
             yasal_sure_gun, son_gun, durum, notlar),
        )
        conn.commit()
        return cur.lastrowid

    def tebligat_guncelle(self, tebligat_id: int, **kwargs) -> bool:
        allowed = {"tebligat_turu", "gonderim_tarihi", "teblig_tarihi",
                    "yasal_sure_gun", "son_gun", "durum", "notlar"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            return False
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [tebligat_id]
        conn = self._get_conn()
        conn.execute(f"UPDATE tebligatlar SET {set_clause} WHERE id=?", values)
        conn.commit()
        return True

    def tebligat_listele(self, dava_id: int | None = None) -> list[dict]:
        conn = self._get_conn()
        if dava_id:
            rows = conn.execute(
                "SELECT t.*, d.dava_no FROM tebligatlar t "
                "LEFT JOIN davalar d ON t.dava_id=d.id "
                "WHERE t.dava_id=? ORDER BY t.created_at DESC",
                (dava_id,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT t.*, d.dava_no FROM tebligatlar t "
                "LEFT JOIN davalar d ON t.dava_id=d.id "
                "ORDER BY t.created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def tebligat_by_dava_no(self, dava_no: str) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT t.*, d.dava_no FROM tebligatlar t "
            "LEFT JOIN davalar d ON t.dava_id=d.id "
            "WHERE d.dava_no=? ORDER BY t.created_at DESC",
            (dava_no,)).fetchall()
        return [dict(r) for r in rows]

    def acil_tebligatlar(self) -> list[dict]:
        conn = self._get_conn()
        bugun = datetime.now().strftime("%Y-%m-%d")
        yedi_gun = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        rows = conn.execute(
            "SELECT t.*, d.dava_no FROM tebligatlar t "
            "LEFT JOIN davalar d ON t.dava_id=d.id "
            "WHERE t.durum != 'iptal' AND ("
            "  (t.son_gun != '' AND t.son_gun <= ?) OR "
            "  (t.son_gun != '' AND t.son_gun <= ? AND t.son_gun >= ?) OR "
            "  (t.durum = 'bekliyor' AND t.son_gun = '')"
            ") ORDER BY t.son_gun",
            (bugun, yedi_gun, bugun),
        ).fetchall()
        return [dict(r) for r in rows]

    def tebligat_sil(self, tebligat_id: int) -> bool:
        conn = self._get_conn()
        cur = conn.execute("DELETE FROM tebligatlar WHERE id=?", (tebligat_id,))
        conn.commit()
        return cur.rowcount > 0

    # ── Masraf ─────────────────────────────────────────────────────

    def masraf_ekle(self, dava_id: int | None, tutar: float, kategori: str = "diger",
                    aciklama: str = "", tarih: str = "") -> int:
        if not tarih:
            tarih = datetime.now().strftime("%Y-%m-%d")
        conn = self._get_conn()
        cur = conn.execute(
            "INSERT INTO masraflar (dava_id, tutar, kategori, aciklama, tarih) VALUES (?,?,?,?,?)",
            (dava_id, tutar, kategori, aciklama, tarih),
        )
        conn.commit()
        return cur.lastrowid

    def masraf_listele(self, dava_id: int | None = None) -> list[dict]:
        conn = self._get_conn()
        if dava_id:
            rows = conn.execute(
                "SELECT ms.*, d.dava_no FROM masraflar ms "
                "LEFT JOIN davalar d ON ms.dava_id=d.id "
                "WHERE ms.dava_id=? ORDER BY ms.tarih DESC",
                (dava_id,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT ms.*, d.dava_no FROM masraflar ms "
                "LEFT JOIN davalar d ON ms.dava_id=d.id "
                "ORDER BY ms.tarih DESC").fetchall()
        return [dict(r) for r in rows]

    def masraf_by_dava_no(self, dava_no: str) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT ms.*, d.dava_no FROM masraflar ms "
            "LEFT JOIN davalar d ON ms.dava_id=d.id "
            "WHERE d.dava_no=? ORDER BY ms.tarih DESC",
            (dava_no,)).fetchall()
        return [dict(r) for r in rows]

    def masraf_raporu(self, dava_id: int | None = None) -> dict:
        conn = self._get_conn()
        where = "WHERE ms.dava_id=?" if dava_id else ""
        params = (dava_id,) if dava_id else ()

        # By category
        kat_rows = conn.execute(
            f"SELECT kategori, SUM(tutar) as toplam, COUNT(*) as adet FROM masraflar ms "
            f"{where} GROUP BY kategori ORDER BY toplam DESC", params).fetchall()

        # By case
        dava_rows = conn.execute(
            f"SELECT d.dava_no, SUM(ms.tutar) as toplam, COUNT(*) as adet FROM masraflar ms "
            f"LEFT JOIN davalar d ON ms.dava_id=d.id {where} GROUP BY ms.dava_id ORDER BY toplam DESC",
            params).fetchall()

        # Total
        toplam_row = conn.execute(
            f"SELECT COALESCE(SUM(tutar),0) as toplam, COUNT(*) as adet FROM masraflar ms {where}",
            params).fetchone()

        return {
            "kategoriler": [dict(r) for r in kat_rows],
            "davalar": [dict(r) for r in dava_rows],
            "genel_toplam": toplam_row["toplam"] if toplam_row else 0,
            "kayit_sayisi": toplam_row["adet"] if toplam_row else 0,
        }

    def masraf_sil(self, masraf_id: int) -> bool:
        conn = self._get_conn()
        cur = conn.execute("DELETE FROM masraflar WHERE id=?", (masraf_id,))
        conn.commit()
        return cur.rowcount > 0

    # ── Vekalet ────────────────────────────────────────────────────

    def vekalet_ekle(self, muvekil_id: int | None, dava_id: int | None = None,
                     vekalet_turu: str = "dava", tarih: str = "",
                     bitis_tarihi: str = "", noter: str = "",
                     yevmiye_no: str = "", durum: str = "aktif",
                     notlar: str = "") -> int:
        conn = self._get_conn()
        cur = conn.execute(
            "INSERT INTO vekaletler (muvekil_id, dava_id, vekalet_turu, tarih, bitis_tarihi, "
            "noter, yevmiye_no, durum, notlar) VALUES (?,?,?,?,?,?,?,?,?)",
            (muvekil_id, dava_id, vekalet_turu, tarih, bitis_tarihi, noter, yevmiye_no, durum, notlar),
        )
        conn.commit()
        return cur.lastrowid

    def vekalet_listele(self, muvekil_id: int | None = None, dava_id: int | None = None) -> list[dict]:
        conn = self._get_conn()
        conditions = []
        params: list = []
        if muvekil_id:
            conditions.append("v.muvekil_id=?")
            params.append(muvekil_id)
        if dava_id:
            conditions.append("v.dava_id=?")
            params.append(dava_id)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        rows = conn.execute(
            f"SELECT v.*, m.ad as muvekil_adi, d.dava_no FROM vekaletler v "
            f"LEFT JOIN muvekkiller m ON v.muvekil_id=m.id "
            f"LEFT JOIN davalar d ON v.dava_id=d.id "
            f"{where} ORDER BY v.created_at DESC", params).fetchall()
        return [dict(r) for r in rows]

    def vekalet_guncelle(self, vekalet_id: int, **kwargs) -> bool:
        allowed = {"vekalet_turu", "tarih", "bitis_tarihi", "noter",
                    "yevmiye_no", "durum", "notlar", "muvekil_id", "dava_id"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            return False
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [vekalet_id]
        conn = self._get_conn()
        conn.execute(f"UPDATE vekaletler SET {set_clause} WHERE id=?", values)
        conn.commit()
        return True

    def vekalet_bul(self, arama: str) -> list[dict]:
        conn = self._get_conn()
        q = f"%{arama}%"
        rows = conn.execute(
            "SELECT v.*, m.ad as muvekil_adi, d.dava_no FROM vekaletler v "
            "LEFT JOIN muvekkiller m ON v.muvekil_id=m.id "
            "LEFT JOIN davalar d ON v.dava_id=d.id "
            "WHERE m.ad LIKE ? OR d.dava_no LIKE ? OR m.tc_no LIKE ? "
            "ORDER BY v.created_at DESC",
            (q, q, q),
        ).fetchall()
        return [dict(r) for r in rows]

    def suresi_dolan_vekaletler(self, gun: int = 30) -> list[dict]:
        conn = self._get_conn()
        bugun = datetime.now().strftime("%Y-%m-%d")
        son_gun = (datetime.now() + timedelta(days=gun)).strftime("%Y-%m-%d")
        rows = conn.execute(
            "SELECT v.*, m.ad as muvekil_adi, d.dava_no FROM vekaletler v "
            "LEFT JOIN muvekkiller m ON v.muvekil_id=m.id "
            "LEFT JOIN davalar d ON v.dava_id=d.id "
            "WHERE v.durum='aktif' AND v.bitis_tarihi != '' AND v.bitis_tarihi <= ? "
            "ORDER BY v.bitis_tarihi",
            (son_gun,),
        ).fetchall()
        return [dict(r) for r in rows]

    def vekalet_sil(self, vekalet_id: int) -> bool:
        conn = self._get_conn()
        cur = conn.execute("DELETE FROM vekaletler WHERE id=?", (vekalet_id,))
        conn.commit()
        return cur.rowcount > 0

    # ── Zaman ──────────────────────────────────────────────────────

    def zaman_baslat(self, dava_id: int | None, aciklama: str = "") -> int:
        conn = self._get_conn()
        cur = conn.execute(
            "INSERT INTO zaman_kayitlari (dava_id, baslangic, aciklama) VALUES (?,?,?)",
            (dava_id, datetime.now().isoformat(), aciklama),
        )
        conn.commit()
        return cur.lastrowid

    def zaman_durdur(self, kayit_id: int) -> dict | None:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM zaman_kayitlari WHERE id=?", (kayit_id,)).fetchone()
        if row is None:
            return None
        r = dict(row)
        if r["bitis"]:
            return r  # Already stopped
        bitis = datetime.now()
        baslangic = datetime.fromisoformat(r["baslangic"])
        sure = int((bitis - baslangic).total_seconds() / 60)
        if sure < 1:
            sure = 1
        conn.execute(
            "UPDATE zaman_kayitlari SET bitis=?, sure_dakika=? WHERE id=?",
            (bitis.isoformat(), sure, kayit_id),
        )
        conn.commit()
        r["bitis"] = bitis.isoformat()
        r["sure_dakika"] = sure
        return r

    def zaman_aktif(self) -> dict | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT zk.*, d.dava_no FROM zaman_kayitlari zk "
            "LEFT JOIN davalar d ON zk.dava_id=d.id "
            "WHERE zk.bitis IS NULL ORDER BY zk.baslangic DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def zaman_raporu(self, dava_id: int | None = None) -> dict:
        conn = self._get_conn()
        where = "WHERE zk.dava_id=? AND" if dava_id else "WHERE"
        params = (dava_id,) if dava_id else ()

        dava_rows = conn.execute(
            f"SELECT d.dava_no, SUM(zk.sure_dakika) as toplam_dakika, COUNT(*) as kayit "
            f"FROM zaman_kayitlari zk LEFT JOIN davalar d ON zk.dava_id=d.id "
            f"{where} zk.bitis IS NOT NULL GROUP BY zk.dava_id ORDER BY toplam_dakika DESC",
            params).fetchall()

        toplam_row = conn.execute(
            f"SELECT COALESCE(SUM(sure_dakika),0) as toplam, COUNT(*) as adet "
            f"FROM zaman_kayitlari zk {where} zk.bitis IS NOT NULL",
            params).fetchone()

        entries = conn.execute(
            f"SELECT zk.*, d.dava_no FROM zaman_kayitlari zk "
            f"LEFT JOIN davalar d ON zk.dava_id=d.id "
            f"{where} zk.bitis IS NOT NULL ORDER BY zk.baslangic DESC",
            params).fetchall()

        return {
            "davalar": [dict(r) for r in dava_rows],
            "toplam_dakika": toplam_row["toplam"] if toplam_row else 0,
            "kayit_sayisi": toplam_row["adet"] if toplam_row else 0,
            "kayitlar": [dict(r) for r in entries],
        }

    def zaman_listele(self, dava_id: int | None = None) -> list[dict]:
        conn = self._get_conn()
        if dava_id:
            rows = conn.execute(
                "SELECT zk.*, d.dava_no FROM zaman_kayitlari zk "
                "LEFT JOIN davalar d ON zk.dava_id=d.id "
                "WHERE zk.dava_id=? ORDER BY zk.baslangic DESC",
                (dava_id,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT zk.*, d.dava_no FROM zaman_kayitlari zk "
                "LEFT JOIN davalar d ON zk.dava_id=d.id "
                "ORDER BY zk.baslangic DESC").fetchall()
        return [dict(r) for r in rows]

    # ── Not ────────────────────────────────────────────────────────

    def not_ekle(self, metin: str, etiket: str = "normal",
                 dava_id: int | None = None, muvekil_id: int | None = None) -> int:
        conn = self._get_conn()
        cur = conn.execute(
            "INSERT INTO notlar (dava_id, muvekil_id, metin, etiket) VALUES (?,?,?,?)",
            (dava_id, muvekil_id, metin, etiket),
        )
        conn.commit()
        return cur.lastrowid

    def not_ara(self, arama: str) -> list[dict]:
        conn = self._get_conn()
        q = f"%{arama}%"
        rows = conn.execute(
            "SELECT n.*, d.dava_no, m.ad as muvekil_adi FROM notlar n "
            "LEFT JOIN davalar d ON n.dava_id=d.id "
            "LEFT JOIN muvekkiller m ON n.muvekil_id=m.id "
            "WHERE n.metin LIKE ? OR n.etiket LIKE ? ORDER BY n.created_at DESC",
            (q, q),
        ).fetchall()
        return [dict(r) for r in rows]

    def not_listele(self) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT n.*, d.dava_no, m.ad as muvekil_adi FROM notlar n "
            "LEFT JOIN davalar d ON n.dava_id=d.id "
            "LEFT JOIN muvekkiller m ON n.muvekil_id=m.id "
            "ORDER BY n.created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def not_sil(self, not_id: int) -> bool:
        conn = self._get_conn()
        cur = conn.execute("DELETE FROM notlar WHERE id=?", (not_id,))
        conn.commit()
        return cur.rowcount > 0

    # ── Hazırılk Maddeleri ─────────────────────────────────────────

    def hazirlik_ekle(self, dava_id: int | None, durusma_id: int | None,
                      madde: str, tamamlandi: int = 0) -> int:
        conn = self._get_conn()
        cur = conn.execute(
            "INSERT INTO hazirlik_maddeleri (dava_id, durusma_id, madde, tamamlandi) VALUES (?,?,?,?)",
            (dava_id, durusma_id, madde, tamamlandi),
        )
        conn.commit()
        return cur.lastrowid

    def hazirlik_listele(self, dava_id: int | None = None,
                         durusma_id: int | None = None) -> list[dict]:
        conn = self._get_conn()
        conditions = []
        params: list = []
        if dava_id:
            conditions.append("h.dava_id=?")
            params.append(dava_id)
        if durusma_id:
            conditions.append("h.durusma_id=?")
            params.append(durusma_id)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        rows = conn.execute(
            f"SELECT h.*, d.dava_no FROM hazirlik_maddeleri h "
            f"LEFT JOIN davalar d ON h.dava_id=d.id "
            f"{where} ORDER BY h.id", params).fetchall()
        return [dict(r) for r in rows]

    def hazirlik_guncelle(self, madde_id: int, tamamlandi: int) -> bool:
        conn = self._get_conn()
        conn.execute("UPDATE hazirlik_maddeleri SET tamamlandi=? WHERE id=?",
                      (tamamlandi, madde_id))
        conn.commit()
        return True

    def hazirlik_sil(self, madde_id: int | None = None,
                     dava_id: int | None = None, durusma_id: int | None = None) -> int:
        conn = self._get_conn()
        if madde_id:
            cur = conn.execute("DELETE FROM hazirlik_maddeleri WHERE id=?", (madde_id,))
        elif durusma_id:
            cur = conn.execute("DELETE FROM hazirlik_maddeleri WHERE durusma_id=?", (durusma_id,))
        elif dava_id:
            cur = conn.execute("DELETE FROM hazirlik_maddeleri WHERE dava_id=?", (dava_id,))
        else:
            return 0
        conn.commit()
        return cur.rowcount

    # ── Dashboard ──────────────────────────────────────────────────

    def gunluk_ozet(self) -> dict:
        conn = self._get_conn()
        bugun = datetime.now().strftime("%Y-%m-%d")
        yedi_gun = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        otuz_gun = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

        # Today's hearings
        bugunki = conn.execute(
            "SELECT du.*, d.dava_no, m.ad as muvekil_adi FROM durusmalar du "
            "LEFT JOIN davalar d ON du.dava_id=d.id "
            "LEFT JOIN muvekkiller m ON d.muvekil_id=m.id "
            "WHERE du.tarih=? AND du.durum='bekliyor' ORDER BY du.saat",
            (bugun,)).fetchall()

        # Upcoming notifications (7 days)
        acil_teb = conn.execute(
            "SELECT t.*, d.dava_no FROM tebligatlar t "
            "LEFT JOIN davalar d ON t.dava_id=d.id "
            "WHERE t.durum != 'iptal' AND t.son_gun != '' AND t.son_gun <= ? "
            "ORDER BY t.son_gun",
            (yedi_gun,)).fetchall()

        # Expiring powers of attorney (30 days)
        dolan_vek = conn.execute(
            "SELECT v.*, m.ad as muvekil_adi FROM vekaletler v "
            "LEFT JOIN muvekkiller m ON v.muvekil_id=m.id "
            "WHERE v.durum='aktif' AND v.bitis_tarihi != '' AND v.bitis_tarihi <= ? "
            "ORDER BY v.bitis_tarihi",
            (otuz_gun,)).fetchall()

        # Active timer
        aktif_zaman = conn.execute(
            "SELECT zk.*, d.dava_no FROM zaman_kayitlari zk "
            "LEFT JOIN davalar d ON zk.dava_id=d.id "
            "WHERE zk.bitis IS NULL LIMIT 1").fetchone()

        # Recent notes
        son_notlar = conn.execute(
            "SELECT * FROM notlar ORDER BY created_at DESC LIMIT 5").fetchall()

        # Active case count
        aktif_dava = conn.execute(
            "SELECT COUNT(*) as c FROM davalar WHERE durum='aktif'").fetchone()

        return {
            "tarih": bugun,
            "bugunki_durusmalar": [dict(r) for r in bugunki],
            "acil_tebligatlar": [dict(r) for r in acil_teb],
            "dolan_vekaletler": [dict(r) for r in dolan_vek],
            "aktif_zamanlayici": dict(aktif_zaman) if aktif_zaman else None,
            "son_notlar": [dict(r) for r in son_notlar],
            "aktif_dava_sayisi": aktif_dava["c"] if aktif_dava else 0,
        }

    # ── Full Client View ───────────────────────────────────────────

    def muvekil_dosya(self, muvekil_id_or_name) -> dict | None:
        conn = self._get_conn()
        if isinstance(muvekil_id_or_name, int):
            row = conn.execute("SELECT * FROM muvekkiller WHERE id=?",
                               (muvekil_id_or_name,)).fetchone()
        else:
            row = conn.execute("SELECT * FROM muvekkiller WHERE LOWER(ad) LIKE LOWER(?)",
                               (f"%{muvekil_id_or_name}%",)).fetchone()
        if row is None:
            return None
        m = dict(row)
        mid = m["id"]

        # All cases
        davalar = conn.execute(
            "SELECT * FROM davalar WHERE muvekil_id=? ORDER BY created_at DESC",
            (mid,)).fetchall()
        m["davalar"] = [dict(d) for d in davalar]

        dava_ids = [d["id"] for d in davalar]
        if not dava_ids:
            m["durusmalar"] = []
            m["tebligatlar"] = []
            m["masraflar"] = []
            m["zaman_kayitlari"] = []
            m["hazirlik_maddeleri"] = []
            m["toplam_masraf"] = 0
        else:
            placeholders = ",".join("?" * len(dava_ids))
            m["durusmalar"] = [dict(r) for r in conn.execute(
                f"SELECT du.*, d.dava_no FROM durusmalar du "
                f"LEFT JOIN davalar d ON du.dava_id=d.id "
                f"WHERE du.dava_id IN ({placeholders}) ORDER BY du.tarih DESC",
                dava_ids).fetchall()]
            m["tebligatlar"] = [dict(r) for r in conn.execute(
                f"SELECT t.*, d.dava_no FROM tebligatlar t "
                f"LEFT JOIN davalar d ON t.dava_id=d.id "
                f"WHERE t.dava_id IN ({placeholders}) ORDER BY t.created_at DESC",
                dava_ids).fetchall()]
            masraflar = conn.execute(
                f"SELECT ms.*, d.dava_no FROM masraflar ms "
                f"LEFT JOIN davalar d ON ms.dava_id=d.id "
                f"WHERE ms.dava_id IN ({placeholders}) ORDER BY ms.tarih DESC",
                dava_ids).fetchall()
            m["masraflar"] = [dict(r) for r in masraflar]
            m["toplam_masraf"] = sum(r["tutar"] for r in masraflar)
            m["zaman_kayitlari"] = [dict(r) for r in conn.execute(
                f"SELECT zk.*, d.dava_no FROM zaman_kayitlari zk "
                f"LEFT JOIN davalar d ON zk.dava_id=d.id "
                f"WHERE zk.dava_id IN ({placeholders}) ORDER BY zk.baslangic DESC",
                dava_ids).fetchall()]
            m["hazirlik_maddeleri"] = [dict(r) for r in conn.execute(
                f"SELECT h.*, d.dava_no FROM hazirlik_maddeleri h "
                f"LEFT JOIN davalar d ON h.dava_id=d.id "
                f"WHERE h.dava_id IN ({placeholders}) ORDER BY h.id",
                dava_ids).fetchall()]

        m["vekaletler"] = [dict(r) for r in conn.execute(
            "SELECT * FROM vekaletler WHERE muvekil_id=? ORDER BY created_at DESC",
            (mid,)).fetchall()]
        m["notlar"] = [dict(r) for r in conn.execute(
            "SELECT * FROM notlar WHERE muvekil_id=? ORDER BY created_at DESC",
            (mid,)).fetchall()]

        return m

    # ── Migration ──────────────────────────────────────────────────

    def migrate_from_json(self):
        """Import existing JSON data files into SQLite tables."""
        data_dir = Path(self.db_path).parent
        migrated = []

        # Clients
        clients_file = data_dir / "clients.json"
        if clients_file.exists():
            try:
                clients = json.loads(clients_file.read_text(encoding="utf-8"))
                for c in clients:
                    self.muvekil_ekle(
                        ad=c.get("ad_soyad", ""),
                        telefon=c.get("telefon", ""),
                        email=c.get("email", ""),
                        notlar=c.get("dava_ozeti", ""),
                    )
                migrated.append(f"clients: {len(clients)}")
            except Exception as e:
                migrated.append(f"clients: HATA - {e}")

        # Court calendar
        cal_file = data_dir / "court_calendar.json"
        if cal_file.exists():
            try:
                events = json.loads(cal_file.read_text(encoding="utf-8"))
                for ev in events:
                    # Convert date format
                    tarih = ev.get("tarih", "")
                    try:
                        dt = datetime.strptime(tarih, "%d.%m.%Y")
                        tarih_iso = dt.strftime("%Y-%m-%d")
                    except ValueError:
                        tarih_iso = tarih
                    self.durusma_ekle(
                        dava_id=None,
                        tarih=tarih_iso,
                        saat=ev.get("saat", ""),
                        mahkeme=ev.get("mahkeme", ""),
                        notlar=ev.get("aciklama", ""),
                    )
                migrated.append(f"court_calendar: {len(events)}")
            except Exception as e:
                migrated.append(f"court_calendar: HATA - {e}")

        # Tebligatlar
        teb_file = data_dir / "tebligatlar.json"
        if teb_file.exists():
            try:
                tebligatlar = json.loads(teb_file.read_text(encoding="utf-8"))
                for t in tebligatlar:
                    self.tebligat_ekle(
                        dava_id=None,
                        tebligat_turu=t.get("tebligat_turu", "normal"),
                        gonderim_tarihi=t.get("gonderim_tarihi", ""),
                        teblig_tarihi=t.get("tebellug_tarihi", ""),
                        son_gun=t.get("son_gun", ""),
                        durum=t.get("durum", "bekliyor"),
                        notlar=t.get("aciklama", ""),
                    )
                migrated.append(f"tebligatlar: {len(tebligatlar)}")
            except Exception as e:
                migrated.append(f"tebligatlar: HATA - {e}")

        # Masraflar
        mas_file = data_dir / "masraflar.json"
        if mas_file.exists():
            try:
                masraflar = json.loads(mas_file.read_text(encoding="utf-8"))
                for m in masraflar:
                    tarih = m.get("tarih", "")
                    try:
                        dt = datetime.strptime(tarih, "%d.%m.%Y")
                        tarih_iso = dt.strftime("%Y-%m-%d")
                    except ValueError:
                        tarih_iso = tarih
                    self.masraf_ekle(
                        dava_id=None,
                        tutar=m.get("tutar", 0),
                        kategori=m.get("kategori", "diger"),
                        aciklama=m.get("aciklama", ""),
                        tarih=tarih_iso,
                    )
                migrated.append(f"masraflar: {len(masraflar)}")
            except Exception as e:
                migrated.append(f"masraflar: HATA - {e}")

        # Vekaletler
        vek_file = data_dir / "vekaletler.json"
        if vek_file.exists():
            try:
                vekaletler = json.loads(vek_file.read_text(encoding="utf-8"))
                for v in vekaletler:
                    # Try to find muvekil by name
                    muvekil = self.muvekil_bul_by_ad(v.get("muvekil", ""))
                    mid = muvekil["id"] if muvekil else None
                    self.vekalet_ekle(
                        muvekil_id=mid,
                        vekalet_turu=v.get("vekalet_turu", "dava"),
                        tarih=v.get("vekalet_tarihi", ""),
                        bitis_tarihi=v.get("bitis_tarihi", ""),
                        noter=v.get("noter", ""),
                        durum=v.get("durum", "aktif"),
                        notlar=v.get("aciklama", ""),
                    )
                migrated.append(f"vekaletler: {len(vekaletler)}")
            except Exception as e:
                migrated.append(f"vekaletler: HATA - {e}")

        # Notes
        notes_file = data_dir / "notes.json"
        if notes_file.exists():
            try:
                notes = json.loads(notes_file.read_text(encoding="utf-8"))
                for n in notes:
                    self.not_ekle(
                        metin=n.get("text", ""),
                        etiket=n.get("tag", "normal"),
                    )
                migrated.append(f"notes: {len(notes)}")
            except Exception as e:
                migrated.append(f"notes: HATA - {e}")

        # Durusma hazirlik
        haz_file = data_dir / "durusma_hazirlik.json"
        if haz_file.exists():
            try:
                hazirliklar = json.loads(haz_file.read_text(encoding="utf-8"))
                for h in hazirliklar:
                    for m in h.get("maddeler", []):
                        self.hazirlik_ekle(
                            dava_id=None,
                            durusma_id=None,
                            madde=m.get("madde", ""),
                            tamamlandi=1 if m.get("tamamlandi") else 0,
                        )
                migrated.append(f"hazirlik: {len(hazirliklar)}")
            except Exception as e:
                migrated.append(f"hazirlik: HATA - {e}")

        # Timekeeper
        tk_file = data_dir / "timekeeper.json"
        if tk_file.exists():
            try:
                tk_data = json.loads(tk_file.read_text(encoding="utf-8"))
                entries = tk_data.get("entries", [])
                for e in entries:
                    conn = self._get_conn()
                    conn.execute(
                        "INSERT INTO zaman_kayitlari (dava_id, baslangic, bitis, sure_dakika, aciklama) "
                        "VALUES (?,?,?,?,?)",
                        (None, e.get("start_time", ""), e.get("end_time", ""),
                         int(e.get("duration_seconds", 0) / 60),
                         e.get("description", "")),
                    )
                    conn.commit()
                migrated.append(f"timekeeper: {len(entries)}")
            except Exception as e:
                migrated.append(f"timekeeper: HATA - {e}")

        return migrated


# ── Schema ─────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS muvekkiller (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad TEXT NOT NULL,
    telefon TEXT,
    email TEXT,
    adres TEXT,
    tc_no TEXT,
    notlar TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS davalar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    muvekil_id INTEGER,
    dava_no TEXT,
    mahkeme TEXT,
    dava_turu TEXT,
    durum TEXT DEFAULT 'aktif',
    ozet TEXT,
    notlar TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (muvekil_id) REFERENCES muvekkiller(id)
);

CREATE TABLE IF NOT EXISTS durusmalar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dava_id INTEGER,
    tarih TEXT NOT NULL,
    saat TEXT,
    mahkeme TEXT,
    salon TEXT,
    notlar TEXT,
    durum TEXT DEFAULT 'bekliyor',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dava_id) REFERENCES davalar(id)
);

CREATE TABLE IF NOT EXISTS tebligatlar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dava_id INTEGER,
    tebligat_turu TEXT,
    gonderim_tarihi TEXT,
    teblig_tarihi TEXT,
    yasal_sure_gun INTEGER,
    son_gun TEXT,
    durum TEXT DEFAULT 'bekliyor',
    notlar TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dava_id) REFERENCES davalar(id)
);

CREATE TABLE IF NOT EXISTS masraflar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dava_id INTEGER,
    tutar REAL NOT NULL,
    kategori TEXT,
    aciklama TEXT,
    tarih TEXT DEFAULT (date('now')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dava_id) REFERENCES davalar(id)
);

CREATE TABLE IF NOT EXISTS vekaletler (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    muvekil_id INTEGER,
    dava_id INTEGER,
    vekalet_turu TEXT,
    tarih TEXT,
    bitis_tarihi TEXT,
    noter TEXT,
    yevmiye_no TEXT,
    durum TEXT DEFAULT 'aktif',
    notlar TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (muvekil_id) REFERENCES muvekkiller(id),
    FOREIGN KEY (dava_id) REFERENCES davalar(id)
);

CREATE TABLE IF NOT EXISTS zaman_kayitlari (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dava_id INTEGER,
    baslangic TEXT NOT NULL,
    bitis TEXT,
    sure_dakika INTEGER,
    aciklama TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dava_id) REFERENCES davalar(id)
);

CREATE TABLE IF NOT EXISTS notlar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dava_id INTEGER,
    muvekil_id INTEGER,
    metin TEXT NOT NULL,
    etiket TEXT DEFAULT 'normal',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dava_id) REFERENCES davalar(id),
    FOREIGN KEY (muvekil_id) REFERENCES muvekkiller(id)
);

CREATE TABLE IF NOT EXISTS hazirlik_maddeleri (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dava_id INTEGER,
    durusma_id INTEGER,
    madde TEXT NOT NULL,
    tamamlandi INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dava_id) REFERENCES davalar(id),
    FOREIGN KEY (durusma_id) REFERENCES durusmalar(id)
);
"""


# ── Singleton ──────────────────────────────────────────────────────

_db: AliDB | None = None


def get_db() -> AliDB:
    """Return the singleton AliDB instance."""
    global _db
    if _db is None:
        _db = AliDB()
    return _db
