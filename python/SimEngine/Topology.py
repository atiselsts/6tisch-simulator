#!/usr/bin/python

'''
 @authors:
       Thomas Watteyne    <watteyne@eecs.berkeley.edu>    
       Xavier Vilajosana  <xvilajosana@uoc.edu> 
                          <xvilajosana@eecs.berkeley.edu>
'''

import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
log = logging.getLogger('Topology')
log.setLevel(logging.ERROR)
log.addHandler(NullHandler())

import threading
import random
import math

import Propagation
import Mote
from SimSettings import SimSettings as s

class Topology(object):
    
     #======================== singleton pattern ===============================
    
    _instance       = None
    _init           = False
    
    RANDOM          = "RANDOM"
    FULL_MESH       = "FULL_MESH"
    BINARY_TREE     = "BINARY_TREE"
    LINE            = "LINE"
    LATTICE         = "LATTICE"
    MIN_DISTANCE    = "MIN_DISTANCE"
    RADIUS_DISTANCE = "RADIUS_DISTANCE"
    MAX_RSSI        = "MAX_RSSI"
    DODAG_TOPOLOGY  = "DODAG_TOPOLOGY"
    
    NEIGHBOR_RADIUS = 0.05 # in km 
    
    TWO_DOT_FOUR_GHZ = 2400000000 #in hertz
    PISTER_HACK_LOWER_SHIFT = 40 #-40 db     
    SPEED_OF_LIGHT = 299792458 
    
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Topology,cls).__new__(cls, *args, **kwargs)
        return cls._instance
    
    def __init__(self):
        
        # don't re-initialize an instance (needed because singleton)
        if self._init:
            return
        self._init = True
        
        # store params
        
        # variables
        self.dataLock            = threading.Lock()
        self.motes=[Mote.Mote(id) for id in range(s().numMotes)]
         
    def createTopology(self,type):
        
        # set RSSI between any two nodes
        self.computeRSSI()
        
        # set the mote's traffic goals
        if type == self.RANDOM:
             self._createRandomTopology()
        elif type == self.FULL_MESH:
            #make sure that the traffic requirements can be met with that so demanding topology.
            self._createFullMeshTopology()   
        elif type == self.BINARY_TREE:
            self._createBTreeTopology()
        elif type == self.LINE:
            raise NotImplementedError('Mode {0} not implemented'.format(type))         
        elif type == self.LATTICE:
            raise NotImplementedError('Mode {0} not implemented'.format(type))
        elif type == self.MIN_DISTANCE:
            self._createMinDistanceTopology()
        elif type == self.RADIUS_DISTANCE:
            self._createRadiusDistanceTopology()
        elif type == self.MAX_RSSI:
            self._createMaxRssiTopology()
        elif type == self.DODAG_TOPOLOGY:
            self._createDodagTopology()        
        else: 
            raise NotImplementedError('Mode {0} not supported'.format(type))
                
        return self.motes
    
    def _createRandomTopology(self):
        for id in range(len(self.motes)):
            neighborId = None
            #pick a random neighbor
            while (neighborId==None) or (neighborId==id):
                neighborId = random.randint(0,len(self.motes)-1)
            #initialize the traffic pattern with that neighbor    
            self.motes[id].setDataEngine(
                self.motes[neighborId],
                s().traffic,
            )
            self.motes[id].setPDR(self.motes[neighborId],
                                  self.computePDR(id,neighborId)
                                  )
            
    def _createFullMeshTopology(self):
        for id in range(len(self.motes)):
            for nei in range(len(self.motes)):
                if nei!=id:
                    #initialize the traffic pattern with that neighbor
                    self.motes[id].setDataEngine(
                        self.motes[nei],
                        s().traffic,
                    )
                    self.motes[id].setPDR(
                        self.motes[nei],
                        self.computePDR(id,nei)
                    )
                    

    def _addChild(self, id,child):
        print 'i {0}'.format(id)
        #downstream link
        self.motes[id].setDataEngine(self.motes[child], s().traffic)
        #upstream link
        self.motes[child].setDataEngine(self.motes[id], s().traffic)

    def _createBTreeTopology(self):
        print 'len {0}, {1}'.format(len(self.motes),(len(self.motes)/2))
        for id in range((len(self.motes)/2)):
              self._addChild(id,(2*id) + 1)
              print 'child 1 {0}'.format((2*id)+1)
              #check if it has second child
              if (2*(id+1)<len(self.motes)):
                  #other child
                  self._addChild(id,2*(id+1))
                  print 'child 2 {0}'.format(2*(id+1))
    
    
    def _createMinDistanceTopology(self):
        for id in range(len(self.motes)):
            #link to 2 min distance neighbors
            min=10000
            linkto=-1
            for nei in range(len(self.motes)):
                if nei!=id:
                    distance=math.sqrt((self.motes[id].x - self.motes[nei].x)**2 + (self.motes[id].y - self.motes[nei].y)**2)  
                    print "distance is {0},{1},{2}".format(id,nei,distance)
                    if distance < min:
                        min=distance 
                        linkto=nei
            if linkto!=-1:
                self.motes[id].setDataEngine(self.motes[linkto], s().traffic,) 
                self.motes[id].setPDR(self.motes[linkto],self.computePDR(id,linkto))
                
            
    def _createRadiusDistanceTopology(self):
        for id in range(len(self.motes)):
            #link to all neighbors with distance smaller than radius
            for nei in range(len(self.motes)):
                if nei!=id:
                    distance=math.sqrt((self.motes[id].x - self.motes[nei].x)**2 + (self.motes[id].y - self.motes[nei].y)**2)  
                    print "distance is {0}".format(distance)
                    if distance < self.NEIGHBOR_RADIUS:
                        print "adding neighbor {0},{1}".format(id,nei)
                        self.motes[id].setDataEngine(self.motes[nei], s().traffic,) 
                        self.motes[id].setPDR(self.motes[nei],self.computePDR(id,nei))
               
    def _createMaxRssiTopology(self):
        for id in range(len(self.motes)):
            #link to a neighbor with max RSSI           
            maxNei  = None
            maxRSSI = None
            for nei in range(len(self.motes)):
                if nei!=id:
                    rssi = self.motes[id].getRSSI(nei) 
                    if maxRSSI == None:
                        maxRSSI = rssi
                        maxNei = nei                        
                    if  rssi > maxRSSI:
                        maxRSSI = rssi
                        maxNei = nei
                        
            print "adding neighbor {0},{1}".format(id,maxNei)
            self.motes[id].setDataEngine(self.motes[maxNei], s().traffic,) 
            self.motes[id].setPDR(self.motes[maxNei], self.computePDR(id, maxNei))

    def _createDodagTopology(self):
        # Create topology that all the nodes have at least one path to DAG root. 
        # If there is no path, location and RSSI of the nodes are reset.
        
        # find DAG root
        for id in range(len(self.motes)):
            if self.motes[id].dagRoot == True:
                dagRoot = id
                
        # check whether all the nodes have path to DAG root
        
        while(True):
            # start or restart with new locations and RSSI set
            for id in range(len(self.motes)):
                if (id != dagRoot):
                
                    findDagroot = False
                    paths = set()
                    checkedNodes = set()
                    candidate = id
                    while(True):
                        neighbors = set()
                        for j in range(len(self.motes)):
                            if j != candidate:
                                if self.motes[candidate].getRSSI(j) > self.motes[candidate].radioSensitivity:
                                    neighbors.add(j) 
                        if dagRoot in neighbors:
                            findDagroot = True
                            break
                        else:
                            paths = paths | neighbors
                            checkedNodes.add(candidate)
                            nextCandidates = paths - checkedNodes
                            if len(nextCandidates) > 0: 
                                candidate = nextCandidates.pop()
                            else:
                                break
                    if(findDagroot == False):
                        # No path to DAG root. Need to reset locations and RSSI of all the motes
                        print "reset location and RSSI"
                        for j in range(len(self.motes)):
                            self.motes[j].setLocation()
                        self.computeRSSI()
                        break
                         
            # All the nodes have paths to DAG root
            if(findDagroot == True):
                break     
            
        for id in range(len(self.motes)):
            #link to a neighbor with higher RSSI than threshold             
            neighbors = []
            for j in range(len(self.motes)):
                if j != id:
                    if self.motes[id].getRSSI(j) > self.motes[id].radioSensitivity:
                        neighbors.append(j) 

            for nei in neighbors:
                # DAG root does not generate data
                if self.motes[id].dagRoot == False:
                    self.motes[id].setDataEngine(self.motes[nei], s().traffic,) 
                self.motes[id].setPDR(self.motes[nei], self.computePDR(id, nei))

    
    def computePDR(self,node,neighbor): 
        ''' computes pdr to neighbor according to RSSI'''

        rssi = self.motes[node].getRSSI(neighbor)

        if rssi < -85 and rssi > self.motes[neighbor].radioSensitivity:
            pdr=(rssi-self.motes[neighbor].radioSensitivity)*6.25
        elif rssi <= self.motes[neighbor].radioSensitivity:
            pdr=0.0
        elif rssi > -85:
            pdr=100.0
            
        print "node {0}, neighbor {1}, rssi {2}, pdr {3}".format(node, neighbor, rssi, pdr)

        log.debug("node {0}, neighbor {1}, rssi {2}, pdr {3}".format(node, neighbor, rssi, pdr)) 

        return pdr 

    def computeRSSI(self): 
        ''' computes RSSI between any two nodes (not only neighbor) according to Pister hack model'''

        for node in range(len(self.motes)):
            for neighbor in range(node+1, len(self.motes)):

                #x and y values are between [0,1) in km
                distance = math.sqrt((self.motes[node].x - self.motes[neighbor].x)**2 + (self.motes[node].y - self.motes[neighbor].y)**2)
                     
                # Convert km to m
                distance = distance*1000.0
        
                # sqrt and inverse of the free space path loss
                fspl=(self.SPEED_OF_LIGHT/(4*math.pi*distance*self.TWO_DOT_FOUR_GHZ)) 
                #simple friis equation in Pr=Pt+Gt+Gr+20log10(c/4piR)   
                pr=self.motes[node].tPower + self.motes[node].antennaGain + self.motes[neighbor].antennaGain +(20*math.log10(fspl))
                #according to the receiver power (RSSI) we can apply the Pister hack model.
                mu=pr-self.PISTER_HACK_LOWER_SHIFT/2 #chosing the "mean" value
        
                #the receiver will receive the packet with an rssi distributed in a gaussian between friis and friis -40
                #rssi=random.gauss(mu,self.PISTER_HACK_LOWER_SHIFT/2)

                #the receiver will receive the packet with an rssi uniformly distributed between friis and friis -40
                rssi = mu + random.uniform(-self.PISTER_HACK_LOWER_SHIFT/2, self.PISTER_HACK_LOWER_SHIFT/2)
                
                self.motes[node].setRSSI(neighbor, rssi)
                self.motes[neighbor].setRSSI(node, rssi)
                