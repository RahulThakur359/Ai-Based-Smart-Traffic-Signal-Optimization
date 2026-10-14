from traffic_engine.processor import RoadVideoProcessor


VIDEO_PATH = "uploads/road1/cam_1.mp4"


processor = RoadVideoProcessor()

print("Starting Road 1 AI processing...")

result = processor.process_video(
    VIDEO_PATH,
    max_frames=300
)

print("\n========== AI RESULT ==========")

for key, value in result.items():
    print(f"{key}: {value}")

print("================================")