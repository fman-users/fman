# Build on an old Fedora version on purpose, to maximize compatibility:
FROM fedora:30

ARG requirements

RUN dnf install -y python39

# Absolute minimum requirements for building a PyQt5 app with PyInstaller:
RUN dnf install -y libstdc++ freetype binutils

# fpm:
RUN dnf install -y ruby-devel gcc make rpm-build libffi-devel && \
    gem install --no-document fpm

WORKDIR /root/${app_name}

# Required for Python dependency pgi - needs to be installed before setting up
# the venv:
RUN dnf install -y gobject-introspection

# Set up virtual environment:
ADD *.txt /tmp/requirements/
RUN python3.9 -m venv .venv && \
    .venv/bin/python -m pip install -U pip && \
    .venv/bin/python -m pip install -r "/tmp/requirements/${requirements}"
RUN rm -rf /tmp/requirements/

ADD .bashrc /root

ADD gpg-agent.conf /root/.gnupg/gpg-agent.conf
RUN chmod -R 600 /root/.gnupg
ADD private-key.gpg public-key.gpg /tmp/
RUN dnf install -y gpg rpm-sign && \
    gpg -q --batch --yes --passphrase ${gpg_pass} --import /tmp/private-key.gpg /tmp/public-key.gpg && \
    rpm --import /tmp/public-key.gpg && \
    rm /tmp/private-key.gpg /tmp/public-key.gpg

ADD .rpmmacros /root

RUN dnf install -y createrepo_c

# The `release` build command calls git to check for uncommitted changes. So we
# need git:
RUN dnf install -y git

ENTRYPOINT ["/bin/bash"]