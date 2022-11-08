### Per testare la funzionalità di PAM usare <login> ed inserire l'utente test

FROM debian:latest
# ESSENTIALS
RUN apt update -y \
&& apt install libpam0g-dev -y \
&& apt install build-essential -y \
&& apt install python3 -y \
&& apt install libpam-python -y
# UTILS E DEBUG
# RUN apt install openssh-server -y \
# && apt install vim -y \ 
# && service ssh start
WORKDIR /root
RUN useradd -ms /bin/bash  test \
&& mkdir /lib/security
COPY src/pam_auth.py /lib/security
# TESTING
# RUN chmod +x /root/src/buildPam.sh && /root/src/buildPam.sh
RUN sed -i '1 i\auth   sufficient   pam_python.so pam_auth.py' /etc/pam.d/common-auth \
&& sed -i '2 i\account   sufficient   pam_python.so pam_auth.py' /etc/pam.d/common-auth \
&& sed -i '1 i\auth   sufficient   pam_python.so pam_auth.py' /etc/pam.d/login \
&& sed -i '2 i\account   sufficient   pam_python.so pam_auth.py' /etc/pam.d/login
EXPOSE 22
