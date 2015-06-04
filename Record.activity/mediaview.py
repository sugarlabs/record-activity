import os
from gettext import gettext as _

import gobject
import gtk
from gtk import gdk

import constants
import utils

COLOR_BLACK = gdk.color_parse('#000000')
COLOR_WHITE = gdk.color_parse('#ffffff')
COLOR_GREY = gdk.color_parse('#808080')

class XoIcon(gtk.Image):
    def __init__(self):
        super(XoIcon, self).__init__()

    def set_colors(self, stroke, fill):
        pixbuf = utils.load_colored_svg('xo-guy.svg', stroke, fill)
        self.set_from_pixbuf(pixbuf)


class InfoView(gtk.EventBox):
    """
    A metadata view/edit widget, that presents a primary view area in the top
    right and a secondary view area in the bottom left.
    """
    __gsignals__ = {
        'primary-allocated': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
        'secondary-allocated': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
        'tags-changed': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_OBJECT,)),
    }

    def __init__(self):
        super(InfoView, self).__init__()
        self.modify_bg(gtk.STATE_NORMAL, COLOR_GREY)

        self.connect('size-allocate', self._size_allocate)

        self._outer_vbox = gtk.VBox(spacing=7)
        self.add(self._outer_vbox)

        hbox = gtk.HBox()
        self._outer_vbox.pack_start(hbox, expand=True, fill=True)

        inner_vbox = gtk.VBox(spacing=5)
        hbox.pack_start(inner_vbox, expand=True, fill=True, padding=6)

        author_hbox = gtk.HBox()
        inner_vbox.pack_start(author_hbox, expand=False)

        label = gtk.Label()
        label.set_markup('<b>' + _('Author:') + '</b>')
        author_hbox.pack_start(label, expand=False)

        self._xo_icon = XoIcon()
        author_hbox.pack_start(self._xo_icon, expand=False)

        self._author_label = gtk.Label()
        author_hbox.pack_start(self._author_label, expand=False)

        self._date_label = gtk.Label()
        self._date_label.set_line_wrap(True)
        alignment = gtk.Alignment(0.0, 0.5, 0.0, 0.0)
        alignment.add(self._date_label)
        inner_vbox.pack_start(alignment, expand=False)

        label = gtk.Label()
        label.set_markup('<b>' + _('Tags:') + '</b>')
        alignment = gtk.Alignment(0.0, 0.5, 0.0, 0.0)
        alignment.add(label)
        inner_vbox.pack_start(alignment, expand=False)

        textview = gtk.TextView()
        self._tags_buffer = textview.get_buffer()
        self._tags_buffer.connect('changed', self._tags_changed)
        inner_vbox.pack_start(textview, expand=True, fill=True)

        # the main viewing widget will be painted exactly on top of this one
        alignment = gtk.Alignment(1.0, 0.0, 0.0, 0.0)
        self._view_bg = gtk.EventBox()
        self._view_bg.modify_bg(gtk.STATE_NORMAL, COLOR_BLACK)
        alignment.add(self._view_bg)
        hbox.pack_start(alignment, expand=False)

        # the secondary viewing widget will be painted exactly on top of this one
        alignment = gtk.Alignment(0.0, 1.0, 0.0, 0.0)
        self._live_bg = gtk.EventBox()
        self._live_bg.modify_bg(gtk.STATE_NORMAL, COLOR_BLACK)
        alignment.add(self._live_bg)
        self._outer_vbox.pack_start(alignment, expand=False)

    def fit_to_allocation(self, allocation):
        # main viewing area: 50% of each dimension
        scale = 0.5
        w = int(allocation.width * scale)
        h = int(allocation.height * scale)
        self._view_bg.set_size_request(w, h)

        # live area: 1/4 of each dimension
        scale = 0.25
        w = int(allocation.width * scale)
        h = int(allocation.height * scale)
        self._live_bg.set_size_request(w, h)

    def show(self):
        self.show_all()

    def hide(self):
        self.hide_all()

    def set_author(self, name, stroke, fill):
        self._xo_icon.set_colors(stroke, fill)
        self._author_label.set_text(name)

    def set_date(self, date):
        self._date_label.set_markup('<b>' + _('Date:') + '</b> ' + date)

    def set_tags(self, tags):
        self._tags_buffer.set_text(tags)

    def _size_allocate(self, widget, allocation):
        self.emit('primary-allocated', self._view_bg.allocation)
        self.emit('secondary-allocated', self._live_bg.allocation)

    def _tags_changed(self, widget):
        self.emit('tags-changed', widget)

class VideoBox(gtk.EventBox):
    """
    A widget with its own window for rendering a gstreamer video sink onto.
    """
    def __init__(self):
        super(VideoBox, self).__init__()
        self.unset_flags(gtk.DOUBLE_BUFFERED)
        self.set_flags(gtk.APP_PAINTABLE)
        self._sink = None
        self._xid = None
        self.connect('realize', self._realize)

    def _realize(self, widget):
        self._xid = self.window.xid

    def do_expose_event(self):
        if self._sink:
            self._sink.expose()
            return False
        else:
            return True

    # can be called from gstreamer thread, must not do any GTK+ stuff
    def set_sink(self, sink):
        self._sink = sink
        sink.set_xwindow_id(self._xid)

class FullscreenButton(gtk.EventBox):
    def __init__(self):
        super(FullscreenButton, self).__init__()

        path = os.path.join(constants.GFX_PATH, 'max-reduce.svg')
        self._enlarge_pixbuf = gdk.pixbuf_new_from_file(path)
        self.width = self._enlarge_pixbuf.get_width()
        self.height = self._enlarge_pixbuf.get_height()

        path = os.path.join(constants.GFX_PATH, 'max-enlarge.svg')
        self._reduce_pixbuf = gdk.pixbuf_new_from_file_at_size(path, self.width, self.height)

        self._image = gtk.Image()
        self.set_enlarge()
        self._image.show()
        self.add(self._image)

    def set_enlarge(self):
        self._image.set_from_pixbuf(self._enlarge_pixbuf)

    def set_reduce(self):
        self._image.set_from_pixbuf(self._reduce_pixbuf)


class InfoButton(gtk.EventBox):
    def __init__(self):
        super(InfoButton, self).__init__()

        path = os.path.join(constants.GFX_PATH, 'corner-info.svg')
        pixbuf = gdk.pixbuf_new_from_file(path)
        self.width = pixbuf.get_width()
        self.height = pixbuf.get_height()

        self._image = gtk.image_new_from_pixbuf(pixbuf)
        self._image.show()
        self.add(self._image)


class ImageBox(gtk.EventBox):
    def __init__(self):
        super(ImageBox, self).__init__()
        self._pixbuf = None
        self._image = gtk.Image()
        self.add(self._image)

    def show(self):
        self._image.show()
        super(ImageBox, self).show()

    def hide(self):
        self._image.hide()
        super(ImageBox, self).hide()

    def clear(self):
        self._image.clear()
        self._pixbuf = None

    def set_pixbuf(self, pixbuf):
        self._pixbuf = pixbuf

    def set_size(self, width, height):
        if self._pixbuf:
            if width == self._pixbuf.get_width() and height == self._pixbuf.get_height():
                pixbuf = self._pixbuf
            else:
                pixbuf = self._pixbuf.scale_simple(width, height, gdk.INTERP_BILINEAR)

            self._image.set_from_pixbuf(pixbuf)

        self._image.set_size_request(width, height)
        self.set_size_request(width, height)

