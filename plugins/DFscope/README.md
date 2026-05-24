# 📡 Interactive Radio Direction Finding (RDF) Training Suite

The **AMWaveSynth** ecosystem now features a fully networked, multi-user training environment. By connecting the master Propagation Simulator with two brand-new trainee applications—**DFscope** and **DFmap**—instructors can simulate realistic Radio Direction Finding (RDF) scenarios. 

This client-server architecture utilizes a zero-config UDP broadcast system, allowing students to instantly discover and connect to the instructor's active simulation without manual IP configuration.

## 🧭 DFscope: The Trainee Console
**DFscope** is a "Glass Cockpit" style tactical display that transforms the trainee's screen into a radio direction finder control. It directly receives the currently active antenna radiation pattern (imported via `.MSI` or `.ANT` files) from the instructor's engine and renders it as a live, rotatable polar plot.

* **Real-Time Null Steering:** Automatically calculates and visually highlights signal nulls (minimums) in the antenna pattern, providing an alphanumeric readout of the precise bearing.
* **Dynamic Attenuation Plotting:** Renders a smooth, dynamic polygon representing signal strength relative to the current heading, scaling dynamically to a 30 dB dynamic range.
* **Zero-Latency Hardware Control:** As the trainee rotates the digital lubber line, heading data (`HDG`) is streamed back to the master simulator. This instantly alters the RF signal synthesis of the AMWaveSynth engine, directly affecting the live transmission emitted via your SDR. Trainees can physically hear the signal fading and nulling on a real radio receiver in real-time!

## 🗺️ DFmap: Tactical Bearing Plotter
**DFmap** complements the acoustic and polar data by providing geodetic context. It acts as the trainee's digital map board, automatically syncing the live list of active transmitters from the propagation engine.

* **Live Transmitter Sync:** Instantly populates the map with all currently simulated active transmission sites, complete with frequency data.
* **Geodesic Bearing Lines:** Trainees can click on a known transmitter and drag their virtual "beam" across the map. The engine calculates true geodesic curves (accounting for the Earth's curvature) to plot highly accurate lines of bearing.
* **Visual Compass Roses:** Automatically renders a 40km radius compass rose around selected targets for quick tactical orientation.

## 📊 Module Comparison

| Feature | DFscope (Console) | DFmap (Tactical Map) |
| :--- | :--- | :--- |
| **Primary Use Case** | Antenna rotation, signal nulling, local orientation | Geodetic plotting, triangulation, situational awareness |
| **Data Received** | Antenna Polar Patterns (`GET_CONFIG`) | Active Transmitter Locations (`GET_TRANSMITTERS`) |
| **Data Sent** | Current Heading (`HDG:xxx`) | None (Passive Visualization) |
| **UI Style** | Dark Mode / Aviation Glass Cockpit | Interactive OpenStreetMap / Topographic |

---

## 🚀 Getting Started & Workflow

To set up the interactive training environment, it is highly recommended to start the modules in the following order:

### 1. The Instructor (Master Engine)
* Run the main `AMWaveSynthPropagationSIM.py` (or your master UI script) on the instructor's machine.
* This initializes the simulation environment, loads the map, and starts the UDP listeners (Port 8887 for RDF telemetry, Port 8888 for Gain control).
* *Note:* Ensure your SDR hardware is connected and the AMWaveSynth engine is actively synthesizing the RF spectrum.

### 2. The Trainee (Clients)
* On the trainee PC(s)—which must be on the same local network—run `DFscope.py` (DFscope) and/or `DFmap.py` (DFmap).
* Upon startup, the apps will default to looking for a local master (`127.0.0.1`). 
* **Zero-Config Discovery:** If the master is running on a different machine in the room, simply click **SYNC / LOAD DATA**. The connection will time out after 2 seconds, and a network discovery dialog will appear.
* Click **SCAN** to broadcast a UDP ping to the local subnet.
* Select the discovered Instructor IP from the list and click **CONNECT**.

### 3. Live Training Execution
* **Instructor:** Place the "secret" RX Location. Load an `.MSI` or `.ANT` antenna pattern in the master engine.
* **DFscope:** The trainee's console will automatically pull the data and display the loaded antenna pattern.
* **DFmap:** The trainee's map will automatically sync all active transmission sites placed by the instructor.
* **Action:** As the trainee searches for the signal null using the DFscope slider, the master engine calculates the attenuation on the fly, physically altering the SDR's RF output. Trainees use their real receivers to find the perfect bearing!

## 🎯 Target Audiences & Educational Value

The **AMWaveSynth Interactive RDF Suite** bridges the gap between theoretical software simulation and hands-on hardware training. By integrating live SDR output with networked digital instruments, this project is highly beneficial for:

* **📻 Amateur Radio (Ham) Clubs:** An ideal tool for indoor "Fox Hunt" (ARDF - Amateur Radio Direction Finding) training. Clubs can practice signal nulling, triangulation, and map plotting regardless of weather conditions or physical location constraints.
* **⚓ Maritime & Aviation Schools:** A perfect sandbox for teaching traditional radio navigation techniques (like NDB/ADF tracking). It allows cadets to build confidence in using non-satellite-based, analog backup systems.
* **🎓 University & STEM Educators:** Provides students with a tangible way to experience RF physics. Instead of just looking at static antenna polar plots on a whiteboard, students can physically hear how radiation patterns and geographic distances affect real RF signals.
