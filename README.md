# Facial-Recognition-PAM
Progetto di Sistemi Digitali per Ingegneria Informatica Magistrale Unibo.
Il progetto sviluppato per Raspberry si trova [qui](https://github.com/FlippaFloppa/Linux-Face-Login/tree/raspberry).
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

## Scelte Progettuali

### Perché Docker?
Grazie all'uso di Docker è possibile testare il sistema in modo "sicuro", ovvero non si va a modificare il comportamento di login di default di Linux. In più utilizzando una sola immagine Docker su una distribuzione prestabilita come Debian, è possibile distribuire la stessa versione di test. Sul registry sono presenti due release: una con architettura **[amd64](https://hub.docker.com/layers/blessedrebus/debian-pam/v1/images/sha256-7b49cc928e195c6dd9fe561525681e1a4c6ea2d3ed64a62b7389f0f9ff206891?context=explore)** e una con architettura **[aarch64](https://hub.docker.com/layers/blessedrebus/debian-pam/armv8/images/sha256-0d34e5de41e3b6b2e45a15a2941253d9605f87f1b46d0383439114677cd8ae26?context=explore)** per eseguire l'applicazione sia su sistemi Linux classici, sia su Raspberry Pi 3/4 ed Apple Silicon. Si può accedere alla webcam utilizzando la flag `--privileged` durante il run dell'immagine Docker. In alternativa è possibile specificare direttamente il device con `--device=/dev/videoX:/dev/video0`, sostituendo X al numero del device USB che identifica la webcam. Per avere il corretto funzionamento su Raspberry è consigliato esegurie con la flag "privileged" in modo da accedere a tutti i pin GPIO.

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


