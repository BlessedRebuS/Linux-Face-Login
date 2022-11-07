### Per testare la funzionalità di PAM modificato <su test> ed inserire "test" come password


FROM debian:latest
RUN apt update -y \
&& apt install libpam0g-dev -y \
&& apt install build-essential -y
RUN apt install openssh-server -y \
&& service ssh start
WORKDIR /root
RUN useradd -ms /bin/bash  test
COPY src /root/src
RUN chmod +x /root/src/buildPam.sh && /root/src/buildPam.sh
RUN sed -i '1 i\auth sufficient mypam.so' /etc/pam.d/common-auth \
&& sed -i '2 i\account sufficient mypam.so' /etc/pam.d/common-auth \
&& sed -i '1 i\auth sufficient mypam.so' /etc/pam.d/login \
&& sed -i '2 i\account sufficient mypam.so' /etc/pam.d/login
EXPOSE 22
