"""opportunity_engine/detectors — Setup Detector Library (D1…D10). PR-1b मध्ये फक्त interface (`base.py`); detectors D1–D3 PR-1c मध्ये."""
from .base import Candidate, Detector

__all__ = ["Candidate", "Detector"]
