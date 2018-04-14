import pytest

from SimEngine import Propagation, Mote

pytestmark = pytest.mark.skip('fails randomly; skip this for now (issue #90)')


def test_propagation_from_trace_get_pdr(settings):
    settings(**{'trace': 'traces/grenoble.k7',
                'fullyMeshed': False,
                'squareSide': 20})
    asn = 10
    source = Mote.Mote(1)
    destination = Mote.Mote(2)
    channel = 11
    propagation = Propagation.PropagationTrace(trace='traces/grenoble.k7')

    propagation.get_pdr(source, destination, asn=asn, channel=channel)
    propagation.get_pdr(source, destination, asn=asn)
    propagation.get_pdr(source, destination, channel=channel)
