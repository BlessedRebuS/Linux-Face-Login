# Facial-Recognition-PAM
Progetto di Sistemi Digitali per Ingegneria Informatica Magistrale Unibo.

## Requisiti

Per riuscire ad esegurie una demo del progetto è necessario disporre di una webcam USB, [installare docker](https://docs.docker.com/get-docker/) e avere i permessi di root sul proprio sistema.

## Installazione immagine pre-buildata dal [registry](https://hub.docker.com/u/blessedrebus)

Per scaricare l'immagine già fatta (x86_64 bit)

`docker pull blessedrebus/debian-pam:v1`

Ed avviare il container con 

`sudo docker run --privileged -p 1234:22 -it -d --name PAM blessedrebus/debian-pam:v1`

## Installazione automatica

`chmod +x install.sh && ./install.sh`

## Installazione manuale

Build Dockerfile

`sudo docker build . -t debian-pam:test`

Run docker image (**1234** host : **22** container)

`sudo docker run --privileged -p 1234:22 -it -d --name PAM debian-pam:test`

Entrare dentro il container con
 
`sudo docker exec -it PAM /bin/bash`
 
## Testing

1) Entrare da dentro il container nella cartella /root/src
2) Registrare il volto per l'utente "test" con il comando `python3 facial_signup_novideo.py test`. Posizionarsi davanti alla webcam e una volta stabili, premere la barra spaziatrice per salvare la foto.
3) Usare il comando `login` ed inserire come username "test". Se tutto è configurato correttamente il login avverrà tramite sblocco facciale. Se si proverà a loggare con l'utente "obama" si verrà rifiutati perché la faccia non corrisponde.

## Uninstalling

Per rimuovere il container e l'immagine

`chmod +x uninstaller.sh && ./uninstaller.sh`

## Abstract
Il progetto si basa su PAM (Pluggable Authentication Module), ovvero un sistema a moduli che è alla base dell’ autenticazione nei moderni sistemi Linux.
PAM è unito al processamento delle immagini ottenute da un flusso di dati registrati da una webcam.
Gli utenti si registreranno con la propria faccia allenando una rete neurale che andrà a costruire un modello da seguire per lo sblocco facciale. Una volta riconosciuti gli utenti tramite la webcam, il sistema si occuperà di effettuare il login.
Il progetto è sviluppato su Raspberry Pi tramite un modulo webcam, che si occuperà di trasferire le informazioni video al Raspberry, ma può essere esteso a una implementazione su webcam integrata in un qualunque sistema Linux. 
Per la nostra implementazione useremo un Raspberry Pi 3, come sistema operativo Debian GNU/Linux 11 (bullseye) ARM e un modulo webcam che si inserisce con un connettore al Raspberry tramite un cavo piatto flessibile.

---

### Documentazioni:
No password login
https://wiki.archlinux.org/title/LightDM#Enabling_interactive_passwordless_login

Webcam passtrough
https://stackoverflow.com/questions/44852484/access-webcam-using-opencv-python-in-docker

Fake display
1) https://askubuntu.com/questions/453109/add-fake-display-when-no-monitor-is-plugged-in

2) https://sick.codes/xfce-inside-docker-virtual-display-screen-inside-your-headless-container/

Raspberry Pinout
https://www.raspberrypi.com/documentation/computers/raspberry-pi.html

I2C Screen
https://www.raspberrypi-spy.co.uk/2018/04/i2c-oled-display-module-with-raspberry-pi/

### Documentazioni PAM:
https://github.com/devinaconley/pam-facial-auth

https://github.com/beatgammit/simple-pam

https://ben.akrin.com/2-factor-authentication-writing-pam-modules-for-ubuntu/

https://wiki.archlinux.org/title/PAM

### Documentazioni OpenCV
https://realpython.com/face-recognition-with-python/

https://pysource.com/2021/08/16/face-recognition-in-real-time-with-opencv-and-python/


