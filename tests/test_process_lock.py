"""
tests/test_process_lock.py
--------------------------------
🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — Duplicate-Order Protection, गंभीर यादीतला
पाचवा मुद्दा) — VPS crontab वर तिन्ही bots दर १ मिनिटाला चालतात; एखादी invocation जास्त वेळ घेतली
(network मंदी), तर cron ची पुढची invocation समांतर सुरू होऊन डुप्लिकेट (खरे) ऑर्डर पाठवू शकते.
process_lock.ProcessLock हे fcntl-आधारित OS-पातळीवरचं advisory file-lock, हे रोखण्यासाठी.
"""
import tempfile

import pytest

import config
import process_lock


@pytest.fixture
def temp_data_dir(monkeypatch):
    tmpdir = tempfile.mkdtemp()
    monkeypatch.setattr(process_lock, "DATA_DIR", tmpdir)
    yield tmpdir


class TestProcessLock:
    def test_acquires_and_releases_cleanly(self, temp_data_dir):
        with process_lock.ProcessLock("bot_a"):
            pass  # काहीही exception आली नाही तरच पुरेसं

    def test_second_concurrent_lock_on_same_name_raises(self, temp_data_dir):
        """flock() हा open-file-description वर असतो, process वर नाही — त्यामुळे त्याच process
        मध्येही, आधीचा lock अजून उघडा (with-block च्या आतच) असताना दुसरा स्वतंत्र ProcessLock
        (त्याच नावाचा) घ्यायचा प्रयत्न केला, तर तो cross-process overlap सारखाच अडतो."""
        with process_lock.ProcessLock("bot_a"):
            with pytest.raises(process_lock.ProcessLockHeld):
                with process_lock.ProcessLock("bot_a"):
                    pass

    def test_lock_released_after_with_block_allows_reacquire(self, temp_data_dir):
        with process_lock.ProcessLock("bot_a"):
            pass
        with process_lock.ProcessLock("bot_a"):
            pass  # आधीचा lock सुटला असल्याने हे यशस्वी व्हायलाच हवं

    def test_different_names_dont_conflict(self, temp_data_dir):
        with process_lock.ProcessLock("bot_a"):
            with process_lock.ProcessLock("bot_b"):
                pass  # वेगळी लॉक-फाईल -- एकमेकांना अडवत नाहीत

    def test_lock_released_even_on_exception_inside_with_block(self, temp_data_dir):
        with pytest.raises(ValueError):
            with process_lock.ProcessLock("bot_a"):
                raise ValueError("simulated failure inside locked block")
        with process_lock.ProcessLock("bot_a"):
            pass  # वरच्या block मध्ये exception आली तरी lock नीट सुटायलाच हवा
