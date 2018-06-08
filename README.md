What is this?
=============

Record is a photo camera, video camera, and audio recorder for the Sugar desktop.

How to use?
===========

Record is part of the Sugar desktop and is often included.  Please refer to;

* [How to Get Sugar on sugarlabs.org](https://sugarlabs.org/),
* [How to use Sugar](https://help.sugarlabs.org/),
* [Download Record using Browse](https://activities.sugarlabs.org/), search for `Record`, then download, and;
* [How to use Speak](https://help.sugarlabs.org/en/record.html).

How to upgrade?
===============

On Sugar desktop systems;
* use [My Settings](https://help.sugarlabs.org/en/my_settings.html), [Software Update](https://help.sugarlabs.org/en/my_settings.html#software-update), or;
* use Browse to open [activities.sugarlabs.org](https://activities.sugarlabs.org/), search for `Record`, then download.

How to integrate?
=================

Record depends on Python, [Sugar Toolkit for GTK+ 3](https://github.com/sugarlabs/sugar-toolkit-gtk3), and PyGObject bindings for GStreamer 1 and GTK+ 3.

Record is started by [Sugar](https://github.com/sugarlabs/sugar).

Record is [packaged by Fedora](https://src.fedoraproject.org/rpms/sugar-record).  On Fedora systems;

```
dnf install sugar-record
```

Record is no longer packaged by Debian and Ubuntu distributions.  When it was packaged, it was called `sugar-record-activity`.  On Debian and Ubuntu systems dependencies include `gir1.2-gstreamer-1.0`, and `gir1.2-telepathyglib-0.12`.

Branch master
=============

The `master` branch targets an environment with latest stable release
of [Sugar](https://github.com/sugarlabs/sugar), with dependencies on
latest stable release of Fedora and Debian distributions.

Branch not-gstreamer1
=====================

The `not-gstreamer1` branch is a backport of features and bug fixes
from the `master` branch for ongoing maintenance of the activity on
Fedora 18 systems which don't have well-functioning GStreamer 1
packages.
