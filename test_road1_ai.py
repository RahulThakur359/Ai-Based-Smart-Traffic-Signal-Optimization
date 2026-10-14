import cv2

from traffic_engine.detector import VehicleDetector


VIDEO_PATH = "uploads/road1/cam_1.mp4"


def main():

    print("Loading YOLOv8 model...")

    detector = VehicleDetector("yolov8n.pt")

    if detector.model is None:

        print("ERROR: YOLO model could not be loaded.")

        return

    print("YOLOv8 model loaded successfully.")
    print("Opening Road 1 video...")

    cap = cv2.VideoCapture(VIDEO_PATH)

    if not cap.isOpened():

        print(
            f"ERROR: Could not open video: {VIDEO_PATH}"
        )

        return

    print("Road 1 video opened successfully.")
    print("Press Q to stop.")

    frame_number = 0

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        frame_number += 1

        # YOLO detection
        detections = detector.detect(frame)

        print(
            f"Frame {frame_number}: "
            f"{len(detections)} vehicles detected"
        )

        # Draw detections
        for detection in detections:

            x1 = detection["x1"]
            y1 = detection["y1"]
            x2 = detection["x2"]
            y2 = detection["y2"]

            confidence = detection["confidence"]
            class_name = detection["class_name"]

            # Bounding box
            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                (0, 255, 0),
                2
            )

            # Label
            label = (
                f"{class_name} "
                f"{confidence:.2f}"
            )

            cv2.putText(
                frame,
                label,
                (x1, max(y1 - 10, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2
            )

        # Display
        cv2.imshow(
            "Road 1 - YOLOv8 Vehicle Detection",
            frame
        )

        # Press Q to quit
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()

    cv2.destroyAllWindows()

    print(
        f"Road 1 detection completed. "
        f"Total frames processed: {frame_number}"
    )


if __name__ == "__main__":
    main()