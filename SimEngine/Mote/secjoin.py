"""
Secure joining layer of a mote.
"""

# =========================== imports =========================================

# Mote sub-modules
import MoteDefines as d

# Simulator-wide modules
import SimEngine

# =========================== defines =========================================

# =========================== helpers =========================================

# =========================== body ============================================

class SecJoin(object):

    def __init__(self, mote):

        # store params
        self.mote                           = mote

        # singletons (to access quicker than recreate every time)
        self.engine                         = SimEngine.SimEngine.SimEngine()
        self.settings                       = SimEngine.SimSettings.SimSettings()
        self.log                            = SimEngine.SimLog.SimLog().log

        # local variables
        self._isJoined                      = False

    #======================== public ==========================================
    
    # getters/setters
    
    def setIsJoined(self, newState):
        assert newState in [True, False]
        
        # log
        self.log(
            SimEngine.SimLog.LOG_JOINED,
            {
                '_mote_id': self.mote.id,
            }
        )
        
        # record
        self._isJoined = newState
    def getIsJoined(self):
        return self._isJoined
    
    # admin
    
    def startJoinProcess(self):
        
        assert self.mote.dagRoot==False
        assert self.mote.tsch.getIsSync()==True
        assert self.mote.tsch.join_proxy!=None
        assert self.getIsJoined()==False
        
        if self.settings.secjoin_enabled:
            
            # log
            self.log(
                SimEngine.SimLog.LOG_JOIN_TX,
                {
                    '_mote_id': self.mote.id,
                }
            )
        
            # create join request
            newJoinRequest = {
                'type':              d.PKT_TYPE_JOIN_REQUEST,
                'app': {
                },
                'net': {
                    'srcIp':         self.mote.id,              # from mote
                    'dstIp':         self.mote.tsch.join_proxy, # to join proxy
                    'packet_length': d.PKT_LEN_JOIN_REQUEST,
                },
            }
            
            # send join request
            self.mote.sixlowpan.sendPacket(newJoinRequest)
            
        else:
            # consider I'm already joined
            self.setIsJoined(True)
    
    # from lower stack
    
    def receive(self, packet):
        
        if   packet['type']== d.PKT_TYPE_JOIN_REQUEST:
        
            if self.mote.dagRoot==False:
                # I'm the join proxy
                
                # forward to DAGroot
                raise NotImplementedError()
            
            else:
                # I'm the dagRoot
            
                # create join response
                newJoinResponse = {
                    'type':              d.PKT_TYPE_JOIN_RESPONSE,
                    'app': {
                    },
                    'net': {
                        'srcIp':         self.mote.id,              # from dagRoot
                        'dstIp':         packet['net']['srcIp'],    # to sender
                        'packet_length': d.PKT_LEN_JOIN_RESPONSE,
                    },
                }
                
                # send join response
                self.mote.sixlowpan.sendPacket(newJoinResponse)
            
        elif packet['type']== d.PKT_TYPE_JOIN_RESPONSE:
            assert self.mote.dagRoot==False
            
            if self.getIsJoined()==True:
                # I'm the join proxy
                
                # forward to pledge
                raise NotImplementedError()
            
            else:
                # I'm the pledge
            
                # I'm now joined!
                self.setIsJoined(True)
        else:
            raise SystemError()

    def areAllNeighborsJoined(self):
        """
        Are all my neighbors joined?
        """
        return [nei for nei in self.mote._myNeighbors() if self.engine.motes[nei].secjoin.getIsJoined()==True]

    #======================== private ==========================================
