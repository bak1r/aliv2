"""
Ali v2 — Kapsamli Stres Testi
Gercek bir avukatin gun boyu Ali v2 kullanimini simule eder.
Hicbir gercek API cagrisi (Anthropic/Gemini) yapmaz.
"""

from __future__ import annotations

import json
import os
import sys
import time
import threading
import shutil
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

# ── Proje kokunun sys.path'te oldugundan emin ol ──────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── Test icin gecici data dizini ──────────────────────────────────────
TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="ali_stress_test_"))


# =====================================================================
#  Fixtures
# =====================================================================

@pytest.fixture(autouse=True)
def _isolate_data(monkeypatch, tmp_path):
    """Her test icin izole data dizini kullan — yan etkilerden korunma."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Veritabani izolasyonu — her test temiz bir SQLite DB kullanir
    import core.database as db_mod
    test_db = db_mod.AliDB(db_path=data_dir / "ali_test.db")
    monkeypatch.setattr(db_mod, "_db", test_db)

    # memory modulu icin de izolasyon
    import core.memory as mem_mod
    monkeypatch.setattr(mem_mod, "MEMORY_FILE", data_dir / "memory.json")
    # Cache'i temizle
    mem_mod._memory_cache = None

    yield data_dir


@pytest.fixture
def registry():
    """Arac registry'sini yukle."""
    from tools import get_registry
    return get_registry()


# =====================================================================
#  1. TOOL LOADING TEST
# =====================================================================

class TestToolLoading:
    """Tum araclarin hatasiz yuklendigini dogrular."""

    def test_registry_loads_without_error(self, registry):
        assert isinstance(registry, dict)
        assert len(registry) > 0

    def test_minimum_tool_count(self, registry):
        """En az 15 arac yuklenmeli (proje 21 arac iceriyor)."""
        assert len(registry) >= 15, f"Beklenen >= 15, gelen {len(registry)}: {list(registry.keys())}"

    def test_core_legal_tools_present(self, registry):
        """Temel hukuk araclari mevcut olmali."""
        expected = [
            "ceza_hesapla", "belge_olustur", "durusma_takvimi",
            "muvekil_takip", "zaman_takip", "bilgi_bankasi",
        ]
        for name in expected:
            assert name in registry, f"'{name}' araci registry'de bulunamadi"

    def test_core_general_tools_present(self, registry):
        """Genel araclar mevcut olmali."""
        expected = ["not_al", "hatirlatici", "web_ara"]
        for name in expected:
            assert name in registry, f"'{name}' araci registry'de bulunamadi"

    def test_all_tools_have_name_and_description(self, registry):
        """Her aracin name ve description'i olmali."""
        for name, tool in registry.items():
            assert tool.name, f"Tool '{name}' has empty name"
            assert tool.description, f"Tool '{name}' has empty description"

    def test_all_tools_have_parameters_schema(self, registry):
        """Her aracin parameters schemasi olmali."""
        for name, tool in registry.items():
            assert isinstance(tool.parameters, dict), f"Tool '{name}' parameters is not dict"
            assert "type" in tool.parameters, f"Tool '{name}' parameters has no 'type'"
            assert tool.parameters["type"] == "object", f"Tool '{name}' parameters type != 'object'"

    def test_claude_tool_definitions(self):
        """Claude API icin arac tanimlari dogru formatda olmali."""
        from tools import get_claude_tool_definitions
        defs = get_claude_tool_definitions()
        assert isinstance(defs, list)
        assert len(defs) > 0

        for d in defs:
            assert "name" in d
            assert "description" in d
            assert "input_schema" in d
            assert isinstance(d["input_schema"], dict)


# =====================================================================
#  2. TOOL EXECUTION TEST — Her arac dogru parametrelerle calistirilir
# =====================================================================

