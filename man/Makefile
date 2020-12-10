#! /usr/bin/make -f

MDFILES=$(wildcard *.?.md)
MANPAGES=$(basename $(MDFILES))

all: $(MANPAGES)

%.1: %.1.md Makefile
	pandoc $< -f markdown-smart -s -t man > $@

%.5: %.5.md Makefile
	pandoc $< -f markdown-smart -s -t man > $@

clean:
	rm -f $(MANPAGES)
