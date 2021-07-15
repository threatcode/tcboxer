#! /bin/sh

case "$1" in
    # kaboxer.yaml
    hi)
	shift
	[ $# -gt 0 ] \
	    && echo "Hi $@" \
	    || echo "Hi there"
	;;
    ask)
	read -p "What's your name? " name
	echo "Hello $name"
	;;
    sleep)
	sleep 60
	;;
    # kbx-demo.kaboxer.yaml
    demo)
	cat /kbx-demo.txt /kaboxer/version
	if [ -d /persist ] ; then
	    v=$(cat /kaboxer/version)
	    echo "Running version $v at $(date)" >> /persist/run_history
	fi
	;;
    history)
	cat /persist/run_history
	;;
esac
