# ISRO Hackathon Problem Statements: Plain English & Technical Report

This report provides a clear, detailed, and structured breakdown of all 14 problem statements present in the [problem statment.txt](file:///c:/Users/Admin/Desktop/Kshitiz/Isro%20Projeect/problem%20statment.txt) file. 

Each analysis is split into:
1. **Plain English Explanation (What is this about?):** Simple, jargon-free summary of the real-world problem and goal.
2. **Technical Deep Dive (How does it work?):** The underlying algorithms, mathematical frameworks, and machine learning models required.
3. **Data & Technical Requirements:** Datasets, libraries, and computational requirements.
4. **Expected Deliverables & Outcomes:** What the judges expect to see in the final solution.
5. **Codebase Synergy (Workspace Alignment):** How this maps to your existing **Healthcare ECG (CWT + EfficientNet + LightGBM)** and **TON-IoT (Split Federated Learning + Network telemetry classifiers)** codebase.

---

## Table of Contents
1. [Problem Statement 1: Urban Heat Mitigation & cooling strategies via AIML](#problem-statement-1-urban-heat-mitigation--cooling-strategies-via-aiml)
2. [Problem Statement 3: Surface AQI & HCHO Hotspot Identification](#problem-statement-3-surface-aqi--hcho-hotspot-identification)
3. [Problem Statement 4: Route Resilience: Occlusion-Robust Road Extraction & Graph Analysis](#problem-statement-4-route-resilience-occlusion-robust-road-extraction--graph-analysis)
4. [Problem Statement 5: AI-Powered Digital Twin of India's Climate](#problem-statement-5-ai-powered-digital-twin-of-indias-climate)
5. [Problem Statement 6: AI-Driven Crop Mapping, Moisture Stress & Irrigation Advisory](#problem-statement-6-ai-driven-crop-mapping-moisture-stress--irrigation-advisory)
6. [Problem Statement 7: Exoplanet Detection from Noisy Light Curves](#problem-statement-7-exoplanet-detection-from-noisy-light-curves)
7. [Problem Statement 8: Subsurface Ice Detection & Rover path planning in Lunar South Pole](#problem-statement-8-subsurface-ice-detection--rover-path-planning-in-lunar-south-pole)
8. [Problem Statement 9: Wavefront Reconstruction & Turbulence Characterization (SH-WFS)](#problem-statement-9-wavefront-reconstruction--turbulence-characterization-sh-wfs)
9. [Problem Statement 10: Infrared (IR) Image Colorization and Enhancement](#problem-statement-10-infrared-ir-image-colorization-and-enhancement)
10. [Problem Statement 11: Cross-Modal Satellite Image Retrieval](#problem-statement-11-cross-modal-satellite-image-retrieval)
11. [Problem Statement 12: Enhancing Temporal Resolution of Satellite Imagery via Optical Flow](#problem-statement-12-enhancing-temporal-resolution-of-satellite-imagery-via-optical-flow)
12. [Problem Statement 13: Air-Gapped Predictive Copilot for Secure MPLS Operations](#problem-statement-13-air-gapped-predictive-copilot-for-secure-mpls-operations)
13. [Problem Statement 14: Forecasting Energetic Particle Radiation for Geostationary Satellites](#problem-statement-14-forecasting-energetic-particle-radiation-for-geostationary-satellites)
14. [Problem Statement 15: Forecasting/Nowcasting Solar Flares via Aditya-L1 X-ray Data](#problem-statement-15-forecastingnowcasting-solar-flares-via-aditya-l1-x-ray-data)

---

### Problem Statement 1: Urban Heat Mitigation & cooling strategies via AIML

#### 1. Plain English Explanation
* **The Problem:** Cities are much hotter than surrounding rural areas due to concrete structures, lack of trees, and human activity (this is called the Urban Heat Island effect). This causes severe heat stress for citizens.
* **The Goal:** Build an AI system that takes satellite temperature maps and city layouts to locate the hottest spots (hotspots), understand why they are so hot (e.g., too much concrete, no trees), and run "what-if" simulations to suggest where to plant trees, put green roofs, or paint roofs white to cool the city down.

#### 2. Technical Deep Dive
* **Physics-Informed ML:** Standard ML models don't understand thermodynamics (how heat moves). You must build a physics-guided neural network (PINN) or integrate microclimate models (like SOLWEIG) that learn the mathematical relationships between Land Surface Temperature (LST), Land Use/Land Cover (LULC), and wind speed.
* **Optimization Engine:** Use genetic algorithms or reinforcement learning to find the optimal arrangement of cooling interventions (e.g., minimum trees planted for maximum temperature reduction).

#### 3. Data & Technical Requirements
* **Data:** Landsat 8 & ECOSTRESS Land Surface Temperature (LST), Sentinel-2 Land Use maps, OpenStreetMap (OSM) for city layouts, and ERA5 weather records.
* **Libraries:** PyTorch/TensorFlow, Rasterio/GDAL (geospatial parsing), InVEST/SOLWEIG modeling tools.

#### 4. Expected Deliverables & Outcomes
* High-resolution maps highlighting heat stress hotspots.
* An AI model capturing urban heat dynamics.
* A simulation dashboard where users can toggle virtual cooling strategies (e.g., "Add 20% trees in this zone") and view predicted temperature drops in °C.

#### 5. Codebase Synergy
* **Low-to-Medium:** You can reuse your Streamlit dashboard design, but the core engine relies heavily on spatial raster data, which is different from your tabular and 1D signal pipelines.

---

### Problem Statement 3: Surface AQI & HCHO Hotspot Identification

#### 1. Plain English Explanation
* **The Problem:** Air pollution is deadly, but ground monitors are sparse (most people live far from one). Also, forest fires and crop-burning release dangerous gases like Formaldehyde (HCHO) that are hard to track in real-time.
* **The Goal:** Use satellite observations (which scan the whole sky) to predict the Air Quality Index (AQI) on the ground. Additionally, locate major formaldehyde hotspots during burning seasons and trace how winds carry these toxic gases across India.

#### 2. Technical Deep Dive
* **Hybrid Deep Learning:** Train CNN-LSTM models where the CNN extracts spatial features from satellite pollutant columns, and the LSTM models the temporal movements (wind transport) over time.
* **Regression mapping:** Predict surface PM2.5 concentrations from satellite Aerosol Optical Depth (AOD) using CPCB ground monitors as training targets.

#### 3. Data & Technical Requirements
* **Data:** INSAT-3D AOD, Sentinel-5P (NO2, SO2, CO, O3, HCHO maps), CPCB ground air stations, MODIS/VIIRS fire counts, and ERA5 wind data.
* **Libraries:** Google Earth Engine (GEE) API, PyTorch/TensorFlow, NetCDF4.

#### 4. Expected Deliverables & Outcomes
* Dynamic maps of ground-level AQI over India.
* Temporal heatmaps showing HCHO hotspots during burning seasons.
* Wind vector overlays showing how smoke/gases travel.

#### 5. Codebase Synergy
* **Medium:** The CPCB ground-sensor dataset is tabular and requires feature engineering similar to your TON-IoT dataset. However, the spatial alignment with satellite bands requires GEE integration.

---

### Problem Statement 4: Route Resilience: Occlusion-Robust Road Extraction & Graph Analysis

#### 1. Plain English Explanation
* **The Problem:** When satellites take photos of cities, trees, building shadows, and clouds block the view of roads. If an AI tries to map these roads, it outputs "broken" fragments. In a disaster (like a flood), a broken road map is useless for routing emergency vehicles.
* **The Goal:** 
  1. Train an AI to "see through" shadows and tree cover to extract a continuous road map.
  2. Turn this visual map into a mathematical roadmap network (nodes and edges).
  3. Run stress-test simulations where you virtually "block" roads (due to flooding or accidents) and calculate how much longer traffic will take to reroute.

#### 2. Technical Deep Dive
* **Computer Vision Segmentation:** Train a U-Net or DeepLabV3+ with attention mechanisms (Transformers) to classify road pixels under occlusions.
* **Skeletonization:** Convert binary road masks into 1-pixel wide centerlines (morphological thinning).
* **Graph Healing:** Build a weighted vector network using Minimum Spanning Trees (MST) and Disjoint Sets to bridge gaps caused by trees.
* **Criticality & Ablation:** Compute Betweenness Centrality (identifying "gatekeeper" intersections) and iteratively delete nodes to calculate a global **Resilience Index**.

#### 3. Data & Technical Requirements
* **Data:** Sentinel-2, Resourcesat LISS-IV, Cartosat-3 imagery, SpaceNet/DeepGlobe road datasets, and OSM vector layers.
* **Libraries:** OpenCV, Albumentations, NetworkX (graph processing), PyG (Graph Neural Networks), Streamlit/Leaflet.js.

#### 4. Expected Deliverables & Outcomes
* High-accuracy road network graph.
* Spatial bottleneck heatmaps showing single points of network failure.
* An interactive dashboard where users click a node to "flood" it and immediately view rerouted paths and delays.

#### 5. Codebase Synergy
* **High:** Your experience with 2D computer vision (EfficientNet-B4 morphological embeddings from the ECG spectrograms) can be directly pivoted to road segmentation. Your backend routing and system design skills match the simulation dashboard requirements.

---

### Problem Statement 5: AI-Powered Digital Twin of India's Climate

#### 1. Plain English Explanation
* **The Problem:** Climate change causes unpredictable rain and extreme temperatures. Traditional physics-based climate models are slow and require supercomputers to run.
* **The Goal:** Build an "AI Digital Twin"—a fast, virtual replica of India's climate. It integrates historical and satellite weather feeds to predict short-term temperature and rainfall, and lets planners simulate "what-if" scenarios (e.g., "What happens to crops if temperature rises by 2°C?").

#### 2. Technical Deep Dive
* **Data Assimilation:** Fuse physical IMD gridded measurements with atmospheric satellite observations (INSAT LST/SST) using convolutional models or Fourier Neural Operators (FNOs).
* **Spatiotemporal Forecasting:** Train ConvLSTMs or spatial transformers to predict changes in rainfall and temperature grids.

#### 3. Data & Technical Requirements
* **Data:** IMD gridded rainfall (0.25° grid) and temperature (1° grid), INSAT-3D LST (Land Surface Temp) & SST (Sea Surface Temp).
* **Libraries:** PyTorch/TensorFlow, GDAL/Xarray, Streamlit/Mapbox.

#### 4. Expected Deliverables & Outcomes
* Fast AI weather prediction engine.
* Web-based map dashboard demonstrating predictions over a selected pilot region.
* Interactive "what-if" temperature/rainfall slider simulating regional climate shifts.

#### 5. Codebase Synergy
* **Medium:** The climate grids are structured arrays, representing a spatial extension of the time-series forecasting you explored. It does not directly leverage your SplitFed code.

---

### Problem Statement 6: AI-Driven Crop Mapping, Moisture Stress & Irrigation Advisory

#### 1. Plain English Explanation
* **The Problem:** To manage water resources and prevent crop failure, governments need to know what crops are growing, which ones are thirsty (moisture stress), and when they need watering. Clouds block optical satellites during the critical monsoon season.
* **The Goal:** Combine optical satellites (color cameras) and microwave radar satellites (which can see through clouds) to map crop types, detect water stress at different growth stages, and generate weekly watering schedules (irrigation advisories) for farms.

#### 2. Technical Deep Dive
* **Multitemporal Classification:** Train Random Forest/XGBoost on multi-date satellite signatures to classify crop types.
* **SAR Polarimetry:** Analyze Sentinel-1 Radar backscatter (VH/VV ratio) to assess canopy moisture under cloud cover.
* **Water Balance Modeling:** Compute Crop Water Demand ($ET_c$) using empirical crop coefficient formulas, and match it against rainfall and evapotranspiration data to map crop water deficits.

#### 3. Data & Technical Requirements
* **Data:** Sentinel-2, LISS-III/AWiFS (optical), Sentinel-1 (microwave SAR), IMD rainfall grids, and crop boundaries.
* **Libraries:** GEE, Rasterio, Scikit-Learn, PyTorch (Temporal CNN/LSTM).

#### 4. Expected Deliverables & Outcomes
* Automated crop-type maps (>85% target accuracy).
* Growth-stage-aware moisture stress maps (color-coded).
* Pixel-level irrigation advisory dashboards (showing liters/mm of water needed).

#### 5. Codebase Synergy
* **Medium-High:** You can directly port your **XGBoost and RandomForest classifiers** (from the TON-IoT project) to handle the multi-temporal tabular features extracted from the satellite pixel time-series.

---

### Problem Statement 7: Exoplanet Detection from Noisy Light Curves

#### 1. Plain English Explanation
* **The Problem:** Exoplanets (planets orbiting other stars) are detected by measuring tiny drops in a star's brightness as the planet passes in front of it (transit photometry). However, starspots, space dust, and telescope sensor noise make these drops look like random static.
* **The Goal:** Build an AI signal-processing pipeline that takes raw stellar brightness recordings (light curves), cleans the noise, identifies periodic dips, classifies them (Is it a planet? Or just a binary star system?), and calculates the planet's size and orbit speed.

#### 2. Technical Deep Dive
* **1D Signal Denoising:** Apply median filtering and spline fitting to remove low-frequency stellar activity.
* **Wavelet Transforms:** Convert the 1D light curve into a 2D time-frequency scalogram to detect periodic transits.
* **Hybrid Classification:** Use a 2D CNN (like EfficientNet) on the scalogram combined with 1D features (transit depth, duration, period) processed by LightGBM.
* **Curve Fitting:** Fit Keplerian transit models to estimate orbital period, transit depth (planet size), and transit duration.

#### 3. Data & Technical Requirements
* **Data:** NASA TESS high-cadence raw stellar light curves (public STScI archive, CDF/FITS formats).
* **Libraries:** Lightkurve, Astropy, PyTorch/TensorFlow, Scipy (curve fitting).

#### 4. Expected Deliverables & Outcomes
* Automated transit detection and classification pipeline.
* Estimated planetary orbital parameters with confidence scores.
* Dashboard showing the raw light curve, fitted transit models, and orbital animations.

#### 5. Codebase Synergy
* **High:** This fits your **ECG Classification System** perfectly! Both systems process noisy 1D signals. You can directly adapt your **Continuous Wavelet Transform (CWT)** and **EfficientNet-B4 + LightGBM hybrid network** to classify transit signals instead of ECG heartbeats.

---

### Problem Statement 8: Subsurface Ice Detection & Rover path planning in Lunar South Pole

#### 1. Plain English Explanation
* **The Problem:** For astronauts to survive on the Moon, they need water. Water-ice is trapped in deep, frozen craters at the Lunar South Pole that never see daylight. We need to identify where this ice is located under the dirt, choose a safe spot to land a spacecraft nearby, and map out the safest path for a rover to drive into the dark crater to mine the ice.
* **The Goal:** 
  1. Analyze spacecraft radar data to locate subsurface ice in dark craters.
  2. Analyze crater slopes and rocks to find a safe landing site.
  3. Run path-planning algorithms to design the safest, shortest route for a solar-powered rover.

#### 2. Technical Deep Dive
* **Polarimetric Radar Processing:** Compute circular polarization ratios (CPR) and degrees of polarization (DOP) from DFSAR radar bands. Subsurface ice has unique polarimetric scattering signatures.
* **Ice Volume Estimation:** Apply dielectric mixing models to estimate ice volume in the top 5 meters of dirt.
* **Path Planning & Optimization:** Build an A* search, Dijkstra, or Reinforcement Learning agent to plan paths across Digital Elevation Models (DEMs) while avoiding steep slopes (>15°), boulders, and ensuring the rover stays in sunlit zones for battery charging.

#### 3. Data & Technical Requirements
* **Data:** Chandrayaan-2 DFSAR (Radar), OHRC (high-res camera), and DEM terrain data.
* **Libraries:** QGIS, GDAL, Python (Scipy, Path-planning packages), MIDAS (DFSAR utility).

#### 4. Expected Deliverables & Outcomes
* Subsurface ice probability maps.
* A coordinate location for a safe landing site.
* Interactive map displaying the optimized rover route, factoring in slopes and solar charging constraints.

#### 5. Codebase Synergy
* **Low-to-Medium:** Focuses heavily on planetary radar geophysics and path planning algorithms. No direct overlap with your tabular ML or federated frameworks.

---

### Problem Statement 9: Wavefront Reconstruction & Turbulence Characterization (SH-WFS)

#### 1. Plain English Explanation
* **The Problem:** Earth's atmosphere is turbulent (warm and cold air mixing), which distorts light passing through it. This makes stars look blurry through telescopes. Deformable Mirrors (DMs) can warp their shape in real-time to cancel out this blur, but they need to know exactly how the light is distorted in milliseconds.
* **The Goal:** Write ultra-fast algorithms that take images from a special grid camera (Shack-Hartmann Wavefront Sensor), calculate how far light spots have shifted, reconstruct the distorted light wave, and compute the mirror commands to flatten it.

#### 2. Technical Deep Dive
* **Centroiding:** Run sub-pixel centroiding algorithms (like Center of Gravity or weighted center) to find the center of thousands of tiny light spots in WFS camera frames.
* **Wavefront Reconstruction:** Solve a set of linear equations ($s = G \cdot \phi$) mapping spot displacements ($s$) to wavefront phase parameters ($\phi$) using Modal (Zernike polynomials) or Zonal methods (least-squares/conjugate gradient).
* **Actuator Mapping:** Map the phase map to deformable mirror actuator stroke lengths, accounting for inter-actuator physical coupling.

#### 3. Data & Technical Requirements
* **Data:** Shack-Hartmann WFS camera frame sequences (.bmp format), camera metrics, and DM actuator layouts.
* **Language:** Low-level language recommended (**C/C++**) due to the extreme speed requirement (<10ms).
* **Libraries:** OpenCV, Eigen/Armadillo (linear algebra).

#### 4. Expected Deliverables & Outcomes
* Ultra-fast wavefront phase reconstruction code.
* Calculated turbulence metrics: Fried parameter ($r_0$) and coherence time ($\tau_0$).
* Deformable mirror actuator voltage maps.

#### 5. Codebase Synergy
* **Low:** This requires low-level, high-performance C programming and matrix calculus. It does not align with your Python ML and federated pipelines.

---

### Problem Statement 10: Infrared (IR) Image Colorization and Enhancement

#### 1. Plain English Explanation
* **The Problem:** Night-vision and thermal satellites capture infrared (IR) images. These images are blurry, black-and-white, and hard for humans or algorithms to interpret (e.g., distinguishing between a river and a road at night).
* **The Goal:** Build an AI model that takes a single-channel, low-res IR satellite image, sharpens its edges (super-resolution), and paints it in realistic colors (e.g., coloring trees green and rivers blue) so it looks like a standard daytime photo, without making up fake objects.

#### 2. Technical Deep Dive
* **Generative Adversarial Networks (GANs):** Train a Pix2Pix or CycleGAN for image-to-image translation (IR $\rightarrow$ RGB).
* **Semantic Constraints:** Pass the generated image through a auxiliary pre-trained classifier (like a Land-Cover Segmentation network) to penalize the generator if it colors water red or forest blue (semantic consistency loss).
* **Super-Resolution:** Train a SRCNN or ESPCN block at the input to upscale the blurry IR frame.

#### 3. Data & Technical Requirements
* **Data:** Paired Landsat 8/9 Thermal/IR bands and visible RGB bands.
* **Libraries:** PyTorch/TensorFlow, OpenCV, Rasterio.

#### 4. Expected Deliverables & Outcomes
* End-to-end IR-to-RGB translation model.
* High-resolution, realistically colored satellite tiles.
* Validation metrics: PSNR, SSIM, and FID (assessing realism).

#### 5. Codebase Synergy
* **Medium:** Connects to your general computer vision experience, but requires generative modeling (GANs) and geospatial processing libraries, which are not currently in your active codebase.

---

### Problem Statement 11: Cross-Modal Satellite Image Retrieval

#### 1. Plain English Explanation
* **The Problem:** Satellite databases are massive. A user might have a radar image (SAR) of a port at night and want to find daytime visible photos of that same port. Because radar and visible photos look completely different, search engines can't easily match them.
* **The Goal:** Build an AI search engine that understands "semantic similarity." If a user uploads a radar image of a forest, the system should instantly find and rank the most similar visible-light images of forests from the database, ignoring the sensor differences.

#### 2. Technical Deep Dive
* **Contrastive Metric Learning:** Train a dual-encoder network (Siamese or Triplet Networks, similar to CLIP) to map optical images and SAR images into a unified, shared embedding space.
* **Loss Function:** Use InfoNCE or Triplet Loss to pull matching SAR-Optical pairs close together in vector space while pushing non-matching pairs far apart.
* **Vector Search:** Index the gallery database using FAISS (Facebook AI Similarity Search) for sub-millisecond retrieval.

#### 3. Data & Technical Requirements
* **Data:** Paired multi-sensor images (Optical, Multispectral, and SAR) covering the same geographic locations.
* **Libraries:** PyTorch, FAISS, pre-trained Vision Transformers (ViT) or ResNets.

#### 4. Expected Deliverables & Outcomes
* Multi-modal feature extraction model.
* A search engine returning ranked top-5 and top-10 matching images for a given query.
* Validation metrics: F1-score@5 and F1-score@10.

#### 5. Codebase Synergy
* **Medium:** The contrastive mapping concept is similar to your **NoPeek loss** (which correlates/decorrelates activation spaces), but applied to image embedding models instead of SplitFed privacy.

---

### Problem Statement 12: Enhancing Temporal Resolution of Satellite Imagery via Optical Flow

#### 1. Plain English Explanation
* **The Problem:** Weather satellites scan the Earth at fixed intervals (e.g., every 30 minutes). If a fast-moving storm, cyclone, or flood happens between scans, we miss it.
* **The Goal:** Build an AI system that takes two consecutive satellite images (e.g., at 12:00 and 12:30) and generates artificial "in-between" frames (e.g., at 12:15) by predicting how clouds and storms are moving. This lets us generate a smooth weather animation without needing new satellites.

#### 2. Technical Deep Dive
* **Optical Flow Estimation:** Train models (like RAFT or SpyNet) to estimate bidirectional motion vectors between frame $T_0$ and $T_1$.
* **Frame Synthesis:** Train a frame interpolation network (like RIFE or Super SloMo) that uses the estimated motion vectors to warp the original frames and synthesize a realistic intermediate frame ($T_{0.5}$).

#### 3. Data & Technical Requirements
* **Data:** Geo-stationary satellite thermal bands (.nc NetCDF or .h5 formats) from GOES-19, INSAT-3DS, or Himawari-8.
* **Libraries:** PyTorch, OpenCV, NetCDF4, Web development tools (for dashboard animation rendering).

#### 4. Expected Deliverables & Outcomes
* Deep learning frame interpolation model.
* Interactive dashboard displaying side-by-side animations of the original 30-min frames vs. the smooth 15-min interpolated sequences.
* Accuracy scores comparing simulated frames against real validation data.

#### 5. Codebase Synergy
* **Medium-Low:** Purely video frame interpolation. Requires heavy temporal deep learning models.

---

### Problem Statement 13: Air-Gapped Predictive Copilot for Secure MPLS Operations

#### 1. Plain English Explanation
* **The Problem:** Modern corporate and government networks are complex. When something goes wrong (e.g., a connection drops or a link gets congested), network operators get flooded with cryptic alerts. In highly secure, classified environments, they cannot send these alerts to cloud AI tools (like ChatGPT) due to data privacy laws.
* **The Goal:** Build a fully self-hosted, offline AI system that:
  1. Predicts network issues *before* they happen by analyzing network logs and usage trends.
  2. Runs a local, secure chatbot (LLM) on an offline server that can read the network map and runbooks to tell the operator exactly what is failing, why, and how to fix it in plain English.

#### 2. Technical Deep Dive
* **Anomaly Detection:** Train classifiers (RandomForest, LightGBM, XGBoost) and time-series predictors (Prophet, LSTMs) to identify precursor states (congestion trends, route flapping).
* **Local LLM & RAG:** Deploy a quantized LLM (e.g., LLaMA-3-8B-Q4) locally using Ollama or llama.cpp. Build a RAG (Retrieval-Augmented Generation) pipeline over network maps and troubleshooting guides using a local vector database (e.g., ChromaDB, FAISS).
* **Distributed Analytics (Your Innovation):** Orchestrate telemetry aggregation across secure branches using **Split Federated Learning (SplitFed)**. Nodes train local ML components locally, transmitting encrypted, 8-bit quantized smashed activations to prevent leakage of network IPs and topologies.

#### 3. Data & Technical Requirements
* **Data:** SNMP metrics, Syslog events, NetFlow traffic logs, and configuration files.
* **Libraries:** PyTorch, NetworkX, Ollama, LangChain, ChromaDB/FAISS, Streamlit.

#### 4. Expected Deliverables & Outcomes
* Machine learning predictive anomaly engine.
* Safe, offline LLM chatbot answering operator questions ("What is likely to fail next?").
* Streamlit dashboard displaying network graphs, active alerts, and AI action playbooks.

#### 5. Codebase Synergy
* **Extreme (95%+):** Your codebase is built for this! You have the telemetry classifiers (`ton-iot-project`), the Streamlit interfaces, and the exact Split Federated Learning framework with advanced privacy defenses (NoPeek, DP, 8-bit Quantization, FedProx) needed to coordinate multiple secure edge NOC sites safely.

---

### Problem Statement 14: Forecasting Energetic Particle Radiation for Geostationary Satellites

#### 1. Plain English Explanation
* **The Problem:** Satellites in high orbits (geostationary orbit) are bombarded by high-energy electrons. During solar storms, this radiation spikes, which can fry satellite electronics. Satellite operators need warning to temporarily shut down sensitive systems.
* **The Goal:** Build an AI model that reads solar wind data and space magnetic field measurements to predict radiation levels 30 minutes, 6 hours, and 12 hours in advance.

#### 2. Technical Deep Dive
* **Multivariate Time-Series Forecasting:** Train LSTMs, GRUs, or Temporal Convolutional Networks (TCN) to perform multi-step forecasting of electron fluxes.
* **Feature Selection:** Analyze physics-based correlations between solar wind speed, magnetic field strength (IMF), density, and downstream electron flux levels.

#### 3. Data & Technical Requirements
* **Data:** NASA GOES satellite >2 MeV electron fluxes (CDF format), NASA Wind spacecraft solar wind data, and ISRO GRASP payload data.
* **Libraries:** Spacepy (for CDF handling), PyTorch/TensorFlow, Scikit-Learn.

#### 4. Expected Deliverables & Outcomes
* Data processing and cleaning pipeline for space datasets.
* Time-series prediction model forecasting flux levels at various horizons (30m, 6h, 12h).
* Dashboard displaying real-time predictions and warning alert banners.

#### 5. Codebase Synergy
* **Medium-Low:** Heavily focused on space physics and multi-step time-series regression.

---

### Problem Statement 15: Forecasting/Nowcasting Solar Flares via Aditya-L1 X-ray Data

#### 1. Plain English Explanation
* **The Problem:** Solar flares are massive explosions on the sun that release radiation. These flares can disrupt GPS and power grids on Earth.
* **The Goal:** Use data from ISRO's Aditya-L1 spacecraft (which sits between the Earth and Sun) to build an AI system that:
  1. Instantly detects and classifies flares as they happen (nowcasting).
  2. Analyzes precursor signals (small wobbles in X-ray readings) to predict a solar flare *before* it erupts (forecasting).

#### 2. Technical Deep Dive
* **Flarer Nowcasting (Detection):** Develop automated peak-detection and thresholding algorithms to classify flare classes (A, B, C, M, X class) in real-time.
* **Precursor Forecasting:** Train sequence models (LSTMs, Transformers) or 1D CNNs on combined Soft and Hard X-ray light curves to output the probability of a flare occurring in the next $N$ minutes.

#### 3. Data & Technical Requirements
* **Data:** Aditya-L1 SoLEXS (Soft X-ray) and HEL1OS (Hard X-ray) light curves from the ISRO ISSDC portal.
* **Libraries:** Astropy, SunPy, PyTorch/TensorFlow, Scipy.

#### 4. Expected Deliverables & Outcomes
* Automated solar flare catalog database.
* Time-series forecasting model with a measured lead time in minutes.
* UI dashboard plotting real-time light curves and triggering flashing alerts.

#### 5. Codebase Synergy
* **Medium-High:** Like the exoplanet problem, this is a 1D time-series classification and anomaly detection challenge. It maps well to your signal processing experience (CWT spectrogram transformation + classifiers) developed for your ECG Arrhythmia detection system.

---

## Technical Summary Matrix

| Problem Statement | Real-World Domain | Core AI Method | Input Data Type | Your Codebase Reuse Potential |
| :--- | :--- | :--- | :--- | :--- |
| **PS 1** | Urban Cooling | Physics-Informed ML, Optimization | Geospatial (Raster & Vector) | Low (Streamlit UI only) |
| **PS 3** | Air Quality | CNN-LSTM, Regression | Geospatial & Weather grids | Medium (Tabular CPCB data) |
| **PS 4** | Urban Transit | CV Segmentation, Graph Theory | High-res satellite imagery | High (Spectrogram CV, Dashboards) |
| **PS 5** | Climate Twin | Spatiotemporal Grid Forecasting | Temperature/Rainfall arrays | Medium (Array processing) |
| **PS 6** | Precision Ag | Random Forest, Radar Backscatter | Satellite bands (SAR/Optical) | Medium-High (RF/XGBoost models) |
| **PS 7** | Exoplanets | 1D Denoising, CWT + LightGBM | Stellar light curves (1D) | High (ECG CWT + Classifier architecture) |
| **PS 8** | Moon Ice | Radar Polarimetry, A* Search | Radar data, elevation maps | Low (Geophysics domain) |
| **PS 9** | Optics/Mirror | Centroiding, Linear System solver | Fast camera frames (.bmp) | Low (Requires C/C++) |
| **PS 10**| Night Vision | Super-Resolution, GANs | Thermal & Visual imagery | Medium (Computer Vision) |
| **PS 11**| Search Engine | Contrastive Metric Learning | Multi-sensor aligned imagery | Medium (Embeddings/Activations) |
| **PS 12**| Satellite Video| Optical Flow, Interpolation | Satellite frame sequences | Low (Temporal CV) |
| **PS 13**| Secure NOC | ML Classifiers, Local LLM RAG, SFL | Network logs (Syslog, SNMP) | **Extreme (TON-IoT, SplitFed, UI)** |
| **PS 14**| Space Radiation | Multi-step Time Series Regression | Spacecraft telemetry | Medium-Low (Physics telemetry) |
| **PS 15**| Solar Flares | 1D Peak Detection, Sequence prediction| Spacecraft X-ray curves (1D) | Medium-High (ECG CWT + Classifiers) |
