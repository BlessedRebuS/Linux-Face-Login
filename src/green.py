#!/usr/bin/python3

import RPi.GPIO as GPIO
import time
GREEN_PIN = 17
GPIO.setmode(GPIO.BCM)
GPIO.setup(GREEN_PIN, GPIO.OUT)
GPIO.output(GREEN_PIN, GPIO.HIGH)
time.sleep(1)
GPIO.cleanup()