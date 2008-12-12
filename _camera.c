#include <Python.h>

#include "pycairo.h"
#include <glib.h>

#include <pygobject.h>

static PyTypeObject *_PyGObject_Type;
#define PyGObject_Type (*_PyGObject_Type)
Pycairo_CAPI_t *Pycairo_CAPI;
static PyTypeObject *_PyGdkPixbuf_Type;
#define PyGdkPixbuf_Type (*_PyGdkPixbuf_Type)

#include <cairo.h>
#include <gdk/gdkpixbuf.h>
#include <gdk/gdkpixmap.h>
#include <cairo-xlib.h>
#include <gdk/gdkcairo.h>

static cairo_surface_t *
_cairo_surface_from_pixbuf (GdkPixbuf *pixbuf)
{
/* Ripped from GooCanvas */
  gint width = gdk_pixbuf_get_width (pixbuf);
  gint height = gdk_pixbuf_get_height (pixbuf);
  guchar *gdk_pixels = gdk_pixbuf_get_pixels (pixbuf);
  int gdk_rowstride = gdk_pixbuf_get_rowstride (pixbuf);
  int n_channels = gdk_pixbuf_get_n_channels (pixbuf);
  guchar *cairo_pixels;
  cairo_format_t format;
  cairo_surface_t *surface;
  static const cairo_user_data_key_t key;
  int j;

  if (n_channels == 3)
    format = CAIRO_FORMAT_RGB24;
  else
    format = CAIRO_FORMAT_ARGB32;

  cairo_pixels = g_malloc (4 * width * height);
  surface = cairo_image_surface_create_for_data ((unsigned char *)cairo_pixels,
						 format,
						 width, height, 4 * width);
  cairo_surface_set_user_data (surface, &key,
			       cairo_pixels, (cairo_destroy_func_t)g_free);

  for (j = height; j; j--)
    {
      guchar *p = gdk_pixels;
      guchar *q = cairo_pixels;

      if (n_channels == 3)
	{
	  guchar *end = p + 3 * width;
	  
	  while (p < end)
	    {
#if G_BYTE_ORDER == G_LITTLE_ENDIAN
	      q[0] = p[2];
	      q[1] = p[1];
	      q[2] = p[0];
#else	  
	      q[1] = p[0];
	      q[2] = p[1];
	      q[3] = p[2];
#endif
	      p += 3;
	      q += 4;
	    }
	}
      else
	{
	  guchar *end = p + 4 * width;
	  guint t1,t2,t3;
	    
#define MULT(d,c,a,t) G_STMT_START { t = c * a; d = ((t >> 8) + t) >> 8; } G_STMT_END

	  while (p < end)
	    {
#if G_BYTE_ORDER == G_LITTLE_ENDIAN
	      MULT(q[0], p[2], p[3], t1);
	      MULT(q[1], p[1], p[3], t2);
	      MULT(q[2], p[0], p[3], t3);
	      q[3] = p[3];
#else	  
	      q[0] = p[3];
	      MULT(q[1], p[0], p[3], t1);
	      MULT(q[2], p[1], p[3], t2);
	      MULT(q[3], p[2], p[3], t3);
#endif
	      
	      p += 4;
	      q += 4;
	    }
	  
#undef MULT
	}

      gdk_pixels += gdk_rowstride;
      cairo_pixels += 4 * width;
    }

  return surface;
}

static PyObject*
_wrap_camera_cairo_surface_from_gdk_pixbuf(PyGObject *self, PyObject *args, PyObject *kwargs)
{
    static char *kwlist[] = { "pixbuf", NULL };
    PyGObject *child;
    cairo_surface_t *surface;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs,"O!:camera.cairo_surface_from_gdk_pixbuf", kwlist, &PyGdkPixbuf_Type, &child))
        return NULL;

    surface = _cairo_surface_from_pixbuf(GDK_PIXBUF (child->obj));
	if (surface == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "surface could not be converted");
        return NULL;
    }

    return PycairoSurface_FromSurface(surface, NULL);
}

