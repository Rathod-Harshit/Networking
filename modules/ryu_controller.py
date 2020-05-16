#!/usr/bin/python
#
#   Assignment : CPSC-558 Project
#   Author(s)    : Harshit Singh Rathod  
#   Program    : This is an RYU SDN controller program. It consists path cost calculation routines and DFS algorithm for path finding. 
#                It also has several handlers for managing switches.
#                Reference: Handlers > Examples in ryu/ryu/app/
#                           DFS      > CLRS book
#                           Bucket   > OSPF
#                To run: start ryu.sh

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.controller import mac_to_port
from ryu.lib.packet import packet
from ryu.lib.packet import arp
from ryu.lib.packet import ethernet, ether_types, ipv4, ipv6
from ryu.lib import mac, ip
from ryu.topology.api import get_switch, get_link
from ryu.app.wsgi import ControllerBase
from ryu.topology import event
from collections import defaultdict
from operator import itemgetter
import time
import random


# defaults
ref_bw = 10000000
default_bw = 10000000
max_allowed_path = 2



class Ryu_controller(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(Ryu_controller, self).__init__(*args, **kwargs)
        self.topology_api_app = self
        self.switches = []
        self.hosts = {}
        self.neighbour = defaultdict(dict)
        self.bandwidths = defaultdict(lambda: defaultdict(lambda: default_bw))
        self.ofids = []
        self.path_ofids = {}
        self.datapath_list = {}
        self.arp_table = {}
        self.mac_to_port = {}

# Routine for DFS

    def dfs(self, source, dest):
        self.logger.info('Using DFS to find paths')
        if source == dest:
            return [[source]]
            
        route_paths = []
        stack = [(source, [source])]
        while stack:
            (node, path) = stack.pop()

            for next in set(self.neighbour[node].keys()) - set(path):
                if next is dest:
                    route_paths.append(path + [next])
                else:
                    stack.append((next, path + [next]))
        self.logger.info('Available path(s) between {0} & {1} : {2}.'.format(source, dest, route_paths))
        return route_paths

# Cost calculation between links, cost calculation: cost= 100000000/bandwith in bps

    def cal_cost_link(self, from_s, to_s):

        forward_e = self.neighbour[from_s][to_s]

        rev_e = self.neighbour[to_s][from_s]
        min_bw = min(self.bandwidths[from_s][forward_e], self.bandwidths[to_s][rev_e])
        cost_link = ref_bw/min_bw
        return cost_link

# This routine calls the link cost calculation routine to get the cost of whole path

    def cal_cost_path(self, path):
        cost_path = 0
        for i in range(len(path) -1):
            cost_path += self.cal_cost_link(path[i], path[i+1])
        return cost_path

# Currently for simplicity we are allowing only two paths between two host.
# It can be changed by changing variable at max_allowed_path present at the top.

    def max_optimal_paths(self, source, dest):
        opt_paths = self.dfs(source, dest)
        opt_paths_no = min(len(opt_paths),max_allowed_path)
        return sorted(opt_paths, key=lambda x: self.cal_cost_path(x))[0:(opt_paths_no)]



    def link(self, paths, source_port, dest_port):
        port_paths = []
        for path in paths:
            p0 = {}
            port_in = source_port
	    for s1, s2 in zip(path[:-1], path[1:]):
		port_out = self.neighbour[s1][s2]
		p0[s1] = (port_in, port_out)
		port_in = self.neighbour[s2][s1]
	    p0[path[-1]] = (port_in, dest_port)
	    port_paths.append(p0)
	return port_paths

# Common openflow subroutine to generate random ids.

    def generate_openflow_gid(self):
        n = random.randint(0, 2**32)
        while n in self.ofids:
            n = random.randint(0, 2**32)
        return n

# This routine is called to establish forward paths

    def est_flinks(self, source, dest, sip, dip, source_port, dest_port):
        t0 = time.time()
        links = self.max_optimal_paths(source, dest)
	arr_link = []
	for link in links:
	    arr_link.append(self.cal_cost_path(link))
            self.logger.info('Path {0} has cost {1}.'.format(link, arr_link[len(arr_link) - 1]))
	sum_link = sum(arr_link) * 1.0
        paths_with_ports = self.link(links, source_port, dest_port)
	link_s = set().union(*links)

	for node in link_s:
            dp = self.datapath_list[node]
            ofp = dp.ofproto
            ofp_parser = dp.ofproto_parser
            ports = defaultdict(list)
            actions = []
            i = 0
	    for path in paths_with_ports:
                if node in path:
                    port_in = path[node][0]
                    port_out = path[node][1]
                    if (port_out, arr_link[i]) not in ports[port_in]:
                        ports[port_in].append((port_out, arr_link[i]))
                i += 1

            for port_in in ports:

                match_ip = ofp_parser.OFPMatch(
                    eth_type=0x0800, 
                    ipv4_src=sip, 
                    ipv4_dst=dip
                )
                match_arp = ofp_parser.OFPMatch(
                    eth_type=0x0806, 
                    arp_spa=sip, 
                    arp_tpa=dip
                )

                out_ports = ports[port_in]

                if len(out_ports) > 1:
                    group_id = None
                    group_new = False

                    if (node, source, dest) not in self.path_ofids:
                        group_new = True
                        self.path_ofids[
                            node, source, dest] = self.generate_openflow_gid()
                    group_id = self.path_ofids[node, source, dest]

#****************** Bucket calculation
#****************** As in our case switch 7 has two ports: port 3 has a cost '3' and port 2 has a cost '4'
#****************** For bucket weight calculation for port 3 we have:
#****************** round(1-(3/3+4))*10 = 6
#****************** The base (3+4) here is from sum of all the cost.

                    buckets = []
                    for port, weight in out_ports:
                        bucket_weight = int(round((1 - weight/sum_link) * 10))
			self.logger.info('Bucket weight for port {0} is {1}.'.format(port, bucket_weight))
                        bucket_action = [ofp_parser.OFPActionOutput(port)]
                        buckets.append(
                            ofp_parser.OFPBucket(
                                weight=bucket_weight,
                                watch_port=port,
                                watch_group=ofp.OFPG_ANY,
                                actions=bucket_action
                            )
                        )


                    if group_new:
                        req = ofp_parser.OFPGroupMod(
                            dp, ofp.OFPGC_ADD, ofp.OFPGT_SELECT, group_id,
                            buckets
                        )
                        dp.send_msg(req)
                    else:
                        req = ofp_parser.OFPGroupMod(
                            dp, ofp.OFPGC_MODIFY, ofp.OFPGT_SELECT,
                            group_id, buckets)
                        dp.send_msg(req)

                    actions = [ofp_parser.OFPActionGroup(group_id)]

                    self.add_flow(dp, 32768, match_ip, actions)
                    self.add_flow(dp, 1, match_arp, actions)

                elif len(out_ports) == 1:
                    actions = [ofp_parser.OFPActionOutput(out_ports[0][0])]

                    self.add_flow(dp, 32768, match_ip, actions)
                    self.add_flow(dp, 1, match_arp, actions)
        self.logger.info('Time taken to install path {0}.'.format(time.time() - t0))
        return paths_with_ports[0][source][1]

# This calls the est_flinks routine in reversed order i.e. source is swapped with destination (for DFS)

    def est_blinks(self,source, dest, sip, dip, source_port, dest_port):
        #self.logger.info('bli')
	return self.est_flinks(dest, source, dip, sip, dest_port, source_port)


    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)


