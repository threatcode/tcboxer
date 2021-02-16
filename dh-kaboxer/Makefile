#! /usr/bin/make -f

MANPAGES=dh_kaboxer.1

all: $(MANPAGES)

%.1: %
	pod2man $^ $@

clean:
	rm -f $(MANPAGES)
