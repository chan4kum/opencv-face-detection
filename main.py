import argparse
import cv2

cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def annotate(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
    for x, y, w, h in faces:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
    cv2.putText(frame, f"Faces: {len(faces)}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    return frame


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--image", help="path to an image (default: webcam)")
    args = p.parse_args()

    if args.image:
        img = cv2.imread(args.image)
        if img is None:
            raise SystemExit(f"Could not read {args.image}")
        cv2.imshow("Face Detection", annotate(img))
        cv2.waitKey(0)
    else:
        cap = cv2.VideoCapture(0)
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                break
            cv2.imshow("Face Detection", annotate(frame))
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
