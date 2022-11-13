#!/bin/bash

docker build . -t debian-pam:test

docker run --privileged -p 1234:22 -it -d --name PAM debian-pam:test

docker exec -it PAM /bin/bash
