from time import time_ns
import face_recognition
import cv2
import numpy as np
import sys
from datetime import datetime
import random

noise_factor = 30

def main(saved, attempt):

    #load the user image and get the face encoding
    saved_image = face_recognition.load_image_file(f"../faces/{saved}.jpg")
    saved_face_encoding = face_recognition.face_encodings(saved_image)[0]
    saved_face_encodings = [saved_face_encoding]

    dims_to_modify = random.randint(0,127)
    noise_array = []
    for i in range(128):
        noise_array.append(0)

    for i in range(dims_to_modify):
        noise = random.random()/noise_factor
        print("noise: " + str(noise))
        noise_array[i] = noise




    attempt_image = face_recognition.load_image_file(f"../faces/{attempt}.jpg")
    attempt_face_encoding = face_recognition.face_encodings(attempt_image)[0]

    for i in range(128):
        op = random.randint(0,1)
        print("op: " + str(op))
        if (op==0):
            attempt_face_encoding[i] = attempt_face_encoding[i] + noise
        else:
            attempt_face_encoding[i] = attempt_face_encoding[i] - noise

    print("dims modified: " + str(dims_to_modify))
    score = face_recognition.face_distance(saved_face_encodings, attempt_face_encoding)
    #print("saved: " + str(saved_face_encoding))
    #print("saved: " + str(attempt_face_encoding))
    print("score: " + str(score))

    
if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
