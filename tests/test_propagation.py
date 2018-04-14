import pytest

from SimEngine import Propagation, Mote

def test_propagation_from_trace_get_pdr(sim):
    sim(**{'trace': 'traces/grenoble.k7.gz',
           'fullyMeshed': False,
           'squareSide': 20})
    asn = 10
    source = Mote.Mote(1)
    destination = Mote.Mote(2)
    channel = 11
    propagation = Propagation.PropagationTrace(trace='traces/grenoble.k7.gz')

    propagation.get_pdr(source, destination, asn=asn, channel=channel)
    propagation.get_pdr(source, destination, asn=asn)
    propagation.get_pdr(source, destination, channel=channel)
