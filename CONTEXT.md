# Jackery HA Integration Domain Model

## Glossary

### Physical Unit (物理单元)
Refers to a single Jackery inverter/battery unit (e.g., SolarVault 2000 Plus). Each unit is identified by its unique Serial Number (SN). 
- **Unit Sensors**: Report data physically local to that SN, such as its own connected battery packs, its own solar MPPT input, and its own temperature.

### System / EMS (系统/能量管理系统)
Refers to the logical entity formed when one or more Physical Units are operated in Parallel (并机) or Grid-tied mode. The **Master** unit acts as the EMS gateway for the entire system.
- **System Sensors**: Report aggregated or collaborative data for the entire set of units, such as system-wide average SOC, total system capacity, and external grid meter readings.

### Master (主机)
The primary physical unit in a parallel system that communicates with the cloud/HA as the system coordinator. It reports both its own **Physical Unit** data and the **System** data.

### Slave (从机)
A secondary physical unit in a parallel system that reports only its own **Physical Unit** data.

## Data Mapping Rules

1. **Physical Isolation**: Sensors representing the physical properties of a specific SN must only be updated by unit-level reports (Type 2, 25, 23).
2. **System Aggregation**: Sensors representing the logic or total state of a parallel system must only be updated by system-level reports (Type 106, 107).
3. **Master Role**: When a unit is a Master, its HA device entry will contain both Unit Sensors and System Sensors. When it is a Slave, it will only contain Unit Sensors.
