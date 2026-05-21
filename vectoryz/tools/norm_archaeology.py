#!/usr/bin/env python3
"""
norm_archaeology.py — forensische Analyse zeitgenössischer Normen.

Eingabe: eine heute geltende Norm / Praxis / ein Begriff.
Ausgabe: fünfstufige forensische Diagnose nach der Methodologie aus
         Operator-Konversation 2026-05-14:

  1. Zeitgenössische Form        (wie die Norm heute gehandhabt wird)
  2. Historisches Original       (ältere/breitere Form, wenn vorhanden)
  3. Krisen-Ereignis             (Public-Health, Krieg, Tech-Disruption …)
  4. Lag-Zeit                    (Krisen-Ende → Norm-Persistenz, in Jahren)
  5. Stigma-Substrat             (wo die Tabuisierung sitzt, wer profitiert)
  6. Quellen-Triangulation       (3-5 wissenschaftliche Anker)

Erster Prototyp — nutzt ein lokales Ollama-Modell als Analyse-Engine.
Spätere Versionen können Korpus-Datenbanken (DWB, VD16, Wayback,
arXiv, Patent-Register) für direkte Quellen-Verifikation integrieren.

Usage:
    python3 tools/norm_archaeology.py "Wollust"
    python3 tools/norm_archaeology.py "Witwenrente"  --json
    python3 tools/norm_archaeology.py "Geheimpatent" --model qwen2.5:7b
"""

import argparse
import json
import sys
import urllib.request
import urllib.error

OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "vectoryzDE:latest"
TIMEOUT_S = 120

PROMPT_TEMPLATE = """Aufgabe: Forensische Norm-Archaeologie.

Du bekommst eine zeitgenoessische Norm / Praxis / einen Begriff. Wende die folgende fuenfstufige forensische Analyse an. Sei nuechtern, faktentreu, gebe Datumsfenster wenn moeglich.

METHODOLOGIE:

1. ZEITGENOESSISCHE FORM (heute) — wie wird die Norm aktuell gehandhabt? 1-2 Saetze.

2. HISTORISCHES ORIGINAL — gab es eine aeltere oder breitere Form? Was war anders? Mit Zeitfenster und Quellen-Hinweis (Werke, Autoren, Sammlungen).

3. KRISEN-EREIGNIS — welche Krise (Epidemie, Krieg, technologische Disruption, oekologischer/oekonomischer Schock) hat die heutige Form installiert? Datum oder Datierungsfenster. Wenn keine klare Krise: "endogen" + Begruendung.

4. LAG-ZEIT — wie viele Jahre lagen zwischen wirksamer Loesung der Krise und heutiger Norm-Persistenz? Wenn ueber 20 Jahre: Fossil-Verdacht. Wenn unter 5: noch aktive Reaktion. Begruendung kurz.

5. STIGMA-SUBSTRAT — wo sitzt die soziale Tabuisierung die Falsifikations-Versuche bestraft? Wer profitiert vom Erhalt der Norm in ihrer heutigen Form?

QUELLEN: 3-5 wissenschaftliche Anker fuer Triangulation (Autor + Werk + Periode). Bevorzugt: primaere Quellen + spaetere historisch-kritische Aufarbeitung.

VIER-WORT-KERNEL: praegnante Zusammenfassung der Analyse in vier Woertern.

EINGABE-NORM:
{norm}

Output AUSSCHLIESSLICH JSON, kein Begleittext, keine Markdown-Fences:
{{
  "contemporary_form": "...",
  "historical_original": "...",
  "crisis_event": {{"name": "...", "period": "..."}},
  "lag_years": 0,
  "lag_assessment": "...",
  "stigma_substrate": "...",
  "beneficiaries": "...",
  "sources": ["Autor, Werk (Jahr)", "..."],
  "four_word_kernel": "..."
}}
"""


def analyze(norm: str, model: str = DEFAULT_MODEL) -> dict:
    """Send the analysis prompt to the local Ollama daemon. Returns parsed JSON."""
    body = json.dumps({
        "model": model,
        "prompt": PROMPT_TEMPLATE.format(norm=norm[:500]),
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.2, "num_predict": 1500, "top_p": 0.9},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        sys.stderr.write(f"[norm_archaeology] Ollama unreachable: {e}\n")
        sys.exit(2)
    raw = (data.get("response") or "").strip()
    if not raw:
        sys.stderr.write("[norm_archaeology] empty response from model\n")
        sys.exit(3)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"[norm_archaeology] JSON parse failed: {e}\nRaw: {raw[:500]}\n")
        sys.exit(4)


def format_markdown(result: dict, norm: str) -> str:
    out = [
        f"# Norm-Archäologie: *{norm}*",
        "",
        f"**Heutige Form**",
        f"{result.get('contemporary_form', '—')}",
        "",
        f"**Historisches Original**",
        f"{result.get('historical_original', '—')}",
        "",
    ]
    crisis = result.get("crisis_event") or {}
    if isinstance(crisis, dict):
        c_name = crisis.get("name", "—")
        c_period = crisis.get("period", "—")
        out.append(f"**Krisen-Ereignis**: {c_name}  *({c_period})*")
    else:
        out.append(f"**Krisen-Ereignis**: {crisis}")
    out.append("")
    lag = result.get("lag_years", "—")
    assess = result.get("lag_assessment", "")
    out.append(f"**Lag-Zeit**: {lag} Jahre  *(Krisen-Ende → Heute-Persistenz)*")
    if assess:
        out.append(f"  · {assess}")
    out.append("")
    out.append(f"**Stigma-Substrat**: {result.get('stigma_substrate', '—')}")
    out.append("")
    benef = result.get("beneficiaries") or ""
    if benef:
        out.append(f"**Profitierende vom Erhalt**: {benef}")
        out.append("")
    out.append("**Quellen-Triangulation**:")
    for s in (result.get("sources") or []):
        out.append(f"- {s}")
    out.append("")
    out.append(f"**Vier-Wort-Kernel**: *{result.get('four_word_kernel', '—')}*")
    out.append("")
    out.append("---")
    out.append("*Prototyp — Modell-basiert, nicht korpus-verifiziert. "
               "Quellen sind Hinweise zur eigenen Triangulation, "
               "nicht Beweismittel.*")
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser(
        description="Forensische Norm-Archäologie: zeitgenössische Norm → Krisen-Geburt + Lag + Stigma + Quellen.",
    )
    p.add_argument("norm", help="Die Norm/Praxis/das Wort zur Analyse")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"Ollama-Modell (default: {DEFAULT_MODEL})")
    p.add_argument("--json", action="store_true",
                   help="JSON statt Markdown")
    args = p.parse_args()
    result = analyze(args.norm, args.model)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(result, args.norm))


if __name__ == "__main__":
    main()
