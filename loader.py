"""
loader.py
-----------
config.yaml वाचून enabled strategies + orchestrator तयार करतो.
तुमच्या Streamlit app/GitHub Actions cron मध्ये फक्त हे import करून वापरायचं:

    from loader import build_orchestrator
    orch = build_orchestrator("config.yaml")
    signals = orch.run_cycle(snapshot)
"""

import yaml
from strategies import STRATEGY_REGISTRY
from orchestrator import SignalOrchestrator, OrchestratorConfig


def build_orchestrator(config_path: str = "config.yaml") -> SignalOrchestrator:
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    strategy_objs = []
    for strat_id, strat_cfg in cfg.get("strategies", {}).items():
        cls = STRATEGY_REGISTRY.get(strat_id)
        if cls is None:
            print(f"[WARN] Unknown strategy in config: {strat_id}, skipping")
            continue
        strategy_objs.append(cls(config=strat_cfg))

    orch_cfg_dict = cfg.get("orchestrator", {})
    orch_cfg = OrchestratorConfig(
        conflict_mode=orch_cfg_dict.get("conflict_mode", "veto"),
        min_confidence_to_act=orch_cfg_dict.get("min_confidence_to_act", 0.5),
    )

    return SignalOrchestrator(strategy_objs, orch_cfg)
