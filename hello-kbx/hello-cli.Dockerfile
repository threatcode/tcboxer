FROM debian:stable-slim
RUN apt-get update && apt-get install -y \
    python3
ARG KBX_APP_VERSION=0.7
RUN mkdir /kaboxer ; echo $KBX_APP_VERSION > /kaboxer/version
COPY ./hello /usr/bin/hello
