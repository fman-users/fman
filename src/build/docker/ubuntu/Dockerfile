# Build on an old Ubuntu version on purpose, to maximize compatibility:
FROM ubuntu:22.04

ARG requirements

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get upgrade -y

# uv manages Python (3.14) and the virtual environment below:
COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /uvx /bin/

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
# Install with pip rather than `uv pip`: the fbs dependency is a direct URL
# without an archive extension, which uv rejects but pip resolves via the
# response's Content-Disposition header.
RUN uv venv --python 3.14 --seed venv && \
    venv/bin/python -m pip install -r "/tmp/requirements/${requirements}"
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
