from time import time_ns
import face_recognition
import cv2
import numpy as np
import sys
from datetime import datetime
import random
from skimage.util import random_noise

noise_factor = 30

def main(saved, attempt, noise_type):

    #load the user image and get the face encoding
    saved_image = face_recognition.load_image_file(f"../faces/{saved}.jpg")
    saved_face_encoding = face_recognition.face_encodings(saved_image)[0]
    saved_face_encodings = [saved_face_encoding]

    if (noise_type == "random"):
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
        #cv2.imwrite(f'/home/leonardobambini/secwork/noise_faces/{attempt}-random-{noise_factor}.jpg', img)

    elif (noise_type == "sp"):
        attempt_image = face_recognition.load_image_file(f"../faces/{attempt}.jpg")
        amount = 0.001
        noise_img = random_noise(attempt_image, mode='s&p', amount=amount)
        noise_img = (255*noise_img).astype(np.uint8)
        attempt_face_encoding = 0
        score = 0
        try:
            attempt_face_encoding = face_recognition.face_encodings(noise_img)[0]
            score = face_recognition.face_distance(saved_face_encodings, attempt_face_encoding)
        except:
            print("no face detected")

        noise_img = cv2.cvtColor(noise_img, cv2.COLOR_BGR2RGB)
        cv2.imwrite(f'/home/leonardobambini/secwork/noise_faces/{attempt}-sp-{amount}.jpg', noise_img)
        print("score: " + str(score))

    elif (noise_type == "gaussian"):
        attempt_image = face_recognition.load_image_file(f"../faces/{attempt}.jpg")
        mean = 0
        var = 0.001
        noise_img = random_noise(attempt_image, mode='gaussian', mean=mean, var=var)
        noise_img = (255*noise_img).astype(np.uint8)
        attempt_face_encoding = 0
        score = 0
        try:
            attempt_face_encoding = face_recognition.face_encodings(noise_img)[0]
            score = face_recognition.face_distance(saved_face_encodings, attempt_face_encoding)
        except:
            print("no face detected")

        noise_img = cv2.cvtColor(noise_img, cv2.COLOR_BGR2RGB)
        cv2.imwrite(f'/home/leonardobambini/secwork/noise_faces/{attempt}-gaussian-{mean}-{var}.jpg', noise_img)
        print("score: " + str(score))
    
if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
