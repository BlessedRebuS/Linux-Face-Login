### Per testare la funzionalità di PAM usare <login> ed inserire l'utente test

FROM debian:bookworm
# ESSENTIALS
RUN apt update -y \
&& apt install sudo -y \
<<<<<<< HEAD
&& apt install libpng-dev -y \
&& apt install libgl1 -y \
&& apt install libglib2.0-0 -y \
&& apt install libimage-png-libpng-perl -y \
&& apt install python3 -y \
&& apt install python3-pip -y
env SUDO_USER root
# SIMULARE DISPLAY
=======
&& apt install libpam0g-dev -y \
&& apt install build-essential -y \
&& apt install python3 -y \
&& apt install python3-pip -y \
&& apt install libpam-python -y \
&& apt install cmake -y \
&& apt install libpng-dev -y \
&& apt install libgl1 -y \
&& apt install libglib2.0-0 -y \
&& apt install libimage-png-libpng-perl -y
>>>>>>> 33be1f65455810d53aef2320319c6bc01e2a997d
# UTILS E DEBUG
# RUN apt install openssh-server -y \
# && apt install vim -y \ 
# && service ssh start
# COPIA CODICE E AGGIUNTA UTENTE
RUN pip install RPi.GPIO
RUN pip install opencv-python
WORKDIR /root
RUN useradd -ms /bin/bash test
COPY src src
COPY faces faces
RUN sed -i -e '$auser ALL=(root) NOPASSWD: /root/src/facial_signup_button.py' /etc/sudoers
# TESTING
# RUN chmod +x /root/src/buildPam.sh && /root/src/buildPam.sh
<<<<<<< HEAD
ENTRYPOINT [ "python3", "/root/src/facial_signup_button.py", "root"]
=======
RUN sed -i '1 i\auth   sufficient   pam_python.so facial_pam_auth.py' /etc/pam.d/common-auth \
&& sed -i '2 i\account   sufficient   pam_python.so facial_pam_auth.py' /etc/pam.d/common-auth \
&& sed -i '1 i\auth   sufficient   pam_python.so facial_pam_auth.py' /etc/pam.d/login \
&& sed -i '2 i\account   sufficient   pam_python.so facial_pam_auth.py' /etc/pam.d/login
RUN cp src/facial_pam_auth.py /lib/security
RUN pip install -r src/requirements.txt
EXPOSE 22
ENTRYPOINT [ "python3", "/root/src/facial_signup_button.py", "root"]
>>>>>>> 33be1f65455810d53aef2320319c6bc01e2a997d
