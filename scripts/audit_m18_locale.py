"""Report untranslated M18 UI candidates without altering source or claiming full coverage."""
import ast,json,re
from pathlib import Path
from streamclipper.m18_language import CATALOG

ROOT=Path(__file__).resolve().parents[1]/"src"/"streamclipper"
WIDGETS={"QLabel","QPushButton","QCheckBox","QGroupBox","setWindowTitle",
         "setToolTip","setPlaceholderText","setText","showMessage","setFormat",
         "warning","critical","question","information","getText","getItem","getInt",
         "getDouble","getOpenFileName","getSaveFileName","getExistingDirectory"}
GERMAN=re.compile(r"[äöüÄÖÜß]|\b(?:nicht|keine?|oder|und|wird|wurde|für|mit|aus|zum|zur|bitte|laden|speichern|öffnen|prüfen|übernehmen|Abbruch|Aufnahme|Auswahl|Zeit|Fehler)\b",re.I)

def scan():
    rows=[];total=0
    for p in sorted(ROOT.glob("*.py")):
        if not (p.name.endswith("_dialog.py") or p.name.endswith("_gui.py") or p.name in ("gui.py","m17_preview.py")):continue
        tree=ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node,ast.Call):continue
            fn=node.func
            label=fn.id if isinstance(fn,ast.Name) else fn.attr if isinstance(fn,ast.Attribute) else ""
            if label not in WIDGETS:continue
            for arg in node.args[:3]:
                if not isinstance(arg,ast.Constant) or not isinstance(arg.value,str):continue
                value=arg.value
                if not GERMAN.search(value):continue
                total+=1
                if value not in CATALOG:
                    rows.append({"file":p.name,"line":arg.lineno,"text":value})
    return {"schema_version":1,"catalog_entries":len(CATALOG),"german_literal_candidates":total,
            "missing_catalog_candidates":rows,"coverage":"NOT_CERTIFIED",
            "note":"Heuristic candidates only. Dynamic strings, indirect labels, Qt defaults and language semantics require manual review."}

if __name__=="__main__":print(json.dumps(scan(),ensure_ascii=False,indent=2))
