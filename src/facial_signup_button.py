import RPi.GPIO as GPIO # Import Raspberry Pi GPIO library
import time
import cv2
import sys
import os
import time
import Adafruit_GPIO.SPI as SPI
import Adafruit_SSD1306
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
import subprocess

done = False

def draw(user):

    draw.rectangle((0,0,width,height), outline=0, fill=0)
    # Write two lines of text.
    name = f"Registrato utente: {user}"
    draw.text((x, top+8),name, font=font, fill=255)

    # Display image.
    disp.image(image)
    disp.display()
    time.sleep(.1)

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
        draw(user)
        time.sleep(1)
        global done
        done = True
        break

    # release the camera
    cam.release()


# Raspberry Pi pin configuration:
RST = None     # on the PiOLED this pin isnt used
# Note the following are only used with SPI:
DC = 23
SPI_PORT = 0
SPI_DEVICE = 0
    
# 128x32 display with hardware I2C:
disp = Adafruit_SSD1306.SSD1306_128_32(rst=RST)

disp.begin()

# Clear display.
disp.clear()
disp.display()

width = disp.width
height = disp.height
image = Image.new('1', (width, height))

# Get drawing object to draw on image.
draw = ImageDraw.Draw(image)

# Draw a black filled box to clear the image.
draw.rectangle((0,0,width,height), outline=0, fill=0)

# Draw some shapes.
# First define some constants to allow easy resizing of shapes.
padding = -2
top = padding
bottom = height-padding
# Move left to right keeping track of the current x position for drawing shapes.
x = 0

# Load default font.
font = ImageFont.load_default()
GPIO.setwarnings(False) # Ignore warning for now
GPIO.setmode(GPIO.BOARD) # Use physical pin numbering
GPIO.setup(10, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Set pin 10 to be an input pin and set initial value to be pulled low (off)
GPIO.add_event_detect(10,GPIO.RISING,callback=button_callback) # Setup event on pin 10 rising edge
#ciclo infinito per aspettare le callback, da modificare ENTRYPOINT
while done is False:
    time.sleep(1)
#message = input("Press enter to quit\n\n") # Run until someone presses enter
GPIO.cleanup() # Clean up


