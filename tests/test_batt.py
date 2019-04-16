import test_utils as u
import SimEngine.Mote.MoteDefines as d
from SimEngine import SimLog

def test_energy_consumption(sim_engine):
    sim_engine = sim_engine(
        {
            'exec_numMotes'  : 2,
            'exec_randomSeed': 0
        }
    )

    u.run_until_end(sim_engine)

    # confirm we can have the same consumption using radio.stats as
    # "charge"
    for mote_id in [0, 1]:
        mote = sim_engine.motes[mote_id]
        stats = mote.radio.stats
        assert (
            stats['last_updated'] == (
                stats['idle_listen'] +
                stats['tx_data_rx_ack'] +
                stats['rx_data_tx_ack'] +
                stats['tx_data'] +
                stats['rx_data'] +
                stats['sleep']
            )
        )
        consumption =  stats['idle_listen'] * d.CHARGE_IdleListen_uC
        consumption += stats['tx_data_rx_ack'] * d.CHARGE_TxDataRxAck_uC
        consumption += stats['rx_data_tx_ack'] * d.CHARGE_RxDataTxAck_uC
        consumption += stats['tx_data'] * d.CHARGE_TxData_uC
        consumption += stats['rx_data'] * d.CHARGE_RxData_uC
        consumption += stats['sleep'] * d.CHARGE_Sleep_uC
        # computation of float values will have errros; we compare the
        # two values having round()
        assert round(consumption, 1) == round(mote.batt.chargeConsumed, 1)
