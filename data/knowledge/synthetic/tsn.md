# TSN Architecture Guidelines

Version: 1.0
Synthetic conceptual engineering requirements only; not production OEM specifications.
These are proposed timing constraints for the same centralized system. Phase 1
does not evaluate TSN scheduling, synchronization, or worst-case latency.

## Time synchronization

REQ-TSN-001:
The gateway, switch-core, adas, front-camera, and radar timing domains shall
support IEEE 802.1AS time synchronization before time-sensitive traffic is enabled.

REQ-TSN-002:
For the synthetic TSN operating mode, the synchronization offset between
front-camera and adas shall remain within 1 microsecond of the selected time reference.
Compliance requires measurement and is not established by document retrieval.

## Traffic scheduling

REQ-TSN-008:
The Ethernet Switch (switch-core) shall support IEEE 802.1Qbv time-aware traffic
scheduling for camera traffic on the egress port p2 toward adas. Gate schedules
shall be reviewed against the selected IEEE 802.1AS time reference.

REQ-TSN-009:
The conceptual camera traffic schedule shall use a 1 ms cycle with a reviewed
reserved transmission window. A concrete gate control list is not supplied in
these guidelines and shall not be invented from nominal bandwidth values.

## Latency and degraded operation

REQ-TSN-010:
The proposed maximum end-to-end latency for svc-camera from front-camera to adas
shall be 5 ms in the synthetic TSN operating mode. This is a design constraint,
not a computed worst-case latency result or evidence of compliance.

REQ-TSN-011:
If time synchronization is lost, adas shall record degraded timing status and
the system shall suspend scheduled camera transmission until synchronization recovers.
