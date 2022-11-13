#!/bin/bash
sudo docker stop PAM
sudo docker rm PAM
sudo docker rmi debian-pam:test