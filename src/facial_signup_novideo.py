import cv2
import sys
import curses

def main(user):
    print(user)

    s = curses.initscr()
    curses.curs_set(0)
    w = curses.newwin(2,2)
    w.nodelay(1)
    shot = False

    # intialize the webcam and pass a constant which is 0
    cam = cv2.VideoCapture(0)

    # title of the app
   # cv2.namedWindow('python webcam screenshot app')

    # while loop
    while True:
        # intializing the frame, ret
        ret, frame = cam.read()
        # if statement
        if not ret:
            print('failed to grab frame')
            break
        
        key = w.getch()
        if (key == 27): #esc
            break
        elif (key == 32):
            shot = True
            img_name = f'faces/{user}.jpg'
            cv2.imwrite(img_name, frame)
            break       
        
        curses.napms(100)

    del w
    curses.endwin()

    # release the camera
    cam.release()

    # stops the camera window
    #cam.destoryAllWindows()


if __name__ == "__main__":
    main(sys.argv[1])