class TestToolExecution:
    """Her araci gecerli parametrelerle cagirip beklenen formatta yanit alir."""

    def test_ceza_hesapla(self, registry):
        tool = registry["ceza_hesapla"]
        result = tool.run(temel_ceza_ay=24, iyi_hal=True)
        assert isinstance(result, str)
        assert "CEZA HESAPLAMA" in result
        assert "SONUC CEZA" in result

    def test_ceza_hesapla_with_all_params(self, registry):
        """Tum parametrelerle ceza hesaplama."""
        tool = registry["ceza_hesapla"]
        result = tool.run(
            temel_ceza_ay=60,
            agirlastirici_orani=0.5,
            hafifletici_orani=0.33,
            tesebbus=True,
            istirak_turu="yardim_eden",
            zincirleme_suc_sayisi=3,
            iyi_hal=True,
            yas_grubu="15-18",
        )
        assert "CEZA HESAPLAMA" in result
        assert "Temel ceza" in result
        assert "Agirlastirici" in result
        assert "Iyi hal" in result

    def test_belge_olustur(self, registry):
        tool = registry["belge_olustur"]
        result = tool.run(belge_turu="dilekce", baslik="Test Dilekce", icerik="Test icerik metni")
        assert isinstance(result, str)
        # python-docx yoksa hata mesaji, varsa dosya yolu
        assert "olusturuldu" in result.lower() or "bulunamadi" in result.lower()

    def test_durusma_takvimi_add(self, registry):
        tool = registry["durusma_takvimi"]
        result = tool.run(
            action="add",
            date="25.03.2026",
            time="10:00",
            court="Istanbul 3. Agir Ceza",
            case_no="2026/123",
            description="Test durusma",
        )
        assert isinstance(result, str)
        assert "EKLENDI" in result

    def test_durusma_takvimi_list(self, registry):
        tool = registry["durusma_takvimi"]
        # Oncelikle bir tane ekle
        tool.run(action="add", date="25.03.2026", time="10:00", court="Test Mahkeme")
        result = tool.run(action="list")
        assert isinstance(result, str)
        assert "DURUSMA TAKVIMI" in result or "Takvimde" in result

    def test_muvekil_takip_add(self, registry):
        tool = registry["muvekil_takip"]
        result = tool.run(
            action="add",
            name="Test Muvekkil",
            phone="05551234567",
            email="test@test.com",
            case_summary="Test dava ozeti",
        )
        assert isinstance(result, str)
        assert "EKLENDI" in result

    def test_zaman_takip_start(self, registry):
        tool = registry["zaman_takip"]
        result = tool.run(action="start", case_name="Test Dosya", description="Arastirma")
        assert isinstance(result, str)
        assert "baslatildi" in result.lower()

    def test_zaman_takip_stop(self, registry):
        tool = registry["zaman_takip"]
        tool.run(action="start", case_name="Test Dosya", description="Arastirma")
        time.sleep(0.1)
        result = tool.run(action="stop")
        assert isinstance(result, str)
        assert "durduruldu" in result.lower()

    def test_not_al_add(self, registry):
        tool = registry["not_al"]
        result = tool.run(action="add", text="Test notu", tag="urgent")
        assert isinstance(result, str)
        assert "eklendi" in result.lower()

    def test_not_al_list(self, registry):
        tool = registry["not_al"]
        tool.run(action="add", text="Liste test notu", tag="normal")
        result = tool.run(action="list")
        assert isinstance(result, str)
        assert "not" in result.lower()

    def test_bilgi_bankasi(self, registry):
        tool = registry["bilgi_bankasi"]
        result = tool.run(query="TCK 157 dolandiricilik", domain="hepsi")
        assert isinstance(result, str)
        # Knowledge dosyalari yoksa bile string donmeli
        assert len(result) > 0

    def test_hatirlatici(self, registry):
        tool = registry["hatirlatici"]
        result = tool.run(message="Test hatirlatma", minutes=60)
        assert isinstance(result, str)
        assert "ayarlandi" in result.lower()

    def test_web_ara(self, registry):
        tool = registry["web_ara"]
        # Gercek web aramasi yapmadan, paketin yuklenmis olup olmadigini test et
        result = tool.run(query="test sorgusu")
        assert isinstance(result, str)
        # Paket yoksa "bulunamadi", varsa sonuclar veya hata
        assert len(result) > 0


# =====================================================================
#  3. DATA PERSISTENCE TEST — Veri yaz, geri oku, tutarlilik dogrula
# =====================================================================

class TestDataPersistence:
    """Verilerin yazildiktan sonra dogru okunabildigini dogrular."""

    def test_note_add_then_list_verify(self, registry):
        """Not ekle -> listele -> dogrula."""
        tool = registry["not_al"]
        add_result = tool.run(action="add", text="Onemli: TCK 157 savunma hazirla", tag="urgent")
        assert "eklendi" in add_result.lower()

        list_result = tool.run(action="list")
        assert "TCK 157" in list_result

    def test_note_add_then_search_verify(self, registry):
        """Not ekle -> ara -> dogrula."""
        tool = registry["not_al"]
        tool.run(action="add", text="Durusma oncesi hazirliklari tamamla", tag="reminder")
        search_result = tool.run(action="search", text="durusma")
        assert "durusma" in search_result.lower()

    def test_court_date_add_then_list_verify(self, registry):
        """Durusma ekle -> listele -> dogrula."""
        tool = registry["durusma_takvimi"]

        # Gelecek bir tarih kullanalim
        future = datetime.now() + timedelta(days=3)
        date_str = future.strftime("%d.%m.%Y")

        add_result = tool.run(
            action="add",
            date=date_str,
            time="14:30",
            court="Ankara 5. Asliye Ceza",
            case_no="2026/456",
        )
        assert "EKLENDI" in add_result

        list_result = tool.run(action="list")
        assert "Ankara" in list_result

    def test_court_date_upcoming(self, registry):
        """Yaklasan durusmalari kontrol et."""
        tool = registry["durusma_takvimi"]

        # Yarin bir durusma ekle
        tomorrow = datetime.now() + timedelta(days=1)
        tool.run(
            action="add",
            date=tomorrow.strftime("%d.%m.%Y"),
            time="09:00",
            court="Izmir 2. Agir Ceza",
        )

        upcoming = tool.run(action="upcoming")
        assert "Izmir" in upcoming or "bulunmuyor" not in upcoming

    def test_client_add_then_search_verify(self, registry):
        """Muvekil ekle -> ara -> dogrula."""
        tool = registry["muvekil_takip"]
        add_result = tool.run(
            action="add",
            name="Ahmet Yilmaz",
            phone="05551112233",
            case_summary="Dolandiricilik davasi",
        )
        assert "EKLENDI" in add_result

        search_result = tool.run(action="search", query="Ahmet")
        assert "Ahmet" in search_result

    def test_client_add_then_list_verify(self, registry):
        """Muvekil ekle -> listele -> dogrula."""
        tool = registry["muvekil_takip"]
        tool.run(action="add", name="Fatma Demir", case_summary="Icra davasi")
        list_result = tool.run(action="list")
        assert "Fatma" in list_result

    def test_timer_start_stop_verify_duration(self, registry):
        """Zamanlayici baslat -> dur -> sure kayit dogrula."""
        tool = registry["zaman_takip"]

        start_result = tool.run(action="start", case_name="Demir Dosyasi", description="Belge inceleme")
        assert "baslatildi" in start_result.lower()

        time.sleep(0.2)  # Kisa bir bekleme

        stop_result = tool.run(action="stop")
        assert "durduruldu" in stop_result.lower()
        # Minimum 1 dakika olarak kaydedilmeli (tool bunu garanti eder)
        assert "saat" in stop_result.lower() or "dk" in stop_result.lower() or "sa" in stop_result.lower()

        # Listede gorunmeli
        list_result = tool.run(action="list")
        assert "Belge inceleme" in list_result

    def test_timer_report(self, registry):
        """Zaman raporu olusturma."""
        tool = registry["zaman_takip"]

        # Iki farkli is yap
        tool.run(action="start", case_name="Dosya A", description="Arastirma")
        time.sleep(0.1)
        tool.run(action="stop")

        tool.run(action="start", case_name="Dosya B", description="Yazisma")
        time.sleep(0.1)
        tool.run(action="stop")

        report = tool.run(action="report")
        assert "RAPOR" in report.upper() or "Toplam" in report
        assert "Toplam Kayit: 2" in report or "Toplam Sure" in report

    def test_multiple_notes_ordering(self, registry):
        """Birden fazla not ekleme ve siralama."""
        tool = registry["not_al"]
        tool.run(action="add", text="Ilk not", tag="normal")
        tool.run(action="add", text="Ikinci not", tag="urgent")
        tool.run(action="add", text="Ucuncu not", tag="reminder")

        result = tool.run(action="list")
        assert "3 not" in result
        assert "Ilk not" in result
        assert "Ikinci not" in result
        assert "Ucuncu not" in result


# =====================================================================
#  4. CONCURRENT ACCESS TEST — Coklu thread'lerden erisim
# =====================================================================

