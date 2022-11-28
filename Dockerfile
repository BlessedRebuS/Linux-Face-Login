### Per testare la funzionalità di PAM usare <login> ed inserire l'utente test

FROM debian:bookworm
# ESSENTIALS
RUN apt update -y \
&& apt install libpam0g-dev -y \
&& apt install build-essential -y \
&& apt install libpam-python -y \
&& apt install libpng-dev -y \
&& apt install libgl1 -y \
&& apt install libglib2.0-0 -y \
&& apt install libimage-png-libpng-perl -y \
&& apt install python3 -y \
&& apt install python3-pip -y \
&& apt install cmake -y
# UTILS E DEBUG
# RUN apt install openssh-server -y \
# && apt install vim -y \ 
# && service ssh start
# COPIA CODICE E AGGIUNTA UTENTE
WORKDIR /root
RUN useradd -ms /bin/bash test
RUN useradd -ms /bin/bash obama
RUN usermod -aG sudo test
COPY src src
COPY faces faces
# TESTING
# RUN chmod +x /root/src/buildPam.sh && /root/src/buildPam.sh
RUN sed -i '1 i\auth   sufficient   pam_python.so facial_pam_auth.py' /etc/pam.d/common-auth \
&& sed -i '2 i\account   sufficient   pam_python.so facial_pam_auth.py' /etc/pam.d/common-auth \
&& sed -i '1 i\auth   sufficient   pam_python.so facial_pam_auth.py' /etc/pam.d/login \
&& sed -i '2 i\account   sufficient   pam_python.so facial_pam_auth.py' /etc/pam.d/login
RUN cp src/facial_pam_auth.py /lib/security
RUN pip install -r src/requirements.txt
EXPOSE 22
ENTRYPOINT [ "python3", "/root/src/stats.py"]
