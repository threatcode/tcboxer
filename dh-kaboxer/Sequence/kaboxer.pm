use warnings;
use strict;

use Debian::Debhelper::Dh_Lib;

insert_after("dh_install", "dh_kaboxer");

1;