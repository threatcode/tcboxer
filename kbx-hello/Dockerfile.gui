FROM debian:stable-slim
RUN apt update
RUN apt install -y python3 python3-gi gir1.2-gtk-3.0
COPY ./kbx-hello /kbx-hello

ENTRYPOINT ["/kbx-hello", "gui"]
