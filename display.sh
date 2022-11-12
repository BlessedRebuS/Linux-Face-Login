#!/bin/bash
Xvfb :99 -screen 0 1000x1000x16 &
xrandr –query
sleep 5
nohup startxfce4 &