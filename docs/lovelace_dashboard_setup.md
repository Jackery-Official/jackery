# Jackery Lovelace Visualization Dashboard Installation Guide

This guide helps you upgrade your Jackery device view from the default "Entity Grid" to a partitioned energy dashboard (Energy Flow Diagram + Key Metrics + Control Section).

## 1. Install HACS Frontend Cards

In Home Assistant:

1. Open **HACS** → **Frontend**
2. Search for and install:
   - **[Mushroom Cards](https://github.com/piitaya/lovelace-mushroom)** — Top chips, entity cards
   - **[Power Flow Card Plus](https://github.com/flixlix/power-flow-card-plus)** — Energy flow diagram
3. (Optional) **mini-graph-card** — Historical mini graphs; **card-mod** — Style fine-tuning
4. After installation, **clear your browser cache** or restart HA to ensure the cards are loaded.

> **Sub-device Section Note**: The "Sub-devices & Accessories" section at the bottom of the dashboard uses the native HA `entities` card and **does not** require `auto-entities`. If you use `custom:auto-entities` without having the HACS plugin installed, it will display a red **"Configuration Error"**.

## 2. Verify Entity IDs

1. Go to **Developer Tools** → **States**
2. Search for `jackery_` + your device SN (lowercase)
3. Refer to [entity_id_reference.md](entity_id_reference.md) to confirm IDs
4. If your SN is not `HS2C12600262HH4`, perform a global search and replace for `hs2c12600262hh4` in the configuration file.

## 3. Create Dashboard

1. **Overview** → Top right ⋮ → **Add Dashboard**
2. Name: `Jackery Energy` (Customizable)
3. Enter the new dashboard → **Edit** → Top right ⋮ → **Raw Configuration Editor**
4. Paste the entire contents of [lovelace_dashboard_jackery.yaml](lovelace_dashboard_jackery.yaml)
5. Save and exit edit mode.

## 4. Using Only the Energy Flow Card

If you only need the energy flow diagram, you can add a single card separately. Configuration can be found in the project root directory [energy_flow_card_config.yaml](../energy_flow_card_config.yaml). Remember to replace the SN in the entity IDs with your actual value before use.

## 5. Multiple Hosts

Each DIY3 host has a unique SN prefix. You can:

- Duplicate a section for each device and replace the corresponding entity_id; or
- Create a separate dashboard for each host.

## 6. Troubleshooting

| Symptom | Resolution |
|------|------|
| Card displays "Custom element doesn't exist" | Confirm HACS cards are installed and refresh the page. |
| Entities show "unavailable" | Check MQTT and Jackery integration connectivity. |
| A specific path in the energy flow diagram has no data | Confirm the corresponding sensor has a value in Developer Tools. |
| Control buttons are ineffective | Verify if the entity_id for switch/select/number/button follows the `main_*` format. |
| Sub-device section displays "Configuration Error" | Usually due to missing `auto-entities`; please use the latest `lovelace_dashboard_jackery.yaml` (which has been switched to native entities). |
| New CT/Plug added but not appearing on the dashboard | Copy the new entity_id from Developer Tools and append it to the `entities` list in the "Sub-devices" section of the dashboard. |
