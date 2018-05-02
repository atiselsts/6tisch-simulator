import pprint

pp = pprint.PrettyPrinter(indent=4)

# =========================== helpers =========================================

def kpi_formation():
    returnVal = {
        'formation': 'TODO',
        # per node?
    }
    return returnVal

def kpi_reliability():
    returnVal = {
        'reliability': 'TODO',
        # per node?
    }
    return returnVal

def kpi_latency():
    returnVal = {
        'latency': 'TODO',
        # per node?
        # min/avg/max?
        # std
    }
    return returnVal

def kpi_consumption():
    returnVal = {
        'avg': 'TODO',
        # per node?
        # per hop?
        # first death?
        # last death?
        # lifetime for different batteries?
    }
    return returnVal

# =========================== main ============================================

def all_kpis():
    kpis = {}
    kpis['formation']   = kpi_formation()
    kpis['reliability'] = kpi_reliability()
    kpis['latency']     = kpi_latency()
    kpis['consumption'] = kpi_consumption()
    return kpis

def main():
    kpis = all_kpis()
    pp.pprint(kpis)
    
if __name__=='__main__':
    main()

