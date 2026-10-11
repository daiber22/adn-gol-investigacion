"""Perfiles prepartido estrictamente cronológicos, sin fuga de información futura."""
import argparse
import csv
import json
from collections import defaultdict

from src.pipeline import BASE, OUT, RAW, fetch_json

def kickoff(match):
    return (match.get("match_date") or "") + "T" + (match.get("kick_off") or "00:00:00")

def teams(match):
    return [match["home_team"]["home_team_id"], match["away_team"]["away_team_id"]]

def mechanism(seq):
    """Etiquetas conservadoras: no llamar contraataque a una jugada solo por su velocidad."""
    shots = [e for e in seq if e.get("type", {}).get("name") == "Shot"]
    if any(any(t.get("name") == "From Counter" for t in (e.get("tags") or [])) for e in shots):
        return "contraataque_etiquetado"
    if any(e.get("type", {}).get("name") == "Carry" for e in seq) and len(seq) <= 8:
        return "transicion_candidata_no_validada"
    return "sin_clasificar"

def summarize_team(events, team_id):
    possessions = defaultdict(list)
    for event in events:
        pid = event.get("possession")
        if pid is not None:
            possessions[pid].append(event)
    totals = defaultdict(float)
    for seq in possessions.values():
        seq.sort(key=lambda e: e.get("index", 0))
        owner = (seq[0].get("possession_team") or {}).get("id")
        if owner is None:
            continue
        shots = [e for e in seq if e.get("type", {}).get("name") == "Shot"]
        label = mechanism(seq)
        side = "for" if owner == team_id else "against"
        totals[f"{side}_possessions"] += 1
        totals[f"{side}_possessions_{label}"] += 1
        for shot in shots:
            # Un remate puede pertenecer a un equipo distinto del dueño de la posesión.
            shot_side = "for" if (shot.get("team") or {}).get("id") == team_id else "against"
            shot_label = label if shot_side == side else "sin_clasificar"
            totals[f"{shot_side}_shots_{shot_label}"] += 1
            data = shot.get("shot") or {}
            totals[f"{shot_side}_xg_{shot_label}"] += float(data.get("statsbomb_xg") or 0)
            totals[f"{shot_side}_goals_{shot_label}"] += int((data.get("outcome") or {}).get("name") == "Goal")
    return totals

def build(matches, limit=10, prior=5):
    ordered = sorted(matches, key=lambda m: (kickoff(m), m["match_id"]))
    output = []
    for target in ordered[-limit:]:
        target_ids = teams(target)
        earlier = [m for m in ordered if kickoff(m) < kickoff(target)]
        for side, team_id in zip(("home", "away"), target_ids):
            history = [m for m in earlier if team_id in teams(m)][-prior:]
            sums = defaultdict(float)
            used = []
            for match in history:
                mid = match["match_id"]
                events = fetch_json(f"{BASE}/events/{mid}.json", RAW / f"events_{mid}.json")
                for key, value in summarize_team(events, team_id).items():
                    sums[key] += value
                used.append(mid)
            output.append({
                "match_id": target["match_id"], "kickoff": kickoff(target),
                "side": side, "team_id": team_id, "prior_matches": len(used),
                "prior_match_ids": json.dumps(used),
                "complete_history": int(len(used) == prior),
                **dict(sums),
            })
    return output

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--competition", type=int, default=37)
    parser.add_argument("--season", type=int, default=90)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--prior", type=int, default=5)
    args = parser.parse_args()
    matches = fetch_json(f"{BASE}/matches/{args.competition}/{args.season}.json", RAW / f"matches_{args.competition}_{args.season}.json")
    rows = build(matches, args.limit, args.prior)
    OUT.mkdir(parents=True, exist_ok=True)
    columns = sorted(set().union(*(r.keys() for r in rows)))
    with (OUT / "pre_match_profiles.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    summary = {"target_matches": len(rows) // 2, "profiles": len(rows), "complete_profiles": sum(r["complete_history"] for r in rows), "minimum_prior": args.prior, "note": "Etiquetas candidatas sin validación táctica; no se calculan probabilidades predictivas."}
    (OUT / "pre_profiles_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))

if __name__ == "__main__":
    main()
