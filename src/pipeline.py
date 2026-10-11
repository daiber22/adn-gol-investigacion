"""Descarga idempotente de StatsBomb Open Data y agregación básica de posesiones."""
import argparse
import csv
import json
import time
from collections import defaultdict
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"

def fetch_json(url, destination, refresh=False, retries=3):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not refresh:
        return json.loads(destination.read_text(encoding="utf-8"))
    for attempt in range(retries):
        try:
            req = Request(url, headers={"User-Agent": "ADN-Gol-Research/0.1"})
            with urlopen(req, timeout=40) as response:
                raw = response.read()
            data = json.loads(raw)
            temp = destination.with_suffix(".tmp")
            temp.write_bytes(raw)
            temp.replace(destination)
            return data
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt == retries - 1:
                raise RuntimeError(f"No se pudo obtener {url}: {exc}") from exc
            time.sleep(2 ** attempt)

def summarize_match(match_id, events):
    possessions = defaultdict(list)
    shots = []
    for event in events:
        possession_id = event.get("possession")
        if possession_id is None:
            continue
        possessions[(match_id, possession_id)].append(event)
        if event.get("type", {}).get("name") == "Shot":
            shot = event.get("shot") or {}
            outcome = (shot.get("outcome") or {}).get("name", "")
            shots.append({
                "match_id": match_id, "event_id": event.get("id"),
                "team_id": (event.get("team") or {}).get("id"),
                "possession": possession_id, "minute": event.get("minute"),
                "xg": shot.get("statsbomb_xg"), "goal": int(outcome == "Goal"),
                "from_counter": int(any((tag or {}).get("name") == "From Counter" for tag in event.get("tags", [])))),
            })
    rows = []
    for (mid, pid), seq in possessions.items():
        seq.sort(key=lambda e: e.get("index") or 0)
        shot_count = sum(e.get("type", {}).get("name") == "Shot" for e in seq)
        rows.append({
            "match_id": mid, "possession": pid,
            "team_id": (seq[0].get("possession_team") or {}).get("id"),
            "events": len(seq), "passes": sum(e.get("type", {}).get("name") == "Pass" for e in seq),
            "shots": shot_count, "has_shot": int(shot_count > 0),
        })
    return rows, shots

def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--competition", type=int, required=True)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    matches = fetch_json(f"{BASE}/matches/{args.competition}/{args.season}.json",
                         RAW / f"matches_{args.competition}_{args.season}.json", args.refresh)
    matches = sorted(matches, key=lambda m: (m.get("match_date", ""), m.get("kick_off") or "", m["match_id"]))[:args.limit]
    all_possessions, all_shots = [], []
    manifest = {"competition": args.competition, "season": args.season, "matches": [], "errors": []}
    for match in matches:
        mid = match["match_id"]
        try:
            events = fetch_json(f"{BASE}/events/{mid}.json", RAW / f"events_{mid}.json", args.refresh)
            possessions, shots = summarize_match(mid, events)
            all_possessions.extend(possessions)
            all_shots.extend(shots)
            manifest["matches"].append({"match_id": mid, "date": match.get("match_date"), "events": len(events), "possessions": len(possessions), "shots": len(shots)})
            print(f"OK {mid}: {len(events)} eventos, {len(possessions)} posesiones, {len(shots)} remates", flush=True)
        except Exception as exc:
            manifest["errors"].append({"match_id": mid, "error": str(exc)})
            print(f"ERROR {mid}: {exc}", flush=True)
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        write_csv(OUT / "possessions.csv", all_possessions, ["match_id","possession","team_id","events","passes","shots","has_shot"])
        write_csv(OUT / "shots.csv", all_shots, ["match_id","event_id","team_id","possession","minute","xg","goal","from_counter"])
    print(json.dumps({"processed": len(manifest["matches"]), "errors": len(manifest["errors"]), "shots": len(all_shots)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
