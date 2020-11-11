FROM python:3.8.1

ARG UID=1000

RUN useradd -s /usr/local/bin/backend.py -m -u $UID arista

RUN usermod -aG root arista

RUN apt update

RUN apt install -y vim sudo screen

RUN pip install ruamel.yaml rcvpapi cvprac pyaml tornado

RUN mkdir /var/run/sshd

RUN echo 'arista ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

COPY backend.py /usr/local/bin

RUN chmod +x /usr/local/bin/backend.py

COPY ConfigureTopology.py /usr/local/bin

RUN chmod +x /usr/local/bin/ConfigureTopology.py

RUN chown -R arista:arista .

EXPOSE 80

USER arista

ENTRYPOINT ["python3", "/usr/bin/backend.py"]
