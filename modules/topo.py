#!/usr/bin/python
#
#   Assignment : CPSC-558 Project
#   Authors    : Harshit Singh Rathod (rathod10892@csu.fullerton.edu)
#                Rahul Chauhan        (rahulchauhan@csu.fullerton.edu)
#                Nathan Elder   
#                Alexis Apilado    
#                Ly Ngo   
#   Program    : This is a python program to create mininet topologies. 
#                Adds two hosts, seven switches and links between them
#                Reference: http://mininet.org/walkthrough/
#                To run: start mininet.sh
#                

from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch, Host
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mininet.topo import Topo


class build_topo(Topo):

    def __init__( self ):
        "Creating network."
        Topo.__init__( self )

        #info( '*** Add switches\n')
        s1 = self.addSwitch('s1', dpid='0000000000000001', protocols='OpenFlow13', cls=OVSKernelSwitch)
        s2 = self.addSwitch('s2', dpid='0000000000000002', protocols='OpenFlow13', cls=OVSKernelSwitch)
        s3 = self.addSwitch('s3', dpid='0000000000000003', protocols='OpenFlow13', cls=OVSKernelSwitch)
        s4 = self.addSwitch('s4', dpid='0000000000000004', protocols='OpenFlow13', cls=OVSKernelSwitch)
        s5 = self.addSwitch('s5', dpid='0000000000000005', protocols='OpenFlow13', cls=OVSKernelSwitch)
        s6 = self.addSwitch('s6', dpid='0000000000000006', protocols='OpenFlow13', cls=OVSKernelSwitch)
        s7 = self.addSwitch('s7', dpid='0000000000000007', protocols='OpenFlow13', cls=OVSKernelSwitch)

        #info( '*** Add hosts\n')
        h1 = self.addHost('h1', cls=Host, ip='10.0.0.1')
        h2 = self.addHost('h2', cls=Host, ip='10.0.0.2')
        #h3 = self.addHost('h3', cls=Host, ip='10.0.0.3')

        #info( '*** Add links\n')
        self.addLink(h1, s1)
        self.addLink(h2, s7)
        #self.addLink(h3, s5)

        self.addLink(s1, s3, delay='100ms', bw=100, loss=0)
        self.addLink(s3, s5, delay='100ms', bw=100, loss=0)
        self.addLink(s5, s6, delay='100ms', bw=100, loss=0)
        self.addLink(s6, s7, delay='100ms', bw=100, loss=0)

        self.addLink(s1, s2, delay='100ms', bw=100, loss=0)
        self.addLink(s2, s4, delay='100ms', bw=100, loss=0)
        self.addLink(s4, s7, delay='100ms', bw=100, loss=0)

topos = {'create': (lambda: build_topo())}
