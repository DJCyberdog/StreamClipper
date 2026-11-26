"""Initial bilingual shell dictionary; domain dialogs remain German until audited."""
LABELS={
"open_button":("📂 Aufnahme öffnen","📂 Open recording"),
"twitch_button":("🌐 Video-URL importieren","🌐 Import video URL"),
"analyze_button":("Highlights analysieren","Analyze highlights"),
"cancel_button":("Abbrechen","Cancel"),
"render_preview_button":("🎞 Exportgetreue Vorschau (bis 20 s)","🎞 Render preview (up to 20 s)"),
"single_export":("Ausgewählten Clip exportieren","Export selected clip"),
"all_export":("Alle Clips exportieren","Export all clips")}
MENUS={"Datei && Projekt":"File && Project","Szenen":"Scenes","Ansicht && Arbeitsbereiche":"View && Workspaces","Integrationen (M18)":"Integrations (M18)"}
def apply_language(window,english):
    for attr,(de,en) in LABELS.items():
        getattr(window,attr).setText(en if english else de)
    mapping=MENUS if english else {v:k for k,v in MENUS.items()}
    for action in window.menuBar().actions():
        if action.text() in mapping:action.setText(mapping[action.text()])
    window.statusBar().showMessage("English shell (partial); specialist dialogs remain German" if english else "Deutsche Hauptbedienung")
