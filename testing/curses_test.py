import curses
s = curses.initscr()
curses.curs_set(0)
w = curses.newwin(2,2)
w.nodelay(1)
shot = False

while True:
    key = w.getch()
    if (key == 27): #esc
        break
    elif (key == 32):
        shot = True
        break       
    #print("key: " + str(key))
    curses.napms(100)

del w
curses.endwin()
