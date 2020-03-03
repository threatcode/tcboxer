FROM debian:stable-slim
RUN apt update
RUN apt install -y python3 python3-flask
COPY ./kbx-hello /kbx-hello
EXPOSE 8765
