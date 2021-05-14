FROM debian:stable-slim
RUN apt-get update && apt-get install -y \
    gir1.2-gtk-3.0 \
    python3 \
    python3-flask \
    python3-gi \
    python3-prompt-toolkit
COPY ./hello /usr/bin/hello
RUN mkdir /kaboxer \
 && hello version > /kaboxer/version
