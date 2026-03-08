# Changelog

## v0.1.0 - Initial Release

- Real-time AIS position tracking via AISStream.io
- 11 sensor entities (latitude, longitude, speed, course, last report, distance from home, distance to North Pole, bearing from home, days since departure, solar elevation, mission phase)
- 4 binary sensor entities (Arctic Circle, polar day, polar night, stationary)
- Optional Panomax webcam integration
- Home Assistant events for expedition milestones
- Config flow with options for poll interval, home coordinates, departure date, webcam toggle
- Haversine distance and bearing calculations
- Polar day/night detection using solar elevation
- HACS compatible
