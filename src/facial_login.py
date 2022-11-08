from time import time_ns
import face_recognition
import cv2
import numpy as np
import sys
from datetime import datetime

def main(user):

    #default webcam
    video_capture = cv2.VideoCapture(0)

    #load the user image and get the face encoding
    user_image = face_recognition.load_image_file(f"faces/{user}.jpg")
    user_face_encoding = face_recognition.face_encodings(user_image)[0]

    #create arrays of known face encodings and their names
    known_face_encodings = [
        user_face_encoding
    ]
    known_face_names = [
        user
    ]

    face_locations = []
    face_encodings = []
    face_names = []
    process_this_frame = True
    found = False
    time = datetime.now()
    max_time = 10 #seconds
    start_time = datetime.now()

    while (not found and (time-start_time).total_seconds() < max_time):

        

        # Grab a single frame of video
        ret, frame = video_capture.read()

        # Only process every other frame of video to save time
        if process_this_frame:
            # Resize frame of video to 1/4 size for faster face recognition processing
            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)

            # Convert the image from BGR color (which OpenCV uses) to RGB color (which face_recognition uses)
            rgb_small_frame = small_frame[:, :, ::-1]
            
            # Find all the faces and face encodings in the current frame of video
            face_locations = face_recognition.face_locations(rgb_small_frame)
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

            for face_encoding in face_encodings:
                # See if the face is a match for the known face(s)
                matches = face_recognition.compare_faces(known_face_encodings, face_encoding)

                # Or instead, use the known face with the smallest distance to the new face
                face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                best_match_index = np.argmin(face_distances)
                if matches[best_match_index]:
                    found = True
                    break

        process_this_frame = not process_this_frame
        
        time = datetime.now()
        #print("time: " + str(time))

    if (found):
        print("AUTENTICATO")
    else:
        print("NON AUTENTICATO")

    # Release handle to the webcam
    video_capture.release()
    cv2.destroyAllWindows()

    if (found):
        return True
    else:
        return False

if __name__ == "__main__":
    main(sys.argv[1])