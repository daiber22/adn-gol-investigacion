"""Auditoria descriptiva de ADN sin cambiar predicciones ni pesos."""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

SOURCE = Path("data/processed/comparison.csv")
TARGET = Path("data/processed/diagnostico_adn.json")

def summarize(rows):
    n = len(rows)
    if not n:
        return {"evaluated": 0, "reason": "Sin partidos con perfiles completos"}
    def accuracy(subset, field):
        return {"n": len(subset), "correct": sum(r[field] == r["actual"] for r in subset)}
    bins = {
        "clash_negativo": [r for r in rows if float(r["counter_clash"]) < 0],
        "clash_cero": [r for r in rows if float(r["counter_clash"]) == 0],
        "clash_positivo": [r for r in rows if float(r["counter_clash"]) > 0],
    }
    transitions = defaultdict(lambda: {"n": 0, "correct": 0, "wrong": 0})
    for r in rows:
        if r["baseline_pick"] != r["augmented_pick"]:
            key = r["baseline_pick"] + "_a_" + r["augmented_pick"]
            transitions[key]["n"] += 1
            transitions[key]["correct"] += int(r["augmented_pick"] == r["actual"])
            transitions[key]["wrong"] += int(r["augmented_pick"] != r["actual"])
    by_actual = {}
    for label in "HDA":
        subset = [r for r in rows if r["actual"] == label]
        by_actual[label] = {"real": len(subset), "base": accuracy(subset, "baseline_pick"), "adn": accuracy(subset, "augmented_pick")}
    return {
        "evaluated": n,
        "base": accuracy(rows, "baseline_pick"),
        "adn": accuracy(rows, "augmented_pick"),
        "by_actual": by_actual,
        "clash_sign": {k: {"base": accuracy(v, "baseline_pick"), "adn": accuracy(v, "augmented_pick")} for k, v in bins.items()},
        "changed_predictions": sum(r["baseline_pick"] != r["augmented_pick"] for r in rows),
        "changes": dict(transitions),
        "mean_brier": {
            "base": sum(float(r["baseline_brier"]) for r in rows)/n,
            "adn": sum(float(r["augmented_brier"]) for r in rows)/n,
        },
        "note": "Diagnostico retrospectivo; no calibra ni valida mecanismos tacticos y no demuestra causalidad.",
    }

def main():
    rows = list(csv.DictReader(SOURCE.open(encoding="utf-8"))) if SOURCE.exists() else []
    result = summarize(rows)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("DIAGNOSTICO_ADN " + json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
