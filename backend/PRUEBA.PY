import cv2

video_path = "p4testdiagnosticoreal.mp4"
cap = cv2.VideoCapture(video_path)

total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 30)
ret, frame = cap.read()

if ret:
    cv2.imwrite("debug_frame.jpg", frame)

cap.release()