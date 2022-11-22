### Per testare la funzionalità di PAM usare <login> ed inserire l'utente test

FROM debian:bookworm
# ESSENTIALS
RUN apt update -y \
&& apt install sudo -y \
&& apt install libpng-dev -y \
&& apt install libgl1 -y \
&& apt install libglib2.0-0 -y \
&& apt install libimage-png-libpng-perl -y \
&& apt install python3 -y \
&& apt install python3-pip -y \
&& apt install build-essential -y \
&& apt install python3 -y \
&& apt install python3-pip -y \
&& apt install cmake -y \
&& apt install libpng-dev -y \
&& apt install libgl1 -y \
&& apt install libglib2.0-0 -y \
&& apt install libimage-png-libpng-perl -y
# UTILS E DEBUG
# RUN apt install openssh-server -y \
# && apt install vim -y \ 
# && service ssh start
# COPIA CODICE E AGGIUNTA UTENTE
RUN pip install RPi.GPIO
RUN pip install opencv-python
WORKDIR /root
RUN useradd -ms /bin/bash test
RUN useradd -ms /bin/bash obama
RUN usermod -aG sudo test
COPY src src
COPY faces faces
RUN sed -i -e '$auser ALL=(root) NOPASSWD: /root/src/facial_signup_button.py' /etc/sudoers
# TESTING
# RUN chmod +x /root/src/buildPam.sh && /root/src/buildPam.sh
RUN pip install -r src/requirements.txt
EXPOSE 22
ENTRYPOINT [ "tail", "-f", "/dev/null"]
