from time import time_ns
import face_recognition
import cv2
import numpy as np
import sys
from datetime import datetime

def main(saved, attempt):

    #load the user image and get the face encoding
    saved_image = face_recognition.load_image_file(f"../faces/{saved}.jpg")
    saved_face_encoding = face_recognition.face_encodings(saved_image)[0]
    saved_face_encodings = [saved_face_encoding]
    attempt_image = face_recognition.load_image_file(f"../faces/{attempt}.jpg")
    attempt_face_encoding = face_recognition.face_encodings(attempt_image)[0]
    score = face_recognition.face_distance(saved_face_encodings, attempt_face_encoding)
    print("saved: " + str(saved_face_encoding))
    print("saved: " + str(attempt_face_encoding))
    print("score: " + str(score))

    
if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
