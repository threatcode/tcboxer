FROM debian:stable-slim
RUN apt update
RUN apt install -y python3 python3-prompt-toolkit
COPY ./kbx-hello /kbx-hello
ENTRYPOINT ["/kbx-hello", "cli"]
