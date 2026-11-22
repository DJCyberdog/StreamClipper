"""M11b: versioned multitrack metadata without media/Qt/ML dependencies."""
from dataclasses import replace
import json
import pytest
from streamclipper.editor_project import (
    EditorProject, ProjectHistory, Track, TimelineItem, SCHEMA_VERSION,
    add_item, add_track, edit_item, initial_project, load_project,
    move_track, project_path, remove_track, rename_track, save_project, toggle_track)
from streamclipper.models import VideoInfo

def video(tmp_path):
    return VideoInfo(str(tmp_path/"long recording.mkv"), 21600, 1920, 1080, 60, True)

def test_initial_tracks_are_named_and_cover_six_hours(tmp_path):
    project=initial_project(video(tmp_path))
    assert [t.kind for t in project.tracks]==["video","audio","audio","captions","overlay"]
    assert project.items[0].source_end==21600
    assert project.items[0].track_id=="gameplay"
    assert project.schema_version==SCHEMA_VERSION

def test_edit_tracks_and_clips_with_lock_protection(tmp_path):
    project=initial_project(video(tmp_path))
    added=add_track(project,"audio","Soundeffekte")
    assert len(added.tracks)==6
    track_id=added.tracks[-1].id
    renamed=rename_track(added,track_id,"  Voice-Over  ")
    assert renamed.tracks[-1].name=="Voice-Over"
    moved=move_track(renamed,track_id,-1)
    assert moved.tracks[-2].id==track_id
    item=add_item(moved,track_id,100,120,20,"Kommentar")
    assert len(item.items)==2
    adjusted=edit_item(item,item.items[-1].id,source_start=101,timeline_start=21)
    assert adjusted.items[-1].source_start==101
    locked=toggle_track(adjusted,track_id,"locked")
    with pytest.raises(ValueError,match="Gesperrte Spur"):
        edit_item(locked,adjusted.items[-1].id,source_end=118)
    with pytest.raises(ValueError,match="enthält Clips"):
        remove_track(adjusted,track_id)
    assert project.items[0].source_start==0

def test_project_history_undo_redo_and_divergence(tmp_path):
    start=initial_project(video(tmp_path))
    added=add_track(start,"audio","Voice")
    renamed=rename_track(added,added.tracks[-1].id,"Voice 2")
    history=ProjectHistory()
    history.record(start,added)
    history.record(added,renamed)
    assert history.undo(renamed)==added
    assert history.undo(added)==start
    assert history.redo(start)==added
    other=toggle_track(added,"mic","muted")
    history.record(added,other)
    assert not history.can_redo
    with pytest.raises(ValueError,match="nicht konsistent"):
        history.undo(start)

def test_editor_project_roundtrip_and_source_guard(tmp_path):
    clip=tmp_path/"long recording.mkv"
    clip.write_bytes(b"unchanged footage")
    info=video(tmp_path)
    project=add_item(initial_project(info),"music",100,130,200,"Musik")
    file=save_project(project,root=tmp_path/"projects")
    assert file==project_path(clip,root=tmp_path/"projects")
    assert load_project(info,root=tmp_path/"projects")==project
    assert clip.read_bytes()==b"unchanged footage"
    with pytest.raises(ValueError,match="anderen Videoaufnahme"):
        load_project(replace(info,width=1280),root=tmp_path/"projects")

def test_corrupt_project_not_accepted_and_valid_file_preserved(tmp_path):
    info=video(tmp_path)
    project=initial_project(info)
    file=save_project(project,root=tmp_path)
    original=file.read_bytes()
    for document in (
        {"schema_version":99,"source":{},"tracks":[],"items":[]},
        {"schema_version":1,"source":project.source.__dict__,
         "tracks":[{"id":"gameplay","kind":"video","name":"Main"}]*2,
         "items":[]},
    ):
        file.write_text(json.dumps(document))
        with pytest.raises(ValueError):
            load_project(info,root=tmp_path)
    file.write_bytes(original)
    assert load_project(info,root=tmp_path)==project

def test_bad_clip_time_and_unexpected_ids_rejected(tmp_path):
    project=initial_project(video(tmp_path))
    with pytest.raises(ValueError,match="Zeitbereich"):
        add_item(project,"music",10,22000,0)
    with pytest.raises(ValueError,match="Zeitbereich"):
        edit_item(project,"source",source_start=100,source_end=10)
    bad=replace(project,tracks=(Track("!!","video","Main"),))
    with pytest.raises(ValueError,match="Ungültige"):
        bad.validate()
    with pytest.raises(ValueError,match="Hauptvideospur"):
        remove_track(project,"gameplay")
