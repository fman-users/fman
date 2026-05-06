# Build on an old Ubuntu version on purpose, to maximize compatibility:
FROM fmanbuildsystem/ubuntu:16.04

ARG requirements

RUN apt-get update && \
    apt-get upgrade -y

RUN DEBIAN_FRONTEND=noninteractive apt-get install software-properties-common -y && \
    add-apt-repository ppa:deadsnakes/ppa -y && \
    apt-get update && \
    apt-get install python3.9 python3.9-dev python3.9-venv -y

# Add missing file libGL.so.1 for PyQt5.QtGui:
RUN apt-get install libgl1-mesa-glx -y

# fpm:
RUN apt-get install ruby ruby-dev build-essential -y && \
    gem install --no-document fpm

WORKDIR /root/${app_name}

# Required for Python dependency pgi:
RUN apt-get install gobject-introspection libgtk-3-0 -y

# Set up virtual environment:
ADD *.txt /tmp/requirements/
RUN python3.9 -m venv .venv && \
    .venv/bin/python -m pip install -U pip && \
    .venv/bin/python -m pip install -r "/tmp/requirements/${requirements}"
RUN rm -rf /tmp/requirements/

ADD .bashrc /root/.bashrc

# Requirements for our use of reprepro:
ADD gpg-agent.conf gpg.conf /root/.gnupg/
# Avoid GPG warning "unsafe permissions":
RUN chmod -R 600 /root/.gnupg/
RUN apt-get install reprepro gnupg-agent gnupg2 -y
ADD private-key.gpg public-key.gpg /tmp/
RUN gpg -q --batch --yes --passphrase ${gpg_pass} --import /tmp/private-key.gpg /tmp/public-key.gpg && \
    rm /tmp/private-key.gpg /tmp/public-key.gpg

ADD id_rsa /root/.ssh/id_rsa
RUN chmod 600 /root/.ssh/id_rsa
ADD id_rsa.pub /root/.ssh/id_rsa.pub
RUN apt-get install openssh-client -y && \
    ssh-keyscan -H github.com >> ~/.ssh/known_hosts && \
    ssh-keyscan -H fman.io >> ~/.ssh/known_hosts && \
    chmod 600 ~/.ssh/known_hosts

RUN apt-get install git -y && \
    git config --global user.email "michael@herrmann.io" && \
    git config --global user.name "Michael Herrmann"

RUN apt-get install locales -y && \
    locale-gen en_US.UTF-8