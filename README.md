# ShevLogger for Home Assistant

This directory contains the native local Home Assistant integration. Copy
`custom_components/shevlogger` to Home Assistant's
`/config/custom_components/shevlogger`, restart Home Assistant and add
**ShevLogger** from **Settings → Devices & services**.

Home Assistant normally discovers the logger automatically. If mDNS traffic is
blocked between networks, choose the integration manually and enter the
logger's IP address or `shevlogger-<id>.local` hostname. Authentication uses the
same activation key that protects the logger's local API.

See [the full setup and API documentation](../docs/home-assistant.md).

