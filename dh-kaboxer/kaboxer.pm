# perl_dbi.pm - debhelper addon for running dh_kaboxer
#
# Copyright 2010, Ansgar Burchardt <ansgar@debian.org>
#
# This program is free software, you can redistribute it and/or modify it
# under the same terms as Perl itself.

use warnings;
use strict;

use Debian::Debhelper::Dh_Lib;

insert_after("dh_install", "dh_kaboxer");

1;
