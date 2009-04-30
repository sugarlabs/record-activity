plugin_LTLIBRARIES = libgstvideorate.la libgstvalve.la

libgstvideorate_la_SOURCES = gstvideorate.c gstvideorate.h
libgstvideorate_la_CFLAGS = $(GST_CFLAGS) $(GST_AUDIO_CFLAGS)
libgstvideorate_la_LIBADD = $(GST_LIBS) $(GST_AUDIO_LIBS)
libgstvideorate_la_LDFLAGS = $(GST_PLUGIN_LDFLAGS)
libgstvideorate_la_LIBTOOLFLAGS = --tag=disable-static

libgstvalve_la_SOURCES = gstvalve.c gstvalve.h
libgstvalve_la_CFLAGS = $(GST_CFLAGS) $(GST_PLUGINS_BASE_CFLAGS) $(ERROR_CFLAGS)
libgstvalve_la_LIBADD = $(GST_LIBS_LIBS)
libgstvalve_la_LDFLAGS = $(GST_PLUGIN_LDFLAGS) $(GST_BASE_LIBS) $(GST_PLUGINS_BASE_LIBS)
libgstvalve_la_LIBTOOLFLAGS = --tag=disable-static

ARCH = $(shell arch | grep 64 >/dev/null && echo linux64 || echo linux32)

dist_xo: all
	rm -rf $(ARCH)
	mkdir $(ARCH)
	cp .libs/libgst*.so $(ARCH)/
