FROM debian:stable-slim
ARG KBX_APP_VERSION=1.0
RUN echo -n "Hello World " > /kbx-demo.txt
COPY pre-upgrade post-upgrade /kaboxer/scripts/
RUN mkdir /kaboxer ; echo $KBX_APP_VERSION > /kaboxer/version
