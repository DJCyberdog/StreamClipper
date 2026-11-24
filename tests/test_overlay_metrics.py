from dataclasses import replace
from streamclipper.smart_director import OverlayZone
from streamclipper.overlay_metrics import evaluate_zones


def test_duplicates_are_false_positives_and_disabled_proposals_count():
    zone=OverlayZone("hud",(0,0,.2,.2),enabled=False)
    m=evaluate_zones([zone,zone],[zone],0,4)
    assert (m.true_positives,m.false_positives,m.false_negatives)==(1,1,0)
    assert m.precision==.5 and m.recall==1


def test_wrong_type_or_time_is_not_a_match():
    z=OverlayZone("alert",(0,0,.2,.2),1,2)
    m=evaluate_zones([replace(z,kind="hud"),replace(z,start=3,end=4)],[z],0,4)
    assert (m.true_positives,m.false_positives,m.false_negatives)==(0,2,1)


def test_maximum_cardinality_not_greedy():
    a=OverlayZone("hud",(0,0,.4,.4))
    b=OverlayZone("hud",(.2,0,.4,.4))
    broad=OverlayZone("hud",(.1,0,.4,.4))
    m=evaluate_zones([broad,a],[a,b],0,4,spatial=.5)
    assert m.true_positives==2


def test_empty_negative_control():
    m=evaluate_zones([],[],0,4)
    assert m.true_positives==m.false_positives==m.false_negatives==0
    assert m.precision is None and m.recall is None
