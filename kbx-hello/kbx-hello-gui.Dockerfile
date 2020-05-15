FROM debian:stable-slim
RUN apt-get update && apt-get install -y \
    gir1.2-gtk-3.0 \
    python3 \
    python3-gi
ARG KBX_APP_VERSION=0.5
RUN mkdir /kaboxer ; echo $KBX_APP_VERSION > /kaboxer/version
COPY ./kbx-hello /kbx-hello
