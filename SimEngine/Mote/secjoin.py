"""
Secure joining layer of a mote.
"""

# =========================== imports =========================================

import copy

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

        # singletons (quicker access, instead of recreating every time)
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
                SimEngine.SimLog.LOG_SECJOIN_TX,
                {
                    '_mote_id': self.mote.id,
                }
            )
            
            # create join request
            joinRequest = {
                'type':                     d.PKT_TYPE_JOIN_REQUEST,
                'app': {
                },
                'net': {
                    'srcIp':                self.mote.id,                      # from pledge (this mote)
                    'dstIp':                self.mote.tsch.join_proxy,         # to join proxy
                    'packet_length':        d.PKT_LEN_JOIN_REQUEST,
                },
            }
            
            # send join request
            self.mote.sixlowpan.sendPacket(joinRequest)
            
        else:
            # consider I'm already joined
            self.setIsJoined(True) # forced (secjoin_enabled==False)
    
    # from lower stack
    
    def receive(self, packet):
        
        if   packet['type']== d.PKT_TYPE_JOIN_REQUEST:
            
            if self.mote.dagRoot==False:
                # I'm the join proxy
                
                assert self.mote.dodagId!=None
                
                # proxy join request to dagRoot
                proxiedJoinRequest = {
                    'type':                 d.PKT_TYPE_JOIN_REQUEST,
                    'app': {
                        'stateless_proxy': {
                            'pledge_id':    packet['mac']['srcMac']
                        }
                    },
                    'net': {
                        'srcIp':            self.mote.id,                      # join proxy (this mote)
                        'dstIp':            self.mote.dodagId,                 # from dagRoot
                        'packet_length':    packet['net']['packet_length'],
                    },
                }
                
                # send proxied join response
                self.mote.sixlowpan.sendPacket(proxiedJoinRequest)
            
            else:
                # I'm the dagRoot
            
                # echo back 'stateless_proxy' element in the join response, if present in the join request
                app = {}
                if 'stateless_proxy' in packet['app']:
                    app['stateless_proxy'] = copy.deepcopy(packet['app']['stateless_proxy'])
                
                # format join response
                joinResponse = {
                    'type':                 d.PKT_TYPE_JOIN_RESPONSE,
                    'app':                  app,
                    'net': {
                        'srcIp':            self.mote.id,                      # from dagRoot (this mote)
                        'dstIp':            packet['net']['srcIp'],            # to join proxy
                        'packet_length':    d.PKT_LEN_JOIN_RESPONSE,
                    },
                }
                
                # send join response
                self.mote.sixlowpan.sendPacket(joinResponse)
            
        elif packet['type']== d.PKT_TYPE_JOIN_RESPONSE:
            assert self.mote.dagRoot==False
            
            if self.getIsJoined()==True:
                # I'm the join proxy
                
                # remove the 'stateless_proxy' element from the app payload
                app       = copy.deepcopy(packet['app'])
                pledge_id = app['stateless_proxy']['pledge_id']
                del app['stateless_proxy']
                
                # proxy join response to pledge
                proxiedJoinResponse = {
                    'type':                 d.PKT_TYPE_JOIN_RESPONSE,
                    'app':                  app,
                    'net': {
                        'srcIp':            self.mote.id,                      # join proxy (this mote)
                        'dstIp':            pledge_id,                         # to pledge
                        'packet_length':    packet['net']['packet_length'],
                    },
                }
                
                # send proxied join response
                self.mote.sixlowpan.sendPacket(proxiedJoinResponse)
            
            else:
                # I'm the pledge
            
                # I'm now joined!
                self.setIsJoined(True) # mote
        else:
            raise SystemError()

    #======================== private ==========================================
