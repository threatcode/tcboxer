#! /usr/bin/make -f

MDFILES=$(wildcard *.1.md)
MANPAGES=$(basename $(MDFILES))

all: $(MANPAGES)

%.1: %.1.md Makefile
	pandoc $< -f markdown-smart -s -t man > $@
