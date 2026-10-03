"""tests/test_no_shadowed_imports.py -- function मधल्या असाइनमेंटने module-level import/def "लपवला" जाऊ नये.

Python मध्ये function मध्ये कुठेही `name = ...` असेल तर ते नाव संपूर्ण function मध्ये local ठरतं; तिथेच आधी
import केलेलं `name(...)` बोलावल्यास UnboundLocalError येतो (Dashboard वर `last_rsi` मुळे bot-view चे
gate-lines कधीच दिसले नव्हते — except Exception ने गिळला जात होता).
"""
import glob
import os
import symtable

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _offenders(path):
    with open(path, encoding="utf-8") as f:
        top = symtable.symtable(f.read(), path, "exec")
    shadowable = {s.get_name() for s in top.get_symbols() if s.is_imported() or s.is_namespace()}
    found = []

    def walk(table):
        for child in table.get_children():
            if child.get_type() == "function":
                for sym in child.get_symbols():
                    if sym.is_local() and sym.is_assigned() and not sym.is_parameter() and sym.get_name() in shadowable:
                        found.append(f"{os.path.basename(path)}:{child.get_name()}:{sym.get_name()}")
            walk(child)

    walk(top)
    return found


def test_no_function_shadows_a_module_level_import_or_def():
    offenders = []
    for path in sorted(glob.glob(os.path.join(ROOT, "*.py")) + glob.glob(os.path.join(ROOT, "strategies", "*.py"))):
        offenders += _offenders(path)
    assert not offenders, offenders
