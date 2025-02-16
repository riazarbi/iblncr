FROM ghcr.io/riazarbi/ib-headless:10.30.1t

USER root

RUN apt-get update \
 && apt-get upgrade -y \
 && apt-get install -y \
    python-is-python3 \
    pipx \
 && apt-get autoclean \
 && apt-get autoremove \
 && rm -rf /var/lib/apt/lists/* \
 && pipx install poetry

USER broker

#RUN python -m pipx ensurepath

ENTRYPOINT ["/bin/bash"]
