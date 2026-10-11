"""Auditoria de cambios 1X2 con los cinco partidos previos y mecanismos candidatos.

No modifica las predicciones: describe los cambios ya hechos por el modelo.
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path("data/processed")
LABELS = ("contraataque_etiquetado", "ataque_directo_rapido_candidato",
          "transicion_indirecta_candidata", "ataque_posicional_candidato")

def load(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def number(row, key):
    return float(row.get(key) or 0)

def mechanisms(home, away):
    out = {}
    for label in LABELS:
        home_for = number(home, "for_xg_" + label)/max(1, number(home, "prior_matches"))
        away_against = number(away, "against_xg_" + label)/max(1, number(away, "prior_matches"))
        away_for = number(away, "for_xg_" + label)/max(1, number(away, "prior_matches"))
        home_against = number(home, "against_xg_" + label)/max(1, number(home, "prior_matches"))
        out[label] = {
            "home_for_xg_per_match": round(home_for, 5),
            "away_against_xg_per_match": round(away_against, 5),
            "away_for_xg_per_match": round(away_for, 5),
            "home_against_xg_per_match": round(home_against, 5),
            "clash_component": round(home_for*away_against-away_for*home_against, 6),
        }
    return out

def main():
    comparisons = load(ROOT / "comparison.csv")
    profiles = {(r["match_id"], r["side"]): r for r in load(ROOT / "pre_match_profiles.csv")}
    changes = []
    for r in comparisons:
        if r["baseline_pick"] == r["augmented_pick"]:
            continue
        h, a = profiles.get((r["match_id"], "home")), profiles.get((r["match_id"], "away"))
        if not h or not a:
            continue
        changes.append({
            "match_id": r["match_id"],
            "actual": r["actual"],
            "score": r["score"],
            "baseline_pick": r["baseline_pick"],
            "augmented_pick": r["augmented_pick"],
            "baseline_correct": r["baseline_pick"] == r["actual"],
            "adn_correct": r["augmented_pick"] == r["actual"],
            "change_type": r["baseline_pick"] + "_a_" + r["augmented_pick"],
            "clash": number(r, "counter_clash"),
            "home_team_id": h["team_id"],
            "away_team_id": a["team_id"],
            "home_prior_match_ids": json.loads(h["prior_match_ids"]),
            "away_prior_match_ids": json.loads(a["prior_match_ids"]),
            "mechanisms": mechanisms(h, a),
        })
    group = defaultdict(lambda: {"total": 0, "corrected": 0, "damaged": 0, "both_wrong": 0})
    for r in changes:
        g = group[r["change_type"]]
        g["total"] += 1
        g["corrected"] += int(r["adn_correct"])
        g["damaged"] += int(r["baseline_correct"])
        g["both_wrong"] += int(not r["adn_correct"] and not r["baseline_correct"])
    result = {
        "changed_matches": len(changes),
        "change_summary": dict(group),
        "changes": changes,
        "caution": "Descriptivo y retrospectivo. No demuestra causalidad ni calibra etiquetas tacticas.",
    }
    path = ROOT / "changed_match_audit.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("CHANGED_MATCH_AUDIT " + json.dumps({
        "changed_matches": len(changes),
        "change_summary": dict(group),
        "home_to_draw": [r["match_id"] for r in changes if r["change_type"] == "H_a_D"],
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
