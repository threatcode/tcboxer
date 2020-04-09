FROM debian:stable-slim
RUN apt update
RUN apt install -y python3 python3-prompt-toolkit
ARG KBX_APP_VERSION=0.5
RUN mkdir /kaboxer ; echo $KBX_APP_VERSION > /kaboxer/version
COPY ./kbx-hello /kbx-hello
