PYVER=`python -c "import sys; print '%s.%s' % (sys.version_info[0], sys.version_info[1])"`
PYTHON=python$(PYVER)

GLIB_INCLUDES=`pkg-config --cflags glib-2.0`
GLIB_LIBS=`pkg-config --libs glib-2.0`

GTK_INCLUDES=`pkg-config --cflags gtk+-2.0`
GTK_LIBS=`pkg-config --libs gtk+-2.0`

PYGTK_INCLUDES=`pkg-config --cflags pygtk-2.0`
PYGTK_LIBS=`pkg-config --libs pygtk-2.0`

CAIRO_INCLUDES=`pkg-config --cflags cairo`
CAIRO_LIBS=`pkg-config --libs cairo`

PYCAIRO_INCLUDES=`pkg-config --cflags pycairo`
PYCAIRO_LIBS=`pkg-config --libs pycairo`

INCLUDES=-I. -I/usr/include/${PYTHON} ${GLIB_INCLUDES} ${PYGTK_INCLUDES} ${CAIRO_INCLUDES} ${PYCAIRO_INCLUDES} ${GTK_INCLUDES}
ARCHFLAGS=-m32 -march=i386 -mtune=generic 
OPTFLAGS=-O2 -g -pipe -Wall -Wp,-D_FORTIFY_SOURCE=2 -fexceptions -fstack-protector --param=ssp-buffer-size=4 -fasynchronous-unwind-tables
CFLAGS=-g -fPIC -DPIC
LDFLAGS=-shared -nostdlib -Wl,--export-dynamic -pthread 

all: build link

build: 
	gcc ${INCLUDES} ${ARCHFLAGS} ${OPTFLAGS} ${CFLAGS} -c _camera.c -o _camera.o

link:
	g++ ${LDFLAGS} _camera.o ${GLIB_LIBS} ${PYGTK_LIBS} ${CAIRO_LIBS} ${PYCAIRO_LIBS} ${GTK_LIBS} -Wl,-soname -Wl,_camera.so -o _camera.so

clean: 
	@find -name "*.o" -exec rm {} \;
	@find -name "*.so" -exec rm {} \;
