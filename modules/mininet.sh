sudo mn --custom topo.py --topo create --mac --link=tc  --switch=ovsk,datapath=kernel --controller=remote
sudo mn -c
exit 0
