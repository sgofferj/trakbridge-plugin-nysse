# Nysse Plugin for TrakBridge

## Description
This plugin integrates real-time vehicle data from Nysse, the regional public transport of Tampere (Finland), into TrakBridge. It polls the ITS Factory vehicle activity API and generates CoT (Cursor-on-Target) events for TAK.

## Configuration

| Field | Description | Default |
|-------|-------------|---------|
| Line Filter | Comma-separated list of bus line numbers to show. Wildcards supported (e.g., `6*`). Leave empty for all lines. | (empty: all) |

## Features
- Real-time bus positions from the Nysse/ITS Factory API.
- Wildcard line filtering (e.g., `60,64,3A` or `6*`).
- Next stop and destination information with stop name/municipality lookup and caching.
- CoT type `a-f-G-E-V-C-M` (friendly ground vehicle), callsign `NYSSE <line>`.

## Example
To follow bus lines 60 and 64, set the line filter to:
```
60,64
```

## Copyright and License
Copyright Stefan Gofferje
Licensed under the Gnu General Public License Version 3 or higher.

## Changelog

### 0.1.0
- Initial release.
- Vehicle activity polling with wildcard line filtering.
- Stop metadata caching.
