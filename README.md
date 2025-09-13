# ⚡ Solarcore Energy – Rockcore Solar Monitoring for Home Assistant

Monitor your Rockcore solar inverter production in real time with this sleek, cloud-connected Home Assistant integration.  
Easily track your solar power, voltage, temperature and total energy generation — fully compatible with the **Home Assistant Energy Dashboard**.


## 🔧 Features

- 🧠 Uses official Rockcore Cloud API (token-based)
- 📊 Supports Home Assistant Energy Dashboard (kWh + total_increasing sensors)
- 🌞 Live power tracking (`power1`, `power2`, total)
- 🔋 Energy statistics (`today_energy`, `total_energy`)
- 🌡️ Voltage, current, grid frequency, temperature

## ✅ Tested with

- 🟢 **MI2S-800D** 
- MI600
- MI1000
- MI2S-1200D
- RCMI 1500
- Hybrid Rockcore units

## 🚀 Installation (via HACS)

1. Go to HACS > Integrations > Custom Repositories
2. Add repository: `https://github.com/ErwinSt/home-assistant-solarcore-energy`
3. Category: Integration
4. Install and restart Home Assistant
5. Go to Settings > Integrations > Add Integration > **Solarcore Energy**

## 🔐 Required

- Rockcore Cloud account
- Your login (email + password)
- Internet access (for cloud API)

## 📣 Station Event Service

This integration exposes the `station_event` service. It can be used to
dispatch custom events about a station.

```yaml
service: solarcore_energy.station_event
data:
  station_id: "12345"
  type: "error"
```

### Example Automation: Mobile Notification

```yaml
automation:
  - alias: Solarcore alert
    trigger:
      platform: event
      event_type: solarcore_energy_station_event
    action:
      - service: notify.mobile_app_my_phone
        data:
          message: >-
            Station {{ trigger.event.data.station_id }} reported {{ trigger.event.data.type }}
```

## 💡 Ideas & Next Steps

- Add local IP support (reverse-engineered API)
- Display historical graphs
- Multi-station support
- Push alerts on inverter errors

---

Made with ☀️ by [@ErwinSt](https://github.com/ErwinSt) — PRs welcome!
