FROM debian:stable-slim
RUN apt-get update && apt-get install -y \
    python3 \
    python3-prompt-toolkit
COPY ./hello /usr/bin/hello
RUN mkdir /kaboxer \
 && hello version > /kaboxer/version
