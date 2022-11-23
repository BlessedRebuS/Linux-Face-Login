import RPi.GPIO as GPIO # Import Raspberry Pi GPIO library
import time
import cv2
import sys
import os

done = False

def button_callback(channel):

    cam = cv2.VideoCapture(0)
    user = sys.argv[1]
    print(user)
    # while loop
    while True:
        # intializing the frame, ret
        ret, frame = cam.read()
        # if statement
        #if not ret:
        #    print('failed to grab frame')
        #    break
        #path globale sennò docker si rompe
        img_name = f'/root/faces/{user}.jpg'
        cv2.imwrite(img_name, frame)
        time.sleep(1)
        global done
        done = True
        break

    # release the camera
    cam.release()

GPIO.setwarnings(False) # Ignore warning for now
GPIO.setmode(GPIO.BOARD) # Use physical pin numbering
GPIO.setup(10, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Set pin 10 to be an input pin and set initial value to be pulled low (off)
GPIO.add_event_detect(10,GPIO.RISING,callback=button_callback) # Setup event on pin 10 rising edge
#ciclo infinito per aspettare le callback, da modificare ENTRYPOINT
while done is False:
    time.sleep(1)
#message = input("Press enter to quit\n\n") # Run until someone presses enter
GPIO.cleanup() # Clean up

