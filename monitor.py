import json, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

DATA = Path("data/colleges.json")
OPEN_WORDS = [
    r"\bapplications?\s+(are\s+)?open\b",
    r"\bregistration\s+(is\s+)?open\b",
    r"\bapply\s+now\b",
    r"\bregister\s+now\b",
    r"\bregistration\s+2027\b",
    r"\badmissions\s+2027\s+open\b",
]

def fetch(url):
    req = Request(url, headers={"User-Agent":"AdmissionRadar/1.0 (+official-source-monitor)"})
    with urlopen(req, timeout=20) as r:
        return r.status, r.read(800_000).decode("utf-8","ignore")

def main():
    rows=json.loads(DATA.read_text())
    now=datetime.now(timezone.utc).strftime("%Y-%m-%d")
    changes=[]
    for x in rows:
        try:
            code, html=fetch(x["source"])
            text=re.sub(r"<[^>]+>"," ",html).lower()
            text=re.sub(r"\s+"," ",text)
            hits=[p for p in OPEN_WORDS if re.search(p,text)]
            old=x["status"]
            # Monitor is deliberately conservative: it can upgrade WATCH -> OPEN,
            # but does not auto-close a form solely from absence of keywords.
            if hits and x["cycle"]=="2027" and x["status"]=="WATCH":
                x["status"]="OPEN"
            x["lastChecked"]=now
            x["httpStatus"]=code
            if x["status"]!=old:
                changes.append(f'{x["name"]}: {old} -> {x["status"]}')
        except Exception as e:
            x["lastChecked"]=now
            x["monitorError"]=str(e)[:180]
    DATA.write_text(json.dumps(rows,indent=2),encoding="utf-8")
    print("Checked",len(rows),"sources at",now)
    for c in changes: print("CHANGE:",c)

if __name__=="__main__":
    main()
