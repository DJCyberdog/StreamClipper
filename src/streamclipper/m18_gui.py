"""M18 Qt controller. External integrations are session opt-in; one active worker."""
from dataclasses import replace
from pathlib import Path
import time
from PySide6.QtCore import QObject,QTimer
from PySide6.QtWidgets import (QFileDialog,QInputDialog,QMessageBox,QLineEdit,QLabel,QApplication)
from .portable import installation_directory
from .local_integrations import root,record_marker,markers,take_commands,WatchFolder,obs_seconds
from .channel_ingestion import Channel,parse_channel,load,save,poll

class Integrations(QObject):
    def __init__(self,window):
        super().__init__(window);self.w=window;self.watch=None;self.ready=[];self.deck=False
        self.channels_enabled=False;self.channels_path=root()/"channels.json";self.channels=[]
        self.youtube_token=None;self.obs_password=None;self.obs_session=None;self.obs_kind="obs-record";self.obs_port=4455
        self.next_watch=0.;self.next_channel=0.
        menu=window.menuBar().addMenu("Integrationen (M18)")
        self.menu=menu
        for label,fn in [
            ("OBS verbinden / Sitzung benennen …",self.configure_obs),
            ("Zeitmarke setzen (OBS oder Editor)",self.mark),
            ("Zeitmarken in manuelle Highlights übernehmen …",self.import_markers),
            ("Watch Folder auswählen / pausieren …",self.configure_watch),
            ("Erkannte Aufnahmen öffnen …",self.open_watched),
            ("Kanalaufnahme verwalten …",self.manage_channels),
            ("Kanalaufnahme für diese Sitzung starten / pausieren",self.toggle_channels),
            ("Schnittliste EDL / FCPXML …",self.nle),
            ("GIF / WebM exportieren …",self.alternative),
            ("Vorhandene SRT/VTT-Untertitel übernehmen …",self.subtitles),
            ("YouTube-Konto vorbereiten (OAuth-Pilot) …",self.youtube),
            ("Interface language / Sprache …",self.language)]:
            menu.addAction(label,fn)
        self.deck_action=menu.addAction("Lokale Stream-Deck-Befehle annehmen (Sitzung)")
        self.deck_action.setCheckable(True);self.deck_action.toggled.connect(self.set_deck)
        self.timer=QTimer(self);self.timer.setInterval(1000);self.timer.timeout.connect(self.tick);self.timer.start()
    def stop(self):
        self.timer.stop();self.deck=False;self.channels_enabled=False;self.obs_password=None;self.youtube_token=None
    def idle(self):
        w=self.w
        return not (w._history_blocked or (w.worker and w.worker.isRunning()) or
                   (w.model_worker and w.model_worker.isRunning()) or
                   (w.proxy_worker and w.proxy_worker.isRunning()) or
                   (w.queue_worker and w.queue_worker.isRunning()))
    def error(self,title,exc):
        QMessageBox.warning(self.w,title,str(exc))
    def run(self,operation,completed):
        if not self.idle():return
        from .gui import M16ReviewThread
        w=self.w;worker=M16ReviewThread(operation,w);w.worker=worker
        worker.done.connect(completed);worker.failed.connect(w.job_failed)
        worker.finished.connect(lambda:w._busy(False))
        w._busy(True);w.statusBar().showMessage("M18-Integration läuft …");worker.start()
    def set_deck(self,value):
        if value:
            # Drop old commands instead of replaying them when enabled.
            take_commands()
        self.deck=value
    def configure_obs(self):
        choices=["OBS-Aufnahme","OBS-Stream","Editor-Modus (OBS trennen)"]
        choice,ok=QInputDialog.getItem(self.w,"OBS","Zeitbasis:",choices,0,False)
        if not ok:return
        if choice==choices[2]:
            self.obs_password=None;self.obs_session=None;return
        session,ok=QInputDialog.getText(self.w,"OBS","Eindeutiger Sitzungsname (später der Aufnahme zuordnen):")
        if not ok or not session.strip():return
        port,ok=QInputDialog.getInt(self.w,"OBS","Lokaler WebSocket-Port",4455,1024,65535)
        if not ok:return
        secret,ok=QInputDialog.getText(self.w,"OBS","WebSocket-Passwort (nur Sitzung)",QLineEdit.EchoMode.Password)
        if not ok:return
        self.obs_password=secret;self.obs_session=session.strip();self.obs_port=port
        self.obs_kind="obs-record" if choice==choices[0] else "obs-stream"
        self.w.statusBar().showMessage("OBS-Zeitbasis gewählt – Verbindung beim nächsten Marker")
    def mark(self):
        if self.obs_session is not None:
            session=self.obs_session;kind=self.obs_kind;password=self.obs_password;port=self.obs_port
            # Network request off GUI; reject if an unrelated job is active.
            self.run(lambda cancel:record_marker(session,obs_seconds(password,kind,port),kind),
                     lambda _:self.w.statusBar().showMessage("OBS-Zeitmarke gespeichert"))
        elif self.w.source and self.idle():
            try:record_marker(str(Path(self.w.source).resolve()),self.w._source_position_seconds())
            except (ValueError,OSError) as exc:self.error("Zeitmarke",exc);return
            self.w.statusBar().showMessage("Editor-Zeitmarke gespeichert")
    def import_markers(self):
        if not self.idle() or not self.w._video_info:return
        kind,ok=QInputDialog.getItem(self.w,"Marker","Zeitbasis auswählen:",["source","obs-record","obs-stream"],0,False)
        if not ok:return
        if kind=="source":session=str(Path(self.w.source).resolve())
        else:
            session,ok=QInputDialog.getText(self.w,"Marker","OBS-Sitzungsname:",text=self.obs_session or "")
            if not ok:return
        offset,ok=QInputDialog.getDouble(self.w,"Marker","Zeitversatz zur geöffneten Originalaufnahme (s):",0,-86400,86400,3)
        if not ok:return
        points=[t+offset for t in markers(session,kind) if 0<=t+offset<self.w._video_info.duration]
        if not points:self.error("Marker","Keine passenden Marker");return
        if QMessageBox.question(self.w,"Marker",f"{len(points)} Zeitmarken als manuelle Highlights übernehmen? Zeitbasis selbst prüfen.")!=QMessageBox.StandardButton.Yes:return
        for t in points[:100]:
            a=max(0,t-5);z=min(self.w._video_info.duration,t+15)
            if z-a>=.2:
                self.w.manual_label.setText("OBS / Stream Deck Marker");self.w.add_manual_interval(a,z)
    def configure_watch(self):
        if self.watch and QMessageBox.question(self.w,"Watch Folder","Aktuellen Ordner pausieren?") == QMessageBox.StandardButton.Yes:
            self.watch=None;return
        path=QFileDialog.getExistingDirectory(self.w,"Aufnahmen überwachen (nur diese Sitzung)")
        if path:
            try:self.watch=WatchFolder(path);self.ready=[];self.next_watch=0.
            except (OSError,ValueError) as exc:self.error("Watch Folder",exc)
    def open_watched(self):
        if not self.idle():return
        self.ready=[p for p in self.ready if p.is_file()]
        if not self.ready:self.error("Watch Folder","Keine neuen stabilen Aufnahmen");return
        labels=[str(p) for p in self.ready]
        choice,ok=QInputDialog.getItem(self.w,"Watch Folder","Aufnahme auswählen:",labels,0,False)
        if ok and self.w.confirm_discard_edits():
            if self.w.load_video_source(choice):self.ready.remove(Path(choice))
    def manage_channels(self):
        if not self.idle():return
        try:self.channels=load(self.channels_path)
        except (OSError,ValueError,TypeError,KeyError) as exc:self.error("Kanalaufnahme",exc);return
        labels=["Neuen autorisierten Kanal hinzufügen"]+[f"{i+1}. {c.url} · {'pausiert' if c.paused else 'aktiv'}" for i,c in enumerate(self.channels)]
        choice,ok=QInputDialog.getItem(self.w,"Kanalaufnahme","Konfiguration (kein Abruf ohne Sitzungsfreigabe):",labels,0,False)
        if not ok:return
        if choice==labels[0]:
            raw,ok=QInputDialog.getText(self.w,"Kanal","Eigener / ausdrücklich autorisierter Kanal:")
            if not ok:return
            try:s=parse_channel(raw)
            except (ValueError,TypeError) as exc:self.error("Kanal",exc);return
            if any(c.url==s.url for c in self.channels):self.error("Kanal","Bereits registriert");return
            if QMessageBox.question(self.w,"Nutzungsrechte","Automatische Downloads dieses Kanals sind ausdrücklich autorisiert? Plattformbedingungen gelten.")!=QMessageBox.StandardButton.Yes:return
            target=QFileDialog.getExistingDirectory(self.w,"Kanal-Zielordner")
            if not target:return
            interval,ok=QInputDialog.getInt(self.w,"Abrufintervall","Minuten",60,15,1440)
            if not ok:return
            count,ok=QInputDialog.getInt(self.w,"Mengenlimit","Maximal neue Videos je Prüfung",1,1,5)
            if not ok:return
            size,ok=QInputDialog.getInt(self.w,"Speicherlimit","Maximal GiB pro Video",4,1,32)
            if not ok:return
            self.channels.append(Channel(s.url,s.provider,target,interval,count,size*1024**3,paused=False))
        else:
            i=labels.index(choice)-1;c=self.channels[i]
            action,ok=QInputDialog.getItem(self.w,"Kanal","Aktion:",["Aktivieren/Pausieren","Registrierung löschen (keine Medien löschen)"],0,False)
            if not ok:return
            if action.startswith("Registrierung"):self.channels.pop(i)
            else:self.channels[i]=replace(c,paused=not c.paused)
        try:save(self.channels_path,self.channels)
        except (ValueError,OSError) as exc:self.error("Kanal",exc)
    def toggle_channels(self):
        if self.channels_enabled:
            self.channels_enabled=False
            self.w.statusBar().showMessage("Kanalaufnahme pausiert – laufenden Import bei Bedarf abbrechen");return
        if not self.idle():return
        try:self.channels=load(self.channels_path)
        except (ValueError,OSError,TypeError,KeyError) as exc:self.error("Kanal",exc);return
        if not any(not c.paused for c in self.channels):self.error("Kanal","Kein aktiver Kanal");return
        if QMessageBox.question(self.w,"Kanalaufnahme","Autorisierte Kanäle während dieser App-Sitzung prüfen und neue Videos automatisch innerhalb der Limits importieren? Erster Abruf speichert nur den Ausgangsbestand.")!=QMessageBox.StandardButton.Yes:return
        self.channels_enabled=True;self.next_channel=0
    def tick(self):
        if QApplication.activeModalWidget() is not None:return
        now=time.monotonic()
        if self.watch and now>=self.next_watch:
            self.next_watch=now+5
            try:
                found=self.watch.scan(now)
                if found:
                    self.ready=list(dict.fromkeys(self.ready+found))[-1000:]
                    self.w.statusBar().showMessage(f"Watch Folder: {len(self.ready)} stabile Aufnahme(n) verfügbar")
            except OSError:
                self.watch=None;self.w.statusBar().showMessage("Watch Folder nicht erreichbar – pausiert")
        if self.deck:
            for cmd in take_commands():
                if not self.idle():continue
                {"marker":self.mark,"play-pause":self.w.toggle_play,"manual-in":self.w.mark_highlight_start,
                 "manual-out":self.w.mark_highlight_end,"manual-create":self.w.add_marked_highlight}[cmd]()
        if self.channels_enabled and now>=self.next_channel and self.idle():
            self.next_channel=now+30
            i=next((i for i,c in enumerate(self.channels) if not c.paused and c.next_check<=time.time()),None)
            if i is not None:
                initial=self.channels[i];snapshot=list(self.channels)
                def operation(cancel):
                    def persist(c):
                        snapshot[i]=c;save(self.channels_path,snapshot)
                    try:poll(initial,persist=persist,cancelled=cancel)
                    except Exception:
                        # Safe generic error; reload persisted next-check rather than loop.
                        return False
                    return True
                def completed(success):
                    try:self.channels=load(self.channels_path)
                    except Exception:self.channels_enabled=False
                    self.w.statusBar().showMessage("Kanalprüfung abgeschlossen" if success else "Kanalprüfung fehlgeschlagen – nächster regulärer Abruf")
                self.run(operation,completed)
    def nle(self):
        w=self.w
        if not self.idle() or not w.analysis:return
        path,_=QFileDialog.getSaveFileName(w,"Schnittliste (nur Schnitte, keine Effekte)","Highlights.fcpxml","FCPXML (*.fcpxml);;CMX3600 (*.edl)")
        if not path:return
        from .nle_export import export_nle
        intervals=[]
        from .editor_project import scene_plan_for
        for c in w.analysis.candidates:
            plan=scene_plan_for(w.editor_project,c.start,c.end)
            intervals.extend([(s.start,s.end) for s in plan.output_scenes] if plan else [(c.start,c.end)])
        try:target=export_nle(w.analysis.video,intervals,path)
        except (ValueError,OSError) as exc:self.error("NLE",exc);return
        w.statusBar().showMessage("Schnittliste exportiert: "+str(target))
    def alternative(self):
        w=self.w
        if not self.idle() or not w.analysis or not w.apply_word_editor() or not w.apply_transcript_editor():return
        c=w.selected_candidate()
        if c is None:return
        from .editor_project import scene_plan_for
        from .render_contract import RenderRequest
        from .gui import render_transcript
        from .alternative_export import export_alternative
        if not w._scene_render_allowed(w.analysis.video,[(c.start,c.end)]):return
        scene=scene_plan_for(w.editor_project,c.start,c.end)
        transcript=render_transcript(w.analysis,c.start,c.end,scene,w.burn_subtitles.isChecked(),w.caption_offset.value())
        req=RenderRequest(video=w.analysis.video,start=c.start,end=c.end,mode=str(w.mode.currentData()),
            transcript=tuple(transcript),burn_subtitles=w.burn_subtitles.isChecked() and bool(transcript),
            subtitle_offset=w.caption_offset.value(),caption_style=w._current_caption_style(),
            project=w.editor_project if w.include_track_audio.isChecked() else None,
            scene_plan=scene,encoder=str(w.encoder_mode.currentData()))
        path,_=QFileDialog.getSaveFileName(w,"Alternative Ausgabe","Highlight.webm","WebM (*.webm);;GIF ohne Ton (*.gif)")
        if path:self.run(lambda cancel:export_alternative(req,path,cancelled=cancel),
                         lambda p:QMessageBox.information(w,"Export",str(p)))
    def subtitles(self):
        w=self.w
        if not self.idle() or not w._video_info or not w.apply_word_editor() or not w.apply_transcript_editor():return
        path,_=QFileDialog.getOpenFileName(w,"Vorhandene Untertitel","","Untertitel (*.srt *.vtt)")
        if not path:return
        from .subtitle_import import load_subtitles
        from .models import AnalysisResult
        try:cues=load_subtitles(path,w._video_info.duration)
        except (OSError,ValueError) as exc:self.error("Untertitel",exc);return
        previous=w.analysis or AnalysisResult(w._video_info,[])
        if QMessageBox.question(w,"Untertitel",f"{len(cues)} vorhandene Untertitel übernehmen? Aktuelles Transkript wird ersetzt (Undo verfügbar).")!=QMessageBox.StandardButton.Yes:return
        w.analysis_finished(replace(previous,transcript=cues,translations=(),caption_language=""),preserve_history=True)
        w._register_edit(previous)
    def youtube(self):
        if not self.idle():return
        from .publish_prepare import authorize_youtube
        from . import publish_credentials as vault
        action,ok=QInputDialog.getItem(self.w,"YouTube OAuth (M18)","Nur Kontovorbereitung, kein Upload:",
            ["Registrierte Desktop-App verbinden","Gespeicherten Token laden","Lokalen Token entfernen"],0,False)
        if not ok:return
        client,ok=QInputDialog.getText(self.w,"Google Desktop Client","Registrierte OAuth-Client-ID:")
        if not ok:return
        try:vault.target(client)
        except ValueError as exc:self.error("YouTube",exc);return
        if action=="Lokalen Token entfernen":
            self.youtube_token=None
            if vault.supported():
                try:vault.remove(client)
                except (OSError,RuntimeError) as exc:self.error("YouTube",exc)
            return
        if action=="Gespeicherten Token laden":
            if not vault.supported():self.error("YouTube","Windows-Tokenspeicher nicht verfügbar");return
            try:self.youtube_token=vault.read(client)
            except (OSError,RuntimeError) as exc:self.error("YouTube",exc);return
            self.w.statusBar().showMessage("Token lokal geladen; API-Zugriff noch nicht validiert" if self.youtube_token else "Kein Token gespeichert")
            return
        secret,ok=QInputDialog.getText(self.w,"Google Desktop Client","Client-Secret (nur Sitzung):",QLineEdit.EchoMode.Password)
        if not ok:return
        if QMessageBox.question(self.w,"YouTube OAuth","Offiziellen Google-Systembrowser-Login mit Upload-Scope öffnen? Es werden keine Medien übertragen.")!=QMessageBox.StandardButton.Yes:return
        remember=vault.supported() and QMessageBox.question(self.w,"Tokenspeicher","Token in Windows Credential Manager speichern? Nein = nur Sitzung.")==QMessageBox.StandardButton.Yes
        def operation(cancel):
            return authorize_youtube(client,secret,authorized=True,cancelled=cancel)
        def complete(token):
            self.youtube_token=token
            if remember:
                try:vault.save(client,token)
                except (ValueError,OSError,RuntimeError) as exc:self.error("Tokenspeicher",exc)
            self.w.statusBar().showMessage("OAuth-Autorisierung erhalten – kein Upload, keine API-Abnahme")
        self.run(operation,complete)
    def language(self):
        from .m18_language import apply_language,english_enabled
        choice,ok=QInputDialog.getItem(self.w,"Language / Sprache","Interface / Oberfläche:",["Deutsch","English (partial)"],int(english_enabled()),False)
        if ok:
            try:apply_language(self.w,choice.startswith("English"))
            except OSError as exc:self.error("Language",exc)
