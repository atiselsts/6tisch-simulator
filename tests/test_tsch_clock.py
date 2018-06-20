import test_utils as u
import SimEngine.Mote.MoteDefines as d
from SimEngine import SimLog


def test_tsch_clock(sim_engine):
    sim_engine = sim_engine(
        diff_config = {
            'exec_numMotes'           : 2,
            'app_pkPeriod'            : 0,
            'app_pkPeriodVar'         : 0,
            'tsch_probBcast_ebDioProb': 0,
            'exec_numSlotframesPerRun': 1000,
        }
    )
    log_type_clock_diff = 'clock_diff'
    sim_log = SimLog.SimLog()
    sim_log.set_log_filters([SimLog.LOG_SIMULATOR_STATE, log_type_clock_diff])

    # shorthands
    root             = sim_engine.motes[0]
    mote_1           = sim_engine.motes[1]
    slot_duration    = sim_engine.settings.tsch_slotDuration
    slotframe_length = sim_engine.settings.tsch_slotframeLength
    max_drift        = sim_engine.settings.tsch_clock_max_drift_ppm
    clock_interval   = 1.0 / sim_engine.settings.tsch_clock_frequency

    def _log_clock_drift():
        # without keep-alive, difference between the two clocks is
        # getting bigger and bigger. but, it should be within
        # -max_drift*2 and +max_drift*2 with offset in the range
        # between 0 and clock_interval*2

        diff = root.tsch.clock.get_drift() - mote_1.tsch.clock.get_drift()
        elapsed_time = sim_engine.getAsn() * slot_duration
        lower_bound_drift = (
            elapsed_time * (-1 * max_drift * 2) - clock_interval * 2
        )
        upper_bound_drift = (
            elapsed_time * (+1 * max_drift * 2) + clock_interval * 2
        )
        assert lower_bound_drift < diff
        assert diff < upper_bound_drift
        # custom log
        sim_log.log(
            {'type': log_type_clock_diff, 'keys': ['value']},
            {'value': diff}
        )
        _schedule_clock_drift_logging()

    def _schedule_clock_drift_logging():
        sim_engine.scheduleAtAsn(
            asn            = slotframe_length + sim_engine.getAsn(),
            cb             = _log_clock_drift,
            uniqueTag      = 'log_clock_drift',
            intraSlotOrder = d.INTRASLOTORDER_ADMINTASKS
        )

    # sync mote_1's clock to mote_0's one
    mote_1.tsch.clock.sync(root.id)
    _schedule_clock_drift_logging()
    u.run_until_end(sim_engine)
