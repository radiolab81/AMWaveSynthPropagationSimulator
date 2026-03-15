### AMWaveSynth-addon for dynamic control of signal amplitudes based on annual and daily propagation conditions.


Based on transmitter data such as location and transmission power, which can be obtained, for example, from older WRTH, 
receiver positions can be defined using a map. At these receiver locations, the conditions of ground and sky waves can be simulated 
according to simplified models ITU-R P.368-10 / ITU-R P.1147-2, varying by year and time of day. 
The resulting data can be used in time-lapse or real-time to control the artificial carriers of the AMWaveSynth modulator, providing an 
even more realistic representation of the transmitted signal at specific times of day.

![UI1](https://github.com/radiolab81/AMWaveSynthPropagationSimulator/blob/main/www/map_view.jpg "WRTH 1975 scenario")
WRTH 1975 scenario on LW and MW

The radiosignals transmitted by the AMWaveSynth creates the impression of an active twilight zone and a day and night scene of the synthetically 
created radio wave bands.


![UI2](https://github.com/radiolab81/AMWaveSynthPropagationSimulator/blob/main/www/simulator_control_view.jpg "WRTH 1975 scenario")


The current status is displayed directly in the simulation window. Additionally, a threshold value for the radio's reception sensitivity can be specified to further filter 
the actually receivable stations.

![UI3](https://github.com/radiolab81/AMWaveSynthPropagationSimulator/blob/main/www/mw_dusk_01.jpg "WRTH 1975 scenario")
Simulation, afternoon of October 15th, 17:26


![UI3](https://github.com/radiolab81/AMWaveSynthPropagationSimulator/blob/main/www/mw_dusk_02.jpg "WRTH 1975 scenario")
Simulation, afternoon of October 15th, 18:52 , foreign radio stations can now also be received via skywave on radios powered by the AMWaveSynth.

Custom transmitter definitions can be stored as a CSV file in the tx_sites folder. Each line represents a location, consisting of the transmitter's location, country code, frequency in kHz, 
transmission power in kW, and transmitter name. 
Upon startup, the program searches this folder for new transmitter definitions and resolves the location data to GPS coordinates using ArcGIS. 
These coordinates are automatically cached in an SQL database for immediate availability upon the next program start. Transmitter and receiver locations are displayed using a TkinterMapView.

### Installation (can be done by uv paket manager)
- checkout AMWaveSynthPropagationSimulator
- get uv
  
`sudo curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" INSTALLER_NO_MODIFY_PATH=1 sudo -E sh`

- create virtual python env.
  
`cd AMWaveSynthPropagationSimulator`

`uv venv --python 3.13`

`source .venv/bin/activate`

`uv init`

- install all required libs
  
`uv add -r requirements.txt`

`source .venv/bin/activate`

- start application
  
`python3.13 AMWaveSyntPropagationSIM.py`
