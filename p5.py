import gtk
from gtk import gdk
import gobject
import cairo
import math

class P5(gtk.DrawingArea):
	def __init__(self):
		super(P5, self).__init__()

		# gtk.Widget signals
		self.connect("expose_event", self.expose)
		self.connect("button_press_event", self.button_press)
		self.connect("button_release_event", self.button_release)
		self.connect("motion_notify_event", self.motion_notify)

		# ok, we have to listen to mouse events here too
		self.add_events(gdk.BUTTON_PRESS_MASK | gdk.BUTTON_RELEASE_MASK | gdk.POINTER_MOTION_MASK)
		#jedi says, this is useful, our very own d&d model
		#how one talks to the sugar taskframe, no one knows.
		self._dragging = False
		self._mouseX = 0
		self._mouseY = 0

		self._w = -1
		self._h = -1


		#ok, this calls an initial painting & setting of painterly variables
		#e.g. time for the clock widget
		#(but not through to redraw_canvas when called here first time)
		self._msecUpdate = 100
		self._looping = False
		self.noloop()


	def loop(self):
		if (self._looping):
			return
		else:
			self._looping = True
			# this is our maybe-threaded refresh (in millisecs)
			gobject.timeout_add( self._msecUpdate, self.update )	


	def noloop(self):
		self._looping = False
		self.redraw()


	def redraw(self):
		self.update()


	def expose(self, widget, event):
		ctx = widget.window.cairo_create()

		# set a clip region for the expose event
		ctx.rectangle(event.area.x, event.area.y, event.area.width, event.area.height)
		ctx.clip()

		rect = widget.allocation
		#self.draw(ctx, event.area.width, event.area.height)
		self.draw( ctx, rect.width, rect.height )


	def button_press(self, widget, event):
		self._mouseX = event.x
		self._mouseY = event.y
		self._dragging = True


	def button_release(self, widget, event):
		if self._dragging:
			self._dragging = False


	def motion_notify(self, widget, event):
		self._mouseX = event.x
		self._mouseY = event.y


	def draw(self, ctx, w, h):
		ctx.set_antialias( cairo.ANTIALIAS_NONE )
		ctx.set_line_width( 1 )
		ctx.identity_matrix( )
		if ((w != self._w) or (h != self._h)):
			self._w = w
			self._h = h
			self.doResize( )


	def doResize(self):
		pass


	#called from update
	def redraw_canvas(self):
		if self.window:
			alloc = self.get_allocation()
			#this is odd behavior, but once we add this widget to a parent (vbox)
			#it requires setting the q_d_a x,y to 0, 0
			#self.queue_draw_area(alloc.x, alloc.y, alloc.width, alloc.height)
			self.queue_draw_area(0, 0, alloc.width, alloc.height)
			self.window.process_updates(True)


	def update(self):
		#paint thread -- call redraw_canvas, which calls expose  
		self.redraw_canvas()
		if (self._looping):
			return True # keep running this event
		else:
			return False


	def drawShape( self, ctx, poly, col ):
		self.setColor( ctx, col )

		for i in range ( 0, len(poly._xs) ):
			ctx.line_to ( poly._xs[i], poly._ys[i] )
		ctx.close_path()
		ctx.set_line_width(1)
		ctx.stroke()


	def fillShape( self, ctx, poly, col ):
		self.setColor( ctx, col )
		for i in range ( 0, len(poly._xs) ):
			ctx.line_to (poly._xs[i], poly._ys[i])
		ctx.close_path()

		ctx.fill()


	def loadImage(self, name):
		image = cairo.ImageSurface.create_from_png( name )
		return image


	def background( self, ctx, col, w, h ):
		self.setColor( ctx, col )

		ctx.line_to(0, 0)
		ctx.line_to(w, 0)
		ctx.line_to(w, h)
		ctx.line_to(0, h)
		ctx.close_path()

		ctx.fill()


	def rect( self, ctx, x, y, w, h ):
		ctx.line_to(x, y)
		ctx.line_to(x+w, y)
		ctx.line_to(x+w, y+h)
		ctx.line_to(x, y+h)
		ctx.close_path()


	def setColor( self, ctx, col ):
		if (not col._opaque):
			ctx.set_source_rgba( col._r, col._g, col._b, col._a )
		else:
			ctx.set_source_rgb( col._r, col._g, col._b )


	def line( self, ctx, x1, y1, x2, y2 ):
		ctx.move_to (x1, y1)
		ctx.line_to (x2, y2)
		ctx.stroke()


	def point( self, ctx, x1, y1 ):
		self.line( ctx, x1, y1, x1+1, y1 )