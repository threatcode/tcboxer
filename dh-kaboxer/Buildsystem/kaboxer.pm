# A debhelper build system class for handling Kaboxer based projects
#
# Copyright: © 2008 Joey Hess
#            © 2008-2009 Modestas Vainius
#            © 2020 Offensive Security
# License: GPL-2+

package Debian::Debhelper::Buildsystem::kaboxer;

use strict;
use warnings;
use Debian::Debhelper::Dh_Lib qw(%dh dpkg_architecture_value sourcepackage compat tmpdir install_dir);
use parent qw(Debian::Debhelper::Buildsystem);

sub DESCRIPTION {
	"Kaboxer"
}

sub new {
    my $class = shift;
    my $this = $class->SUPER::new(@_);
    #$this->prefer_out_of_source_building();
    $this->{build_artifact_prefix}='kaboxerbuild-';
    return $this;
}

sub check_auto_buildable {
    my $this=shift;
    my ($step)=@_;

    return 0 unless glob ("kaboxer.yaml *.kaboxer.yaml");

    return 1 if $step eq "build";
    return 1 if $step eq "install";
    return 1 if $step eq "clean";
    return $this->SUPER::check_auto_buildable(@_);
}

sub build {
    my $this=shift;

    $this->doit_in_sourcedir("kaboxer", "--verbose", "build", "--save", @_);
}

sub install {
    my $this=shift;
    my $destdir=shift;

    install_dir("$destdir/usr/share/kaboxer");
    $this->doit_in_sourcedir("kaboxer", "--verbose", "install", "--destdir", "$destdir", "--prefix", "/usr", "--tarball", @_);
}

sub clean {
    my $this=shift;

    $this->doit_in_sourcedir("kaboxer", "--verbose", "clean", @_);
}

1