##################################################################################
#     ---------------Useful Handlers taken from RYU examples--------------       #
##################################################################################

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def _switch_features_handler(self, ev):
        #self.logger.info('Handler called: Switch features')

        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

#

    @set_ev_cls(ofp_event.EventOFPPortDescStatsReply, MAIN_DISPATCHER)
    def port_desc_stats_reply_handler(self, ev):
        switch = ev.msg.datapath
        for p in ev.msg.body:
            self.bandwidths[switch.id][p.port_no] = p.curr_speed

#

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        arp_pkt = pkt.get_protocol(arp.arp)

        # avoid broadcast from LLDP
        if eth.ethertype == 35020:
            return

        if pkt.get_protocol(ipv6.ipv6):  # Drop the IPV6 Packets.
            match = parser.OFPMatch(eth_type=eth.ethertype)
            actions = []
            self.add_flow(datapath, 1, match, actions)
            return None

        dest = eth.dst
        source = eth.src
        dpid = datapath.id


        if source not in self.hosts:
            self.hosts[source] = (dpid, in_port)
        port_out = ofproto.OFPP_FLOOD

        if arp_pkt:
            sip = arp_pkt.src_ip
            dip = arp_pkt.dst_ip
            if arp_pkt.opcode == arp.ARP_REPLY:
                self.arp_table[sip] = source
                h1 = self.hosts[source]
                h2 = self.hosts[dest]
                port_out = self.est_flinks(h1[0], h2[0], sip, dip, h1[1], h2[1])
		self.est_blinks(h1[0], h2[0], sip, dip, h1[1], h2[1])
            elif arp_pkt.opcode == arp.ARP_REQUEST:
                if dip in self.arp_table:
                    self.arp_table[sip] = source
                    dst_mac = self.arp_table[dip]
                    h1 = self.hosts[source]
                    h2 = self.hosts[dst_mac]
                    port_out = self.est_flinks(h1[0], h2[0], sip, dip, h1[1], h2[1])
		    self.est_blinks(h1[0], h2[0], sip, dip, h1[1], h2[1])


        actions = [parser.OFPActionOutput(port_out)]

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath, buffer_id=msg.buffer_id, in_port=in_port,
            actions=actions, data=data)
        datapath.send_msg(out)

#

    @set_ev_cls(event.EventSwitchEnter)
    def switch_enter_handler(self, ev):
        switch = ev.switch.dp
        ofp_parser = switch.ofproto_parser

        if switch.id not in self.switches:
            self.switches.append(switch.id)
            self.datapath_list[switch.id] = switch

            # Request port/link descriptions, useful for obtaining bandwidth
            req = ofp_parser.OFPPortDescStatsRequest(switch)
            switch.send_msg(req)

#

    @set_ev_cls(event.EventSwitchLeave, MAIN_DISPATCHER)
    def switch_leave_handler(self, ev):
        self.logger.info('Switch left with dpid {0}.'.format(ev.switch.dp.id))
        switch = ev.switch.dp.id
        if switch in self.switches:
            self.switches.remove(switch)
            del self.datapath_list[switch]
            del self.neighbour[switch]


#

    @set_ev_cls(event.EventLinkAdd, MAIN_DISPATCHER)
    def link_add_handler(self, ev):
        s1 = ev.link.src
        s2 = ev.link.dst
        self.neighbour[s1.dpid][s2.dpid] = s1.port_no
        self.neighbour[s2.dpid][s1.dpid] = s2.port_no

#

    @set_ev_cls(event.EventLinkDelete, MAIN_DISPATCHER)
    def link_delete_handler(self, ev):
        s1 = ev.link.src
        s2 = ev.link.dst
        # Exception handling if switch already deleted
        try:
            del self.neighbour[s1.dpid][s2.dpid]
            del self.neighbour[s2.dpid][s1.dpid]
        except KeyError:
            pass