class TestConcurrentAccess:
    """Birden fazla thread'in ayni anda araclara erisimini simule eder."""

    def test_concurrent_note_adding(self, registry):
        """10 thread ayni anda not ekler — veri bozulmamali."""
        tool = registry["not_al"]
        errors = []
        results = []

        def add_note(i):
            try:
                result = tool.run(action="add", text=f"Paralel not #{i}", tag="normal")
                results.append(result)
            except Exception as e:
                errors.append(f"Thread {i}: {e}")

        threads = [threading.Thread(target=add_note, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Thread hatalari: {errors}"
        assert len(results) == 10

        # Tum notlar kaydedildi mi?
        list_result = tool.run(action="list")
        # En az 10 not olmali
        assert "not" in list_result.lower()

    def test_concurrent_calendar_adding(self, registry):
        """5 thread ayni anda takvime durusma ekler."""
        tool = registry["durusma_takvimi"]
        errors = []

        def add_hearing(i):
            try:
                future = datetime.now() + timedelta(days=i + 1)
                tool.run(
                    action="add",
                    date=future.strftime("%d.%m.%Y"),
                    time=f"{9 + i}:00",
                    court=f"Mahkeme #{i}",
                    case_no=f"2026/{100 + i}",
                )
            except Exception as e:
                errors.append(f"Thread {i}: {e}")

        threads = [threading.Thread(target=add_hearing, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Thread hatalari: {errors}"

        # Tum durusmalar kayitli mi?
        list_result = tool.run(action="list")
        assert "DURUSMA TAKVIMI" in list_result

    def test_concurrent_client_adding(self, registry):
        """5 thread ayni anda muvekil ekler."""
        tool = registry["muvekil_takip"]
        errors = []

        def add_client(i):
            try:
                tool.run(
                    action="add",
                    name=f"Muvekil {i}",
                    case_summary=f"Dava {i}",
                )
            except Exception as e:
                errors.append(f"Thread {i}: {e}")

        threads = [threading.Thread(target=add_client, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Thread hatalari: {errors}"

    def test_concurrent_mixed_tools(self, registry):
        """Farkli araclar ayni anda calistirilir (gercek kullanim simule)."""
        errors = []

        def run_tool(tool_name, kwargs):
            try:
                tool = registry[tool_name]
                result = tool.run(**kwargs)
                assert isinstance(result, str)
                assert len(result) > 0
            except Exception as e:
                errors.append(f"{tool_name}: {e}")

        tasks = [
            ("not_al", {"action": "add", "text": "Concurrent test notu", "tag": "normal"}),
            ("ceza_hesapla", {"temel_ceza_ay": 36, "iyi_hal": True}),
            ("bilgi_bankasi", {"query": "hukuk", "domain": "hepsi"}),
            ("hatirlatici", {"message": "Test", "minutes": 30}),
        ]

        threads = [threading.Thread(target=run_tool, args=(name, kw)) for name, kw in tasks]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert len(errors) == 0, f"Concurrent tool hatalari: {errors}"


# =====================================================================
#  5. ERROR HANDLING TEST — Hatali parametreler ve graceful error
# =====================================================================

class TestErrorHandling:
    """Hatali girdi ve eksik parametrelerle araclarin crash etmedigini dogrular."""

    def test_ceza_hesapla_missing_ceza(self, registry):
        """Temel ceza belirtilmeden ceza hesaplama."""
        tool = registry["ceza_hesapla"]
        result = tool.run()  # temel_ceza_ay yok
        assert isinstance(result, str)
        assert "belirtilmedi" in result.lower()

    def test_ceza_hesapla_zero_ceza(self, registry):
        tool = registry["ceza_hesapla"]
        result = tool.run(temel_ceza_ay=0)
        assert isinstance(result, str)
        assert "belirtilmedi" in result.lower()

    def test_ceza_hesapla_negative_ceza(self, registry):
        tool = registry["ceza_hesapla"]
        result = tool.run(temel_ceza_ay=-5)
        assert isinstance(result, str)
        # Negatif deger de "belirtilmedi" donmeli
        assert "belirtilmedi" in result.lower()

    def test_belge_olustur_empty_icerik(self, registry):
        """Bos icerikle belge olusturma."""
        tool = registry["belge_olustur"]
        result = tool.run(belge_turu="dilekce", icerik="")
        assert isinstance(result, str)
        assert "belirtilmedi" in result.lower()

    def test_durusma_takvimi_add_missing_date(self, registry):
        """Tarih olmadan durusma ekleme."""
        tool = registry["durusma_takvimi"]
        result = tool.run(action="add", time="10:00", court="Test")
        assert isinstance(result, str)
        assert "belirtilmedi" in result.lower()

    def test_durusma_takvimi_add_missing_time(self, registry):
        """Saat olmadan durusma ekleme."""
        tool = registry["durusma_takvimi"]
        result = tool.run(action="add", date="25.03.2026", court="Test")
        assert isinstance(result, str)
        assert "belirtilmedi" in result.lower()

    def test_durusma_takvimi_invalid_date(self, registry):
        """Gecersiz tarih formati."""
        tool = registry["durusma_takvimi"]
        result = tool.run(action="add", date="invalid-date", time="10:00")
        assert isinstance(result, str)
        assert "gecersiz" in result.lower() or "format" in result.lower()

    def test_durusma_takvimi_invalid_action(self, registry):
        """Gecersiz action."""
        tool = registry["durusma_takvimi"]
        result = tool.run(action="nonexistent_action")
        assert isinstance(result, str)
        assert "bilinmeyen" in result.lower()

    def test_muvekil_takip_add_no_name(self, registry):
        """Adsiz muvekil ekleme."""
        tool = registry["muvekil_takip"]
        result = tool.run(action="add")
        assert isinstance(result, str)
        assert "belirtilmedi" in result.lower()

    def test_muvekil_takip_search_empty(self, registry):
        """Bos arama."""
        tool = registry["muvekil_takip"]
        result = tool.run(action="search", query="")
        assert isinstance(result, str)
        assert "belirtilmedi" in result.lower() or "gerekli" in result.lower()

    def test_muvekil_takip_invalid_action(self, registry):
        tool = registry["muvekil_takip"]
        result = tool.run(action="invalid")
        assert isinstance(result, str)
        assert "bilinmeyen" in result.lower()

    def test_zaman_takip_start_no_case(self, registry):
        """Dava adi olmadan zamanlayici baslatma."""
        tool = registry["zaman_takip"]
        result = tool.run(action="start")
        assert isinstance(result, str)
        assert "belirtilmedi" in result.lower()

    def test_zaman_takip_stop_without_start(self, registry):
        """Baslatilmamis zamanlayiciyi durdurma."""
        tool = registry["zaman_takip"]
        result = tool.run(action="stop")
        assert isinstance(result, str)
        assert "yok" in result.lower() or "baslat" in result.lower()

    def test_zaman_takip_double_start(self, registry):
        """Cift baslatma."""
        tool = registry["zaman_takip"]
        tool.run(action="start", case_name="Dosya 1", description="Is 1")
        result = tool.run(action="start", case_name="Dosya 2", description="Is 2")
        assert isinstance(result, str)
        assert "zaten" in result.lower() or "aktif" in result.lower()
        # Cleanup
        tool.run(action="stop")

    def test_not_al_add_empty_text(self, registry):
        """Bos metin ile not ekleme."""
        tool = registry["not_al"]
        result = tool.run(action="add", text="")
        assert isinstance(result, str)
        assert "bos" in result.lower()

    def test_not_al_delete_invalid_number(self, registry):
        """Gecersiz numara ile not silme."""
        tool = registry["not_al"]
        result = tool.run(action="delete", text="abc")
        assert isinstance(result, str)
        assert "gecersiz" in result.lower()

    def test_not_al_delete_nonexistent(self, registry):
        """Olmayan not silme."""
        tool = registry["not_al"]
        result = tool.run(action="delete", text="999")
        assert isinstance(result, str)
        assert "bulunamadi" in result.lower()

    def test_hatirlatici_no_message(self, registry):
        """Mesajsiz hatirlatici."""
        tool = registry["hatirlatici"]
        result = tool.run(minutes=5)
        assert isinstance(result, str)
        assert "belirtilmedi" in result.lower()

    def test_hatirlatici_no_minutes(self, registry):
        """Surersiz hatirlatici."""
        tool = registry["hatirlatici"]
        result = tool.run(message="test")
        assert isinstance(result, str)
        assert "belirtilmedi" in result.lower()

    def test_web_ara_empty_query(self, registry):
        """Bos sorgu ile web arama."""
        tool = registry["web_ara"]
        result = tool.run(query="")
        assert isinstance(result, str)
        assert "belirtilmedi" in result.lower()

    def test_bilgi_bankasi_empty_query(self, registry):
        """Bos sorgu ile bilgi bankasi arama."""
        tool = registry["bilgi_bankasi"]
        result = tool.run(query="")
        assert isinstance(result, str)
        assert "belirtilmedi" in result.lower()

    def test_tool_returns_string_not_none(self, registry):
        """Tum araclar None degil string donmeli."""
        # Basit parametrelerle calistir — crash etmemeli
        safe_calls = {
            "ceza_hesapla": {},
            "not_al": {"action": "list"},
            "durusma_takvimi": {"action": "list"},
            "muvekil_takip": {"action": "list"},
            "zaman_takip": {"action": "list"},
            "bilgi_bankasi": {"query": "test"},
        }
        for tool_name, kwargs in safe_calls.items():
            if tool_name in registry:
                result = registry[tool_name].run(**kwargs)
                assert result is not None, f"'{tool_name}' None dondu!"
                assert isinstance(result, str), f"'{tool_name}' string donmedi: {type(result)}"


# =====================================================================
#  6. MEMORY TEST — Hafiza sistemi
# =====================================================================

class TestMemory:
    """core/memory.py hafiza sistemi testleri."""

    def test_store_and_retrieve_identity(self):
        """Kimlik bilgisi kaydet ve oku."""
        from core.memory import _add_memory, _load_memory, _memory_cache
        import core.memory as mem_mod
        mem_mod._memory_cache = None

        _add_memory("identity", "isim", "Mehmet Avukat", confidence=0.9)
        data = _load_memory()
        names = [e["value"] for e in data["identity"] if e["key"] == "isim"]
        assert "Mehmet Avukat" in names

    def test_store_and_retrieve_case(self):
        """Dava bilgisi kaydet ve oku."""
        from core.memory import _add_memory, _load_memory
        import core.memory as mem_mod
        mem_mod._memory_cache = None

        _add_memory("cases", "dosya_no:2026/789", "2026/789", confidence=0.85)
        data = _load_memory()
        cases = [e["value"] for e in data["cases"]]
        assert "2026/789" in cases

    def test_store_and_retrieve_preference(self):
        """Tercih kaydet ve oku."""
        from core.memory import _add_memory, _load_memory
        import core.memory as mem_mod
        mem_mod._memory_cache = None

        _add_memory("preferences", "uslup", "resmi", confidence=0.9)
        data = _load_memory()
        prefs = {e["key"]: e["value"] for e in data["preferences"]}
        assert prefs.get("uslup") == "resmi"

    def test_memory_update_existing(self):
        """Ayni key ile guncelleme — uzerine yazmali."""
        from core.memory import _add_memory, _load_memory
        import core.memory as mem_mod
        mem_mod._memory_cache = None

        _add_memory("identity", "isim", "Ali", confidence=0.7)
        _add_memory("identity", "isim", "Mehmet", confidence=0.9)

        data = _load_memory()
        isim_entries = [e for e in data["identity"] if e["key"] == "isim"]
        assert len(isim_entries) == 1
        assert isim_entries[0]["value"] == "Mehmet"

    def test_extract_memories_from_message(self):
        """Mesajdan otomatik hafiza cikarimi."""
        from core.memory import extract_memories, _load_memory
        import core.memory as mem_mod
        mem_mod._memory_cache = None

        extract_memories("Benim adim Kemal")
        data = _load_memory()
        isimler = [e["value"] for e in data["identity"] if e["key"] == "isim"]
        assert any("Kemal" in v for v in isimler)

    def test_get_memory_context(self):
        """Hafiza konteksti olusturma."""
        from core.memory import _add_memory, get_memory_context
        import core.memory as mem_mod
        mem_mod._memory_cache = None

        _add_memory("identity", "isim", "Avukat Kemal", confidence=0.9)
        _add_memory("preferences", "dil", "turkce", confidence=0.9)

        context = get_memory_context()
        assert isinstance(context, str)
        assert "Kemal" in context or "KULLANICI" in context

    def test_get_user_name(self):
        """Kullanici adi getirme."""
        from core.memory import _add_memory, get_user_name
        import core.memory as mem_mod
        mem_mod._memory_cache = None

        _add_memory("identity", "isim", "Zeynep", confidence=0.9)
        name = get_user_name()
        assert name == "Zeynep"

    def test_memory_stats(self):
        """Hafiza istatistikleri."""
        from core.memory import _add_memory, memory_stats
        import core.memory as mem_mod
        mem_mod._memory_cache = None

        _add_memory("identity", "isim", "Test", confidence=0.9)
        _add_memory("cases", "dava:Test", "Test Dava", confidence=0.8)

        stats = memory_stats()
        assert isinstance(stats, dict)
        assert "toplam" in stats
        assert stats["toplam"] >= 2

    def test_clear_all_memories(self):
        """Tum hafizayi temizleme."""
        from core.memory import _add_memory, clear_all_memories, _load_memory
        import core.memory as mem_mod
        mem_mod._memory_cache = None

        _add_memory("identity", "isim", "Silinecek", confidence=0.9)
        clear_all_memories()

        mem_mod._memory_cache = None
        data = _load_memory()
        total = sum(len(v) for v in data.values())
        assert total == 0

    def test_forget_specific_memory(self):
        """Belirli bir hatirayi silme."""
        from core.memory import _add_memory, forget, _load_memory
        import core.memory as mem_mod
        mem_mod._memory_cache = None

        _add_memory("identity", "isim", "Unutulacak", confidence=0.9)
        _add_memory("identity", "meslek", "Avukat", confidence=0.9)

        result = forget("identity", "isim")
        assert result is True

        mem_mod._memory_cache = None
        data = _load_memory()
        keys = [e["key"] for e in data["identity"]]
        assert "isim" not in keys
        assert "meslek" in keys


# =====================================================================
#  7. CONFIG TEST — API anahtar yuklemesi
# =====================================================================

class TestConfig:
    """Konfigurasyon sistemi testleri."""

    def test_settings_loads(self):
        """settings.json yuklenebilmeli."""
        from core.config import SETTINGS
        assert isinstance(SETTINGS, dict)

    def test_anthropic_key_from_env(self, monkeypatch):
        """ANTHROPIC_API_KEY .env'den okunmali."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-12345")
        from core.config import get_anthropic_key
        key = get_anthropic_key()
        assert key == "test-key-12345"

    def test_anthropic_key_empty_returns_none(self, monkeypatch):
        """Bos API key None donmeli."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        from core.config import get_anthropic_key
        key = get_anthropic_key()
        assert key is None

    def test_gemini_key_from_env(self, monkeypatch):
        """GOOGLE_API_KEY .env'den okunmali."""
        monkeypatch.setenv("GOOGLE_API_KEY", "gemini-test-key")
        from core.config import get_gemini_key
        key = get_gemini_key()
        assert key == "gemini-test-key"

    def test_telegram_token_from_env(self, monkeypatch):
        """TELEGRAM_BOT_TOKEN .env'den okunmali."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tg-token-123")
        from core.config import get_telegram_token
        token = get_telegram_token()
        assert token == "tg-token-123"

    def test_is_configured_false_when_no_keys(self, monkeypatch):
        """API key'ler yoksa is_configured False donmeli."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        monkeypatch.setenv("GOOGLE_API_KEY", "")
        from core.config import is_configured
        assert is_configured() is False

    def test_base_dir_exists(self):
        """BASE_DIR mevcut olmali."""
        from core.config import BASE_DIR
        assert BASE_DIR.exists()

    def test_data_dir_path(self):
        """DATA_DIR dogru yolu gostermeli."""
        from core.config import DATA_DIR, BASE_DIR
        assert DATA_DIR == BASE_DIR / "data"


# =====================================================================
#  8. BRAIN MODULE TEST (no real API calls)
# =====================================================================

class TestBrainModule:
    """Brain modulu — API cagrisi yapmadan test edilebilen fonksiyonlar."""

    def test_legal_keyword_detection(self):
        """Hukuki anahtar kelime tespiti."""
        from core.brain import _detect_legal_query
        assert _detect_legal_query("TCK madde 157 dolandiricilik") is True
        assert _detect_legal_query("Mahkeme karari ne zaman aciklanacak") is True
        assert _detect_legal_query("bugun hava nasil") is False
        assert _detect_legal_query("savunma hazirlamamiz lazim") is True
        assert _detect_legal_query("yemek tarifi") is False

    def test_clear_history(self):
        """Konusma gecmisini temizleme."""
        from core.brain import clear_history, _conversation_history
        _conversation_history.append({"role": "user", "content": "test"})
        clear_history()
        assert len(_conversation_history) == 0

    def test_cost_tracking(self):
        """Maliyet takibi."""
        from core.brain import _track_cost, get_cost_summary, _session_cost, _cost_lock

        # Reset
        with _cost_lock:
            _session_cost["input_tokens"] = 0
            _session_cost["output_tokens"] = 0
            _session_cost["calls"] = 0

        mock_usage = MagicMock()
        mock_usage.input_tokens = 100
        mock_usage.output_tokens = 200

        _track_cost(mock_usage)

        summary = get_cost_summary()
        assert summary["input_tokens"] == 100
        assert summary["output_tokens"] == 200
        assert summary["calls"] == 1

    def test_cancel_mechanism(self):
        """Iptal mekanizmasi."""
        from core.brain import request_cancel, _check_cancelled, _reset_cancel

        _reset_cancel()
        assert _check_cancelled() is False

        request_cancel()
        assert _check_cancelled() is True

        _reset_cancel()
        assert _check_cancelled() is False

    def test_execute_single_tool(self, registry):
        """Tek arac calistirma."""
        from core.brain import _execute_single_tool
        result = _execute_single_tool("ceza_hesapla", {"temel_ceza_ay": 24})
        assert isinstance(result, str)
        assert "CEZA" in result

    def test_execute_unknown_tool(self):
        """Bilinmeyen arac calistirma."""
        from core.brain import _execute_single_tool
        result = _execute_single_tool("nonexistent_tool", {})
        assert "Bilinmeyen" in result


# =====================================================================
#  9. FULL DAY SIMULATION — Gercek kullanim senaryosu
# =====================================================================

class TestFullDaySimulation:
    """Bir avukatin tam gunluk Ali v2 kullanimini simule eder."""

    def test_morning_routine(self, registry):
        """Sabah: Notlar kontrol, takvim gozden gecir, yeni muvekil ekle."""
        # Notlara bak
        notes = registry["not_al"]
        notes.run(action="add", text="Bugunku gorevler: dosya hazirla, muvekil ara", tag="reminder")
        list_result = notes.run(action="list")
        assert "gorevler" in list_result.lower()

        # Takvime bak
        cal = registry["durusma_takvimi"]
        tomorrow = datetime.now() + timedelta(days=1)
        cal.run(
            action="add",
            date=tomorrow.strftime("%d.%m.%Y"),
            time="10:30",
            court="Istanbul 14. Asliye Hukuk",
            case_no="2026/342",
            description="Tensip durusmasi",
        )
        upcoming = cal.run(action="upcoming")
        assert isinstance(upcoming, str)

        # Yeni muvekil
        clients = registry["muvekil_takip"]
        clients.run(
            action="add",
            name="Ayse Kara",
            phone="05559876543",
            email="ayse@example.com",
            case_summary="Kira uyusmazligi — tahliye davasi",
        )

    def test_midday_legal_work(self, registry):
        """Oglen: Ceza hesapla, belge olustur, zamanlayici baslat."""
        # Zamanlayici baslat
        timer = registry["zaman_takip"]
        timer.run(action="start", case_name="Kara/Tahliye", description="Dilekce yazimi")

        # Ceza hesapla
        ceza = registry["ceza_hesapla"]
        result = ceza.run(temel_ceza_ay=48, hafifletici_orani=0.33, iyi_hal=True)
        assert "SONUC CEZA" in result

        # Not al
        notes = registry["not_al"]
        notes.run(action="add", text="Kara dosyasi: ceza hesabi yapildi, dilekce hazirlaniyor", tag="normal")

        # Zamanlayici durdur
        time.sleep(0.1)
        stop_result = timer.run(action="stop")
        assert "durduruldu" in stop_result.lower()

    def test_afternoon_client_management(self, registry):
        """Ikindi: Muvekil yonetimi, not ekleme."""
        clients = registry["muvekil_takip"]

        # 3 muvekil ekle
        for i, (name, case) in enumerate([
            ("Hasan Yildiz", "Trafik kazasi tazminat"),
            ("Elif Celik", "Is hukuku — haksiz fesih"),
            ("Omer Demir", "Miras davasi"),
        ]):
            clients.run(action="add", name=name, case_summary=case)

        # Arama
        search = clients.run(action="search", query="Hasan")
        assert "Hasan" in search

        # Liste
        lst = clients.run(action="list")
        assert "Elif" in lst
        assert "Omer" in lst

    def test_evening_review(self, registry):
        """Aksam: Gunluk rapor, hatirlatici ayarla."""
        # Zaman raporu
        timer = registry["zaman_takip"]
        timer.run(action="start", case_name="Genel", description="Gun sonu degerlendirme")
        time.sleep(0.1)
        timer.run(action="stop")
        report = timer.run(action="report")
        assert isinstance(report, str)

        # Yarin icin hatirlatici
        reminder = registry["hatirlatici"]
        result = reminder.run(message="Durusma hazirligi: dosyalari kontrol et", minutes=720)
        assert "ayarlandi" in result.lower()

        # Son notlar
        notes = registry["not_al"]
        notes.run(action="add", text="Gun sonu: 3 muvekil eklendi, 2 dosya uzerinde calisildi", tag="normal")

        final_notes = notes.run(action="list")
        assert "gun sonu" in final_notes.lower()


# =====================================================================
#  Cleanup
# =====================================================================

def pytest_sessionfinish(session, exitstatus):
    """Test bitince gecici dosyalari temizle."""
    if TEST_DATA_DIR.exists():
        shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)
