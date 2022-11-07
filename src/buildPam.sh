#!/bin/bash

gcc -fPIC -fno-stack-protector -c src/mypam.c

ld -x --shared -o /lib/aarch64-linux-gnu/security/mypam.so mypam.o

rm mypam.o
