#! /bin/sh

case "$1" in
    hi)
	shift
	[ $# -gt 0 ] \
	    && echo "Hi $@" \
	    || echo "Hi there"
	;;
    sleep)
	sleep 60
	;;
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
    ask)
	read -p "What's your name? " name
	echo "Hello $name"
	;;	
esac
