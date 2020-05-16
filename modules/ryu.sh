if [[ $1 = "c" ]]; then 
    ovs-ofctl -O OpenFlow13 del-flows s1
    ovs-ofctl -O OpenFlow13 del-flows s2
    ovs-ofctl -O OpenFlow13 del-flows s3
    ovs-ofctl -O OpenFlow13 del-flows s4
    ovs-ofctl -O OpenFlow13 del-flows s5
    ovs-ofctl -O OpenFlow13 del-flows s6
    ovs-ofctl -O OpenFlow13 del-flows s7
fi
ryu-manager --observe-links --enable-debugger gui_topology.py ryu_controller.py
