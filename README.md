# AI-Based Smart Traffic Signal Optimization Using Computer Vision and Deep Learning

B.E. Computer Engineering Major Project

---

## 1. Project Description
Urban traffic congestion is a critical issue causing massive delays, fuel waste, and increased emissions. Traditional traffic signals operate on fixed timing plans or simple inductive loop triggers that do not adapt to real-time traffic volumes. 

This project implements an **AI-Based Smart Traffic Signal Optimization** system. Using camera feeds at a four-way intersection, the system detects vehicles, tracks them, estimates real-time road density and wait times, and dynamically adjusts green signal phases using computer vision algorithms and scheduling heuristics to optimize throughput.

---

## 2. Key Objectives
*   **Real-time Object Detection:** Detect vehicles (cars, trucks, buses, motorcycles) using a custom-trained **YOLOv8** model.
*   **Vehicle Tracking:** Maintain vehicle identities across frames using **ByteTrack** to calculate individual waiting times.
*   **Emergency Vehicle Preemption:** Detect emergency vehicles (e.g., ambulances) using a specialized classifier to immediately trigger green lights.
*   **Dynamic Signal Control:** Replace standard timers with dynamic green phase scheduling based on priority scores (calculated from count, density, and wait times).
*   **Data Logging & Auditing:** Keep database logs of traffic performance and signal decisions for post-congestion analysis.

---

## 3. Technology Stack
*   **Backend Web Server:** Python Flask (v3.x)
*   **Computer Vision & AI:** OpenCV, Ultralytics YOLOv8, ByteTrack
*   **Database:** MySQL Server
*   **Frontend UI:** Vanilla HTML5, CSS3, JavaScript (Canvas API for charts)

---

## 4. Project Directory Structure
```
AI_Traffic_Signal/
│
├── app.py                     # Flask main application server
├── config.py                  # Global configurations and env variable setups
├── requirements.txt           # Python package dependencies
├── README.md                  # Project documentation
├── .gitignore                 # Excluded directories
│
├── venv/                      # Local virtual environment
│
├── models/                    # Model checkpoints repository
│   ├── yolov8n.pt             # Pre-trained base model weights
│   ├── best.pt                # Custom traffic detection weights
│   └── ambulance_best.pt      # Custom emergency vehicle weights
│
├── data/
│   ├── raw/                   # Raw traffic streams (e.g. cam_1.mp4 to cam_4.mp4)
│   ├── processed/             # Output recordings showing tracks and count lines
│   ├── datasets/              # Training/Validation split repositories
│   │   └── traffic/
│   └── annotations/           # Ground truth label definitions
│
├── uploads/                   # Upload subfolders for roads 1-4
│   ├── road1/
│   ├── road2/
│   ├── road3/
│   └── road4/
│
├── outputs/                   # Processed outputs directory
│   ├── road1/
│   ├── road2/
│   ├── road3/
│   └── road4/
│
├── runs/                      # YOLO model validation and predict checkpoints
│   ├── detect/
│   └── track/
│
├── training/                  # YOLOv8 custom training scripts package
│   ├── train.py
│   ├── validate.py
│   ├── test.py
│   └── dataset.yaml
│
├── traffic_engine/            # Computer vision analytics engine
│   ├── __init__.py
│   ├── detector.py
│   ├── tracker.py
│   ├── vehicle_counter.py
│   ├── movement_analyzer.py
│   ├── density.py
│   ├── waiting_time.py
│   ├── congestion.py
│   └── emergency_detector.py
│
├── optimization/              # Dynamic scheduling controller algorithms
│   ├── __init__.py
│   ├── priority.py
│   ├── signal_controller.py
│   ├── timing.py
│   └── optimizer.py
│
├── database/                  # Data persistence helper layer
│   ├── __init__.py
│   ├── db.py
│   ├── models.py
│   └── queries.py
│
├── routes/                    # HTTP Blueprints controllers
│   ├── __init__.py
│   ├── dashboard.py
│   ├── upload.py
│   ├── traffic_api.py
│   ├── signal_api.py
│   └── report_api.py
│
├── templates/                 # Glassmorphic HTML templates
│   ├── dashboard.html
│   ├── login.html
│   ├── reports.html
│   └── settings.html
│
├── static/                    # Dashboard UI styles & logic
│   ├── css/
│   │   ├── style.css
│   │   └── dashboard.css
│   │
│   ├── js/
│   │   ├── dashboard.js
│   │   ├── signal.js
│   │   └── charts.js
│   │
│   └── images/
│
└── reports/                   # Performance output PDF/CSV sheets
    ├── daily/
    ├── weekly/
    └── monthly/
```

---

## 5. Local Installation Steps

### Step 5.1: Create Python Virtual Environment
Navigate to the project root and create a virtual environment:
```powershell
python -m venv venv
```

Activate the environment:
*   **Windows (PowerShell):**
    ```powershell
    .\venv\Scripts\Activate.ps1
    ```
*   **Windows (CMD):**
    ```cmd
    .\venv\Scripts\activate.bat
    ```
*   **Linux / macOS:**
    ```bash
    source venv/bin/activate
    ```

### Step 5.2: Install Required Dependencies
Install the required packages using the requirements list:
```powershell
pip install -r requirements.txt
```

### Step 5.3: Start the Flask Server
Run the startup script:
```powershell
python app.py
```
Open a browser and navigate to:
[http://127.0.0.1:5000/](http://127.0.0.1:5000/)

---

## 6. Model Weight Setup
To run vehicle detection and emergency vehicle detection, download and place model weights in the `models/` directory:
1.  **YOLOv8n.pt:** Download from Ultralytics releases.
2.  **best.pt:** Save custom-trained vehicle detector weights here.
3.  **ambulance_best.pt:** Save custom ambulance detection weights here.

The backend automatically checks for model existence. If weights are missing, the server logs a warning and runs in standby mode, ensuring developers can test the web interfaces independently of heavy GPU requirements.

---

## 7. Future AI/ML Pipeline Integration Roadmap
1.  **OpenCV Stream Handler:** Read frames from uploaded videos in `uploads/roadX/`.
2.  **YOLO Inference:** Pass frames to `VehicleDetector.detect()`.
3.  **ByteTrack Tracker:** Pass bounding box results to `VehicleTracker.update()` to map tracking IDs.
4.  **Density & Waiting Times:** Run `TrafficDensityCalculator` and `WaitingTimeEstimator` to compute real metrics.
5.  **Heuristic Optimization:** Pass computed densities and waiting times to `TrafficSignalOptimizer.optimize_cycle()` to decide the next green phase and duration.
6.  **Database log & UI updates:** Save metrics into MySQL and serve values to the dashboard using `/api/traffic/status` and `/api/signal/status`.




how to run website:
case1: if in path see : New website; then : cd.. ; then : .\venv\Scripts\activate ; then: cd "New website" ; then : python app.py

if in path see : venv; then : deactivate ;{
    case1
}

PATH Aisa Hona chahiye:
C:\Users\Ranjan Thakur\Desktop\AI_Traffic_Signal>.\venv\Scripts\activate
    (venv) C:\Users\Ranjan Thakur\Desktop\AI_Traffic_Signal>cd "New website"
        (venv) C:\Users\Ranjan Thakur\Desktop\AI_Traffic_Signal\New website>python app.py
        