# Centralized E/E Architecture Overview

Version: 1.0
Entirely synthetic engineering test data; not production OEM specifications.
Device and link IDs align with data/examples/centralized_architecture.json.

## Central compute and gateway

SYS-REQ-101:
The Central Gateway (gateway) shall connect the central Ethernet Switch (switch-core)
through link-gateway and the Body Controller (body) through CAN link-body-can at 1 Mbps.
Physical connectivity shall not imply CAN-to-Ethernet protocol translation.

SYS-REQ-102:
The ADAS Domain Controller (adas) shall consume camera and radar data through
switch-core. The Infotainment Controller (infotainment) shall exchange declared
vehicle state and diagnostic traffic through switch-core and gateway.

## Sensors and topology

NET-REQ-042:
The Front Camera ECU (front-camera) and Radar ECU (radar) shall each connect
to switch-core through independent 100 Mbps Ethernet links. The front-camera
to adas physical path shall be front-camera, switch-core, adas.

REQ-CONN-001:
The camera and ADAS shall have a physical path using link-camera and link-adas.
This identifier links to the Phase 1 connectivity requirement without changing it.

REQ-CONN-002:
The Body Controller (body) shall have a physical connection to Central Gateway
(gateway) through link-body-can. This identifier links to the Phase 1 requirement.

## Review boundaries

REQ-ISO-001:
Camera and infotainment traffic shall have a reviewed isolation policy. The
Phase 1 validator reports isolation as NOT_EVALUATED; no switch policy proof is supplied.

REQ-TEXT-001:
Camera delivery latency shall be reviewed by an engineer with the proposed TSN
constraints in tsn.md. The free-text Phase 1 requirement remains NOT_EVALUATED.
