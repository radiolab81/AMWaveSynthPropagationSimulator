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

Custom transmitter definitions can be stored as a CSV file in the tx_sites folder. Each line represents a transmitter site, consisting of the transmitters location, country code, frequency in kHz, transmission power in kW, and call/name of radiostation. 
Upon startup, the program searches this folder for new transmitter definitions and resolves the location data to GPS coordinates using ArcGIS. 
These coordinates are automatically cached in an SQL database for immediate availability upon the next program start. Transmitter and receiver locations are displayed using a TkinterMapView.

### 🚀 SFERICS-SIMULATION

Since the AMWaveSynth also allows the firing of sferics at RF level, it is possible to define a thunderstorm area/storm cell on the map with heading, ground speed and intensity. The intensity of the simulated disturbances is influenced by the distance of the storm cell from the receiver's location. Since the storm moves across the map during its lifetime, this affects the listening experience on the radio.

![SFERICS](https://github.com/radiolab81/AMWaveSynthPropagationSimulator/blob/main/www/sferics.jpg "sferics")
We plan to further expand these features in later versions if needed and desired.

### 🚀 Advanced Radio Direction Finding (RDF) & Navigation Subsystem

The simulator has been upgraded from an omnidirectional propagation model to a fully dynamic, physics-based **Radio Direction Finding (RDF) and Navigation Simulation Environment**. By integrating standard antenna pattern files with real-time geographical azimuth calculations, the system now replicates the exact behavior of vintage and modern radio navigation equipment—projecting the calculated RF environment straight onto your physical hardware receiver.

#### 📡 Key New Features

* **Real-Time Antenna Pattern Convolution (`.msi` / `.ant` Support)**
  * Users can now load standardized antenna files (such as a horizontal Ferrite Rod Antenna with its characteristic figure-of-eight loop pattern) directly into the UI.
  * The engine calculates the precise geographical bearing (azimuth) from the freely movable receiver to every transmitter marker on the map in real time.
  * An intuitive orientation slider allows users to rotate the virtual antenna through 0°–359°, calculating dynamic angle-dependent attenuation on the fly.

* **Live Map Vector Overlays**
  * When an antenna profile is active, a highly responsive vector polygon represents the true-to-scale reception pattern directly centered on the blue receiver icon.
  * The visual pattern dynamically rotates with the slider and automatically updates its coordinate projection when dragging the receiver to a new location.

![DF1](https://github.com/radiolab81/AMWaveSynthPropagationSimulator/blob/main/www/DF1.jpg "Direction Finder NDB")

![DF2](https://github.com/radiolab81/AMWaveSynthPropagationSimulator/blob/main/www/DF2.jpg "Direction Finder NDB")

#### 🗺️ Advanced Practical Application Scenarios

With this sub-system, the application becomes a training bench for real-world analog navigation and signals intelligence:

#### 1. Aviation NDB & ADF Training (Automatic Direction Finder)
Simulate realistic Non-Directional Beacon navigation (190 kHz - 535 kHz). 
* **The Night Effect (Ionospheric Fading):** Switch the clock to midnight to hear and observe the physical transition into `GrW+SkW` (Groundwave + Skywave phase cancellation). The resulting fading-induced bearing errors perfectly simulate the real-world erratic needle behavior pilots face at dawn or dusk.

#### 2. Maritime Radio Direction Finding (RDF) & Cross-Bearing Navigation
Replicate traditional maritime navigation used before the GPS era.
* **Triangulation/Fixing:** Users can maneuver the virtual vessel across the seas, tune into various coastal marine beacons, manually locate the sharp signal nulls using the antenna rotor, and plot the lines of position to calculate a highly precise cross-bearing fix.
* **Storm-Resilience Operations (QRN):** Engage the dynamic `StormEngine` to overlay intense atmospheric static discharges into the RF path. Trainees can practice pulling a weak beacon's null out of an intimidating wall of real-world thunder-crack noise.

#### 3. Virtual "Fox Hunting" (ARDF - Amateur Radio Direction Finding)
Create tactical field exercises straight from the cockpit of your PC.

#### 4. Hardware-In-The-Loop (HIL) Signal & AGC Benchmarking
Because the propagation engine modulates the **actual physical amplitude** via the connected SDR/RF modulator pipe, you can connect an authentic vintage communication receiver or a physical airborne ADF avionics unit directly to the RF output. The physical S-meter will drop, the audio will dip right into the noise floor as you hit an antenna null, and the hardware AGC loop will react natively to the calculated environmental physics.


### 🚀 Upcoming features: 

- Whether traveling through Europe, visiting distant exotic lands, or driving along the legendary Route 66 — from now on, the radio landscape will drift past your radio just as it did back when you were actually on that route.
see: https://github.com/radiolab81/AMWaveSynthPropagationSimulator/tree/main/plugins/MovableRXLocationPlayer

![MRXLP](https://github.com/radiolab81/AMWaveSynthPropagationSimulator/blob/main/www/mrxlp.jpg "virtual car radio travel")
 
- more to come

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
  
`python3.13 AMWaveSynthPropagationSIM.py`

in one go, simply

```console
#!/bin/bash
sudo apt update
sudo apt install build-essential cmake git python3-tk python3-gpxpy python3-geopy
git clone https://github.com/radiolab81/AMWaveSynthPropagationSimulator
sudo curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" INSTALLER_NO_MODIFY_PATH=1 sudo -E sh
cd AMWaveSynthPropagationSimulator
uv venv --python 3.13
source .venv/bin/activate
uv init
uv add -r requirements.txt
source .venv/bin/activate
python3.13 AMWaveSynthPropagationSIM.py

```
