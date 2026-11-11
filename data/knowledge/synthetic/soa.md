# SOA Communication Requirements

Version: 1.0
Synthetic engineering test data only; not production OEM specifications.
These requirements describe the same illustrative system as ethernet.md.

## Providers, consumers, and interfaces

REQ-SOA-001:
The Front Camera ECU (front-camera) shall provide the SOME/IP camera stream
service svc-camera to the ADAS Domain Controller (adas) as its consumer.
The declared provider-to-consumer unicast demand shall be 60 Mbps via
link-camera and link-adas. This demand does not include unspecified reverse traffic.

REQ-SOA-002:
The Radar ECU (radar) shall provide the DDS radar object service svc-radar
to adas as its consumer. Its declared demand shall be 20 Mbps via link-radar
and link-adas.

REQ-SOA-003:
The ADAS Domain Controller (adas) shall provide driving status service svc-driving-status
using SOME/IP to infotainment, with a declared demand of 8 Mbps to that consumer.

REQ-SOA-004:
The Infotainment Controller (infotainment) shall provide diagnostics service
svc-diagnostics using REST to gateway, with a declared demand of 0.2 Mbps.

## Service discovery and availability

REQ-SOA-015:
SOME/IP-SD service discovery shall advertise svc-camera on VLAN 20 and svc-driving-status
on VLAN 30.
Consumers shall resolve a service provider endpoint before subscribing. Discovery
messages are additional traffic and are not quantified in the Phase 1 budget example.

REQ-SOA-016:
The svc-camera SOME/IP interface shall use synthetic service identifier 0x1234.
Provider front-camera and consumer adas shall agree on the service identifier and
interface version before communication is enabled.

REQ-SOA-017:
When svc-camera becomes unavailable, adas shall detect expiration of the SOME/IP-SD
service availability announcement within 500 ms and record degraded camera input.
This is a requirement, not a measured availability or verified timing result.

REQ-SOA-018:
The ADAS controller shall advertise svc-driving-status using SOME/IP-SD on the
reviewed VLAN 30. Provider/consumer declarations do not prove service reachability.
