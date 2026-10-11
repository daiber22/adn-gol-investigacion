"""Evaluación exploratoria 1X2, sin datos posteriores al inicio de cada encuentro.

Compara un modelo tradicional (goles, victorias y derrotas anteriores)
con el mismo modelo más el choque ataque-defensa. Las ponderaciones son
exploratorias, no entrenadas ni optimizadas con estos resultados.
"""
import argparse
import csv
import json
import math
from collections import defaultdict

from src.pipeline import BASE, OUT, RAW, fetch_json
from src.pre_profiles import build, kickoff, teams

def result(match, team_id):
    home, away = teams(match)
    h, a = match.get("home_score"), match.get("away_score")
    if h is None or a is None:
        return None
    gf, ga = (h, a) if team_id == home else (a, h)
    return int(gf), int(ga)

def history_stats(matches, target, team_id, prior=5):
    earlier = sorted((m for m in matches if kickoff(m) < kickoff(target) and team_id in teams(m)), key=lambda m: (kickoff(m), m["match_id"]))
    history = earlier[-prior:]
    values = [result(m, team_id) for m in history]
    if len(values) != prior or any(v is None for v in values):
        return None
    gf = sum(v[0] for v in values) / prior
    ga = sum(v[1] for v in values) / prior
    wins = sum(v[0] > v[1] for v in values) / prior
    draws = sum(v[0] == v[1] for v in values) / prior
    losses = sum(v[0] < v[1] for v in values) / prior
    return gf, ga, wins, draws, losses

def rate(profile, prefix, suffix):
    return float(profile.get(prefix + "_" + suffix, 0) or 0) / max(1, profile["prior_matches"])

def clash(home, away):
    # Solo señales etiquetadas explícitamente como contraataque.
    label = "contraataque_etiquetado"
    home_attack = rate(home, "for", "xg_" + label)
    away_weakness = rate(away, "against", "xg_" + label)
    away_attack = rate(away, "for", "xg_" + label)
    home_weakness = rate(home, "against", "xg_" + label)
    return home_attack * away_weakness - away_attack * home_weakness

def softmax(scores):
    m = max(scores)
    exps = [math.exp(v-m) for v in scores]
    return [v/sum(exps) for v in exps]

def probabilities(h, a, mechanism_adjustment=0):
    gf_diff = (h[0]-a[1]) - (a[0]-h[1])
    form_diff = (h[2]-h[4]) - (a[2]-a[4])
    advantage = 0.30 + 0.38*gf_diff + 0.45*form_diff + mechanism_adjustment
    return softmax([advantage, 0.0, -advantage])

def brier(p, actual):
    return sum((v - int(i == actual))**2 for i, v in enumerate(p))

def evaluate(matches, limit=10, prior=5):
    ordered = sorted(matches, key=lambda m: (kickoff(m), m["match_id"]))
    targets = ordered[-limit:]
    profiles = build(matches, limit=limit, prior=prior)
    by_key = {(r["match_id"], r["side"]): r for r in profiles}
    rows = []
    for target in targets:
        mid = target["match_id"]
        home_id, away_id = teams(target)
        h, a = history_stats(matches, target, home_id, prior), history_stats(matches, target, away_id, prior)
        hp, ap = by_key[(mid, "home")], by_key[(mid, "away")]
        if h is None or a is None or not (hp["complete_history"] and ap["complete_history"]):
            continue
        final = result(target, home_id)
        if final is None:
            continue
        actual = 0 if final[0] > final[1] else 1 if final[0] == final[1] else 2
        base = probabilities(h, a)
        delta = clash(hp, ap)
        augmented = probabilities(h, a, mechanism_adjustment=0.8*delta)
        rows.append({"match_id":mid, "actual":"HDA"[actual], "score":str(final[0])+"-"+str(final[1]),
                     "counter_clash":round(delta,6), "baseline_pick":"HDA"[base.index(max(base))],
                     "augmented_pick":"HDA"[augmented.index(max(augmented))],
                     "baseline_brier":round(brier(base,actual),6),
                     "augmented_brier":round(brier(augmented,actual),6),
                     "baseline_probabilities":json.dumps([round(x,5) for x in base]),
                     "augmented_probabilities":json.dumps([round(x,5) for x in augmented])})
    return rows

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--competition",type=int,default=37)
    parser.add_argument("--season",type=int,default=90)
    parser.add_argument("--limit",type=int,default=10)
    args = parser.parse_args()
    matches = fetch_json(f"{BASE}/matches/{args.competition}/{args.season}.json", RAW / f"matches_{args.competition}_{args.season}.json")
    rows = evaluate(matches,args.limit)
    OUT.mkdir(parents=True,exist_ok=True)
    if rows:
        with (OUT/"comparison.csv").open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    n=len(rows)
    summary={"evaluated":n,"requested":args.limit,"baseline_brier":round(sum(r["baseline_brier"] for r in rows)/n,6) if n else None,
             "augmented_brier":round(sum(r["augmented_brier"] for r in rows)/n,6) if n else None,
             "baseline_correct":sum(r["baseline_pick"]==r["actual"] for r in rows),
             "augmented_correct":sum(r["augmented_pick"]==r["actual"] for r in rows),
             "nonzero_clashes":sum(r["counter_clash"]!=0 for r in rows),
             "caution":"Exploratorio, muestra pequeña, pesos no calibrados. No prueba causalidad ni superioridad generalizable."}
    (OUT/"comparison_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print("COMPARISON_SUMMARY "+json.dumps(summary,ensure_ascii=False))
if __name__=="__main__":
    main()
