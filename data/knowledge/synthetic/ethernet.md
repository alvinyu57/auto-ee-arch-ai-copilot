# Automotive Ethernet Architecture Requirements

Version: 1.0
Synthetic engineering test data only. These are not production OEM specifications.
Component identifiers match the Phase 1 centralized example. Requirements describe
design intent and do not establish that an implementation has been verified.

## Physical Ethernet interfaces

REQ-ETH-001:
The Central Gateway (gateway) shall connect its eth0 interface to Ethernet Switch
switch-core port p1 using 1000BASE-T1 with a nominal link bandwidth of 1000 Mbps.

REQ-ETH-002:
The communication path between the Central Gateway (gateway) and ADAS Domain
Controller (adas) shall use switch-core and two links, link-gateway and link-adas,
each supporting a nominal bandwidth of at least 1000 Mbps using 1000BASE-T1.
This is a switched path, not a direct gateway-to-ADAS cable.

REQ-ETH-003:
The Front Camera ECU (front-camera) shall connect eth0 to switch-core port p4
using 100BASE-T1 at a nominal speed of 100 Mbps on link-camera.

REQ-ETH-004:
The Radar ECU (radar) shall connect eth0 to switch-core port p5 using
100BASE-T1 at a nominal speed of 100 Mbps on link-radar.

REQ-ETH-005:
The Infotainment Controller (infotainment) shall connect eth0 to switch-core
port p3 using 1000BASE-T1 at 1000 Mbps on link-infotainment.

## Switching and VLAN segmentation

REQ-ETH-006:
The Ethernet Switch (switch-core) shall configure ports p1, p2, and p3 for
1000 Mbps, and ports p4 and p5 for 100 Mbps. Switch configuration shall be
reviewed separately from the physical adjacency model.

REQ-ETH-007:
VLAN 20 shall identify sensor communication from front-camera and radar to adas.
Gateway port p1 shall declare VLAN memberships 10, 20, and 30; ADAS port p2
shall declare memberships 20 and 30. VLAN membership alone does not prove forwarding.

REQ-ETH-008:
VLAN 30 shall identify infotainment communication. The camera port p4 shall
declare only VLAN 20, and the infotainment port p3 shall declare only VLAN 30.
VLAN separation between camera and infotainment requires a reviewed switch policy;
it is not verified by the Phase 1 topology model.

REQ-BW-001:
All declared unicast service traffic shall fit the nominal link budgets listed
in the Phase 1 architecture. Explicit traffic routes and demands are required;
port speed alone shall not be used to infer available application throughput.