class MediaView(gtk.EventBox):
    """
    A widget to show the main record UI with a video feed, but with some
    extra features: possibility to show images, information UI about media,
    etc.

    It is made complicated because under the UI design, some widgets need
    to be placed on top of others. In GTK+, this is not trivial. We achieve
    this here by relying on the fact that GDK+ specifically allows us to
    raise specific windows, and by packing all our Z-order-sensitive widgets
    into EventBoxes (which have their own windows).
    """
    __gtype_name__ = "MediaView"
    __gsignals__ = {
        'media-clicked': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
        'pip-clicked': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
        'full-clicked': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
        'info-clicked': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
        'tags-changed': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_OBJECT,)),
    }

    MODE_LIVE = 0
    MODE_PHOTO = 1
    MODE_VIDEO = 2
    MODE_STILL = 3
    MODE_INFO_PHOTO = 4
    MODE_INFO_VIDEO = 5

    @staticmethod
    def _raise_widget(widget):
        widget.show()
        widget.realize()
        widget.window.raise_()

    def __init__(self):
        self._mode = None
        self._allocation = None
        self._hide_controls_timer = None

        super(MediaView, self).__init__()
        self.connect('size-allocate', self._size_allocate)
        self.connect('motion-notify-event', self._motion_notify)
        self.set_events(gdk.POINTER_MOTION_MASK | gdk.POINTER_MOTION_HINT_MASK)

        self._fixed = gtk.Fixed()
        self.add(self._fixed)

        self._info_view = InfoView()
        self._info_view.connect('primary-allocated', self._info_view_primary_allocated)
        self._info_view.connect('secondary-allocated', self._info_view_secondary_allocated)
        self._info_view.connect('tags-changed', self._info_view_tags_changed)
        self._fixed.put(self._info_view, 0, 0)

        self._image_box = ImageBox()
        self._image_box.connect('button-release-event', self._image_clicked)
        self._fixed.put(self._image_box, 0, 0)

        self._video = VideoBox()
        self._video.connect('button-release-event', self._video_clicked)
        self._fixed.put(self._video, 0, 0)

        self._video2 = VideoBox()
        self._video2.connect('button-release-event', self._video2_clicked)
        self._fixed.put(self._video2, 0, 0)

        self._info_button = InfoButton()
        self._info_button.connect('button-release-event', self._info_clicked)
        self._fixed.put(self._info_button, 0, 0)

        self._full_button = FullscreenButton()
        self._full_button.connect('button-release-event', self._full_clicked)
        self._fixed.put(self._full_button, 0, 0)

        self._switch_mode(MediaView.MODE_LIVE)

    def _size_allocate(self, widget, allocation):
        # First check if we've already processed an allocation of this size.
        # This is necessary because the operations we do in response to the
        # size allocation cause another size allocation to happen.
        if self._allocation == allocation:
            return

        self._allocation = allocation
        self._place_widgets()

    def _motion_notify(self, widget, event):
        if self._hide_controls_timer:
            # remove timer, it will be reprogrammed right after
            gobject.source_remove(self._hide_controls_timer)
        else:
            self._show_controls()

        self._hide_controls_timer = gobject.timeout_add(2000, self._hide_controls)

    def _show_controls(self):
        if self._mode in (MediaView.MODE_LIVE, MediaView.MODE_VIDEO, MediaView.MODE_PHOTO, MediaView.MODE_STILL):
            self._raise_widget(self._full_button)

        if self._mode in (MediaView.MODE_VIDEO, MediaView.MODE_PHOTO):
            self._raise_widget(self._info_button)

        if self._mode in (MediaView.MODE_VIDEO, MediaView.MODE_PHOTO):
            self._raise_widget(self._video)

    def _hide_controls(self):
        if self._hide_controls_timer:
            gobject.source_remove(self._hide_controls_timer)
            self._hide_controls_timer = None

        self._full_button.hide()
        if self._mode not in (MediaView.MODE_INFO_PHOTO, MediaView.MODE_INFO_VIDEO):
            self._info_button.hide()

        if self._mode in (MediaView.MODE_VIDEO, MediaView.MODE_PHOTO):
            self._video.hide()

        return False

    def _place_widgets(self):
        allocation = self._allocation

        self._image_box.hide()
        self._video.hide()
        self._video2.hide()
        self._info_view.hide()
        self._info_button.hide()

        border = 5
        full_button_x = allocation.width - border - self._full_button.width
        full_button_y = border
        self._fixed.move(self._full_button, full_button_x, full_button_y)

        info_x = allocation.width - self._info_button.width
        info_y = allocation.height - self._info_button.height
        self._fixed.move(self._info_button, info_x, info_y)

        if self._mode == MediaView.MODE_LIVE:
            self._fixed.move(self._video, 0, 0)
            self._video.set_size_request(allocation.width, allocation.height)
            self._video.show()
            self._image_box.clear()
        elif self._mode == MediaView.MODE_VIDEO:
            self._fixed.move(self._video2, 0, 0)
            self._video2.set_size_request(allocation.width, allocation.height)
            self._video2.show()
            self._image_box.clear()

            vid_h = allocation.height / 6
            vid_w = allocation.width / 6
            self._video.set_size_request(vid_w, vid_h)

            border = 20
            vid_x = border
            vid_y = self.allocation.height - border - vid_h
            self._fixed.move(self._video, vid_x, vid_y)
        elif self._mode == MediaView.MODE_PHOTO:
            self._fixed.move(self._image_box, 0, 0)
            self._image_box.set_size(allocation.width, allocation.height)
            self._image_box.show()

            vid_h = allocation.height / 6
            vid_w = allocation.width / 6
            self._video.set_size_request(vid_w, vid_h)

            border = 20
            vid_x = border
            vid_y = self.allocation.height - border - vid_h
            self._fixed.move(self._video, vid_x, vid_y)
        elif self._mode == MediaView.MODE_STILL:
            self._fixed.move(self._image_box, 0, 0)
            self._image_box.set_size(allocation.width, allocation.height)
            self._image_box.show()
        elif self._mode in (MediaView.MODE_INFO_PHOTO, MediaView.MODE_INFO_VIDEO):
            self._full_button.hide()
            self._info_view.set_size_request(allocation.width, allocation.height)
            self._info_view.fit_to_allocation(allocation)
            self._info_view.show()
            self._raise_widget(self._info_button)

    def _info_view_primary_allocated(self, widget, allocation):
        if self._mode == MediaView.MODE_INFO_PHOTO:
            self._fixed.move(self._image_box, allocation.x, allocation.y)
            self._image_box.set_size(allocation.width, allocation.height)
            self._raise_widget(self._image_box)
        elif self._mode == MediaView.MODE_INFO_VIDEO:
            self._fixed.move(self._video2, allocation.x, allocation.y)
            self._video2.set_size_request(allocation.width, allocation.height)
            self._raise_widget(self._video2)

    def _info_view_secondary_allocated(self, widget, allocation):
        if self._mode in (MediaView.MODE_INFO_PHOTO, MediaView.MODE_INFO_VIDEO):
            self._fixed.move(self._video, allocation.x, allocation.y)
            self._video.set_size_request(allocation.width, allocation.height)
            self._raise_widget(self._video)

    def _info_view_tags_changed(self, widget, tbuffer):
        self.emit('tags-changed', tbuffer)

    def _switch_mode(self, new_mode):
        if self._mode == MediaView.MODE_LIVE and new_mode == MediaView.MODE_LIVE:
            return
        self._mode = new_mode

        if self._hide_controls_timer:
            gobject.source_remove(self._hide_controls_timer)
            self._hide_controls_timer = None

        if self._allocation:
            self._place_widgets()

    def _image_clicked(self, widget, event):
        self.emit('media-clicked')

    def _video_clicked(self, widget, event):
        if self._mode != MediaView.MODE_LIVE:
            self.emit('pip-clicked')

    def _video2_clicked(self, widget, event):
        self.emit('media-clicked')

    def _full_clicked(self, widget, event):
        self.emit('full-clicked')

    def _info_clicked(self, widget, event):
        self.emit('info-clicked')

    def _show_info(self, mode, author, stroke, fill, date, tags):
        self._info_view.set_author(author, stroke, fill)
        self._info_view.set_date(date)
        self._info_view.set_tags(tags)
        self._switch_mode(mode)

    def show_info_photo(self, author, stroke, fill, date, tags):
        self._show_info(MediaView.MODE_INFO_PHOTO, author, stroke, fill, date, tags)

    def show_info_video(self, author, stroke, fill, date, tags):
        self._show_info(MediaView.MODE_INFO_VIDEO, author, stroke, fill, date, tags)

    def set_fullscreen(self, fullscreen):
        if self._hide_controls_timer:
            gobject.source_remove(self._hide_controls_timer)
            self._hide_controls_timer = None

        if fullscreen:
            self._full_button.set_reduce()
        else:
            self._full_button.set_enlarge()

    def realize_video(self):
        self._video.realize()
        self._video2.realize()

    # can be called from gstreamer thread, must not do any GTK+ stuff
    def set_video_sink(self, sink):
        self._video.set_sink(sink)

    # can be called from gstreamer thread, must not do any GTK+ stuff
    def set_video2_sink(self, sink):
        self._video2.set_sink(sink)

    def show_still(self, pixbuf):
        # don't modify the original...
        pixbuf = pixbuf.copy()
        pixbuf.saturate_and_pixelate(pixbuf, 0, 0)
        self._image_box.set_pixbuf(pixbuf)
        self._switch_mode(MediaView.MODE_STILL)

    def show_photo(self, path):
        if path:
            pixbuf = gdk.pixbuf_new_from_file(path)
            self._image_box.set_pixbuf(pixbuf)
        self._switch_mode(MediaView.MODE_PHOTO)

    def show_video(self):
        self._switch_mode(MediaView.MODE_VIDEO)

    def show_live(self):
        self._switch_mode(MediaView.MODE_LIVE)

    def show(self):
        self._fixed.show()
        super(MediaView, self).show()

    def hide(self):
        self._fixed.hide()
        super(MediaView, self).hide()

