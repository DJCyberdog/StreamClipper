from streamclipper.overlay_recognition import LABELS, REGIONS, classify, proposals


def scores(kind, value=.6):
    return {k: value if k==kind else (1-value)/(len(LABELS)-1) for k,_ in LABELS}


def test_neutral_controls_and_ambiguous_scores():
    assert classify(scores("gameplay"),1,REGIONS[0]) is None
    assert classify(scores("hud",.15),1,REGIONS[0]) is None
    assert classify(scores("chat"),1,REGIONS[0]).kind=="chat"


def test_repeated_overlay_is_disabled_and_unmasked():
    times=[1.,2.,3.]
    hits=[classify(scores("topbar"),t,REGIONS[0]) for t in times]
    zones=proposals(hits,times,0,4)
    assert len(zones)==1 and zones[0].kind=="topbar"
    assert zones[0].start is None
    assert not zones[0].enabled and not zones[0].mask


def test_transient_alert_has_bounded_window():
    times=[1.,2.,3.,4.]
    hits=[classify(scores("alert"),2.,REGIONS[-1])]
    zones=proposals(hits,times,0,5)
    assert len(zones)==1
    assert (zones[0].start,zones[0].end)==(1.5,2.5)
    assert not zones[0].enabled


def test_unrepeated_non_alert_rejected_and_gap_not_bridged():
    times=[1.,2.,3.,4.]
    hits=[classify(scores("hud"),t,REGIONS[2]) for t in (1.,3.)]
    assert proposals(hits,times,0,5)==()
