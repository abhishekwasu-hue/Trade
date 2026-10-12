"""gallery2 — Chart Reader v2 golden gallery (spec §5, step CR3): Abhi च्या हाताने केलेल्या chart marking ची साठवण.

🎓 हा package **labels** ठेवतो (reader2 चं logic नाही): candidate charts ची यादी (manifest), एका chart ची marking (schema), साठवण
(Supabase table + JSON export) आणि bars वाचणं (data policy सह). `reader2` इथे import होत नाही — gallery निवड / marking reader च्या
उत्तरांवर अवलंबून राहू नये, आणि dashboard पान (`page_reader2_gallery.py`) reader2 import करू शकत नाही (tests/test_reader2_boundary.py).
CR4 (scoring) उलट दिशेने gallery2 वाचेल. Test split sealed: calibration कधीच test labels वाचत नाही (`store.calibration_labels`).
"""
