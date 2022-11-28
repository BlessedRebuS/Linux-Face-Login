#!/usr/bin/python3

import RPi.GPIO as GPIO
import time
RED_PIN = 27
GPIO.setmode(GPIO.BCM)
GPIO.setup(RED_PIN, GPIO.OUT)
GPIO.output(RED_PIN, GPIO.HIGH)
time.sleep(1)
GPIO.cleanup()