import tests.test_utils as u

def test_free_run(sim_engine):
    sim_engine = sim_engine(
        diff_config = {'rpl_of': 'OFBestLinkPDR'}
    )
    u.run_until_end(sim_engine)