static GdkPixbuf *
_pixbuf_from_cairo_surface (cairo_surface_t * sf)
{
    GdkPixmap * pixmap;
    GdkPixbuf * pixbuf = NULL;
    cairo_surface_type_t type;
    gint width = 0, height = 0, depth = 0;
    int format;
    cairo_t * cr;
    GdkColormap * cm;

    type = cairo_surface_get_type (sf);
    switch (type) {
        case CAIRO_SURFACE_TYPE_IMAGE:
            width = cairo_image_surface_get_width (sf);
            height = cairo_image_surface_get_height (sf);
            format = cairo_image_surface_get_format (sf);
            if (format == CAIRO_FORMAT_ARGB32)
                depth = 32;
            else if (format == CAIRO_FORMAT_RGB24)
                depth = 24;
            else if (format == CAIRO_FORMAT_A8)
                depth = 8;
            else if (format == CAIRO_FORMAT_A1)
                depth = 1;
            else if (format == CAIRO_FORMAT_RGB16_565)
                depth = 16;
            break;
        case CAIRO_SURFACE_TYPE_XLIB:
            width = cairo_xlib_surface_get_width (sf);
            height = cairo_xlib_surface_get_height (sf);
            depth = cairo_xlib_surface_get_depth (sf);
            break;
        default:
            break;
    }
    if (!depth)
        return NULL;

	pixmap = gdk_pixmap_new (NULL, width, height, depth);
    if (!pixmap)
        return NULL;

    cr = gdk_cairo_create (pixmap);
    if (!cr)
        goto release_pixmap;

    cairo_set_source_surface (cr, sf, 0, 0);
    cairo_paint (cr);
    cairo_destroy (cr);

    cm = gdk_colormap_get_system ();
    pixbuf = gdk_pixbuf_get_from_drawable (NULL, pixmap, cm, 0, 0, 0, 0, -1, -1);

release_pixmap:
    gdk_pixmap_unref (pixmap);

    return pixbuf;
}


static PyObject*
_wrap_camera_gdk_pixbuf_from_cairo_surface(PyGObject *self, PyObject *args, PyObject *kwargs)
{
    static char *kwlist[] = { "surface", NULL };
    PyGObject *child;
    GdkPixbuf * pixbuf;
    PyTypeObject *type = &PycairoSurface_Type;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs,"O!:camera.gdk_pixbuf_from_cairo_surface", kwlist, type, &child))
        return NULL;

    pixbuf = _pixbuf_from_cairo_surface((cairo_surface_t *)(child->obj));
	if (pixbuf == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "pixbuf could not be converted");
        return NULL;
    }

    return pygobject_new ((GObject *) pixbuf);
}

const PyMethodDef py_camera_functions[] = {
    { "cairo_surface_from_gdk_pixbuf", (PyCFunction)_wrap_camera_cairo_surface_from_gdk_pixbuf,
      METH_VARARGS|METH_KEYWORDS, NULL },
    { "gdk_pixbuf_from_cairo_surface", (PyCFunction)_wrap_camera_gdk_pixbuf_from_cairo_surface,
      METH_VARARGS|METH_KEYWORDS, NULL },
    { NULL, NULL, 0, NULL }
};


/* ----------- enums and flags ----------- */

void
py_sugar_add_constants(PyObject *module, const gchar *strip_prefix)
{
}

/* initialise stuff extension classes */
void
py_camera_register_classes(PyObject *d)
{
    PyObject *module;

    if ((module = PyImport_ImportModule("gobject")) != NULL) {
        _PyGObject_Type = (PyTypeObject *)PyObject_GetAttrString(module, "GObject");
        if (_PyGObject_Type == NULL) {
            PyErr_SetString(PyExc_ImportError,
                "cannot import name GObject from gobject");
            return ;
        }
        _PyGObject_Type = (PyTypeObject *)PyObject_GetAttrString(module, "GObject");
        if (_PyGObject_Type == NULL) {
            PyErr_SetString(PyExc_ImportError,
                "cannot import name GObject from gobject");
            return ;
        }
    } else {
        PyErr_SetString(PyExc_ImportError,
            "could not import gobject");
        return ;
    }
    if ((module = PyImport_ImportModule("gtk.gdk")) != NULL) {
        _PyGdkPixbuf_Type = (PyTypeObject *)PyObject_GetAttrString(module, "Pixbuf");
        if (_PyGdkPixbuf_Type == NULL) {
            PyErr_SetString(PyExc_ImportError,
                "cannot import name Pixbuf from gtk.gdk");
            return ;
        }
    } else {
        PyErr_SetString(PyExc_ImportError,
            "could not import gtk.gdk");
        return ;
    }

    Pycairo_IMPORT;
}

DL_EXPORT(void)
init_camera(void)
{
    PyObject *m, *d;

    Pycairo_IMPORT;

    m = Py_InitModule ("_camera", py_camera_functions);
    d = PyModule_GetDict (m);

    py_camera_register_classes (d);
    if (PyErr_Occurred ()) {
        Py_FatalError ("can't initialise module _camera");
    }
}
