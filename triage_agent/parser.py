"""Parse validation run logs into RunMeta and LogEvent objects."""

import re
from pathlib import Path
from typing import List, Tuple

from .schemas import LogEvent, RunMeta

HEADER_RE = re.compile(r"^=== RUN START (?P<body>.*) ===$")
FOOTER_RE = re.compile(r"^=== RUN END (?P<body>.*) ===$")
KV_RE = re.compile(r"(\w+)=(\S+)")
LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\s*\|\s*"
    r"(?P<level>\w+)\s*\|\s*(?P<comp>\w+)\s*\|\s*(?P<unit>[\w-]+)\s*\|\s*"
    r"(?P<suite>\w+)\s*\|\s*iter=(?P<iter>\d+)\s*\|\s*(?P<msg>.*)$"
)


def parse_log_text(text: str, file_name: str) -> Tuple[RunMeta, List[LogEvent]]:
    meta_fields = {"file": file_name}
    events: List[LogEvent] = []
    run_id = Path(file_name).stem.split("_")[0]

    for no, line in enumerate(text.splitlines(), start=1):
        line = line.rstrip()
        if not line:
            continue
        h = HEADER_RE.match(line)
        if h:
            meta_fields.update(dict(KV_RE.findall(h.group("body"))))
            run_id = meta_fields.get("run_id", run_id)
            continue
        f = FOOTER_RE.match(line)
        if f:
            kv = dict(KV_RE.findall(f.group("body")))
            meta_fields["result"] = kv.get("result", "UNKNOWN")
            meta_fields["iterations"] = kv.get("iterations", "")
            meta_fields["duration_s"] = int(kv.get("duration_s", 0))
            continue
        m = LINE_RE.match(line)
        if not m:
            continue  # unknown line format, skip
        events.append(
            LogEvent(
                run_id=run_id,
                line_no=no,
                timestamp=m.group("ts"),
                level=m.group("level").upper(),
                component=m.group("comp").upper(),
                unit=m.group("unit"),
                suite=m.group("suite"),
                iteration=int(m.group("iter")),
                message=m.group("msg").strip(),
            )
        )

    meta_fields["run_id"] = run_id
    allowed = RunMeta.model_fields.keys()
    meta = RunMeta(**{k: v for k, v in meta_fields.items() if k in allowed})
    return meta, events


def parse_log_file(path: Path) -> Tuple[RunMeta, List[LogEvent]]:
    path = Path(path)
    return parse_log_text(path.read_text(errors="replace"), path.name)
