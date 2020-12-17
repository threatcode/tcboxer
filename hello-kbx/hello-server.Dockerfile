FROM debian:stable-slim
RUN apt-get update && apt-get install -y \
    python3 \
    python3-flask
ARG KBX_APP_VERSION=0.5
RUN mkdir /kaboxer ; echo $KBX_APP_VERSION > /kaboxer/version
COPY ./hello /usr/bin/hello
EXPOSE 8765
