import datetime
import time

from p5 import P5
from color import Color
from button import Button

class P5Button(P5):

	def __init__(self):
		P5.__init__(self)
		self.noloop()

		self._butts = []

		self._colPressed = Color( 172, 168, 153, 200 )
		self._colHighlight = Color( 255, 255, 255, 255 )
		self._colDarkShadow = Color( 113, 111, 100, 255 )
		self._colShadow = Color( 172, 168, 153, 255 )
		self._colBackground = Color( 236, 233, 216, 0 )

		self._pressDownTime = -1
		self._buttonPressed = False


	def getButtonPressTime():
		now = datetime.datetime.now()
		nowTime = time.mktime( now.timetuple() )
		diff = nowTime - self._pressDownTime
		return diff


	def fireButton(self, actionCommand):
		pass


	def button_press(self, widget, event):
		P5.button_press(self, widget, event)

		#iterate through the buttons to see if you've pressed any down
		bp = False
		for i in range ( 0, len(self._butts) ):
			if (self._butts[i]._enabled):
				contains = self._butts[i].contains(event.x, event.y)
				self._butts[i]._pressed = contains
				if (contains):
					now = datetime.datetime.now()
					self._pressDownTime = time.mktime( now.timetuple() )
					bp = True

		self._buttonPressed = bp
		self.redraw()


	def button_release(self, widget, event):
		P5.button_release(self, widget, event)
		self._buttonPressed = False

		pressed = []
		#iterate through the buttons to see if you've released on any
		for i in range ( 0, len(self._butts) ):
			if (self._butts[i]._enabled):
				if (self._butts[i]._pressed):
					if (self._butts[i].contains(event.x, event.y)):
						pressed.append( self._butts[i] )

					if (self._butts[i]._toggle):
						self._butts[i]._pressed = not self._butts[i]._pressed
					else:
						self._butts[i]._pressed = False

		for i in range( 0, len(pressed) ):
			pressed[i].doPressed()

		self.redraw()


	def drawButton(self, ctx, butt):
		pass


	def drawButtonOld(self, ctx, butt):
		ctx.scale (1, 1)
		ctx.translate( butt._offX, butt._offY )
		
		#!enabled?
		#do stuff, return
		if (not butt._enabled):
			#if(butt.isImg()):
			#	ctx.set_source_surface(butt._img, 0, 0)
			#	ctx.paint()

			#self.fillShape( ctx, butt._poly, self._colPressed )
			#ctx.translate( -butt._offX, -butt._offY )
			return

		#set highlightColor
		#draw highlightShape
		ctx.translate( 1, 1 )
		#self.drawShape( ctx, butt._poly, self._colHighlight )
		ctx.translate( -1, -1 )

		#draw image
		if (butt.isImg()):
			ctx.set_source_surface(butt._img, 0, 0)
			ctx.paint()

		if (butt._pressed):
			self.fillShape( ctx, butt._poly, self._colPressed )

		#self.drawShape( ctx, butt._poly, self._colDarkShadow )

		#if not pressed, setColor buttonHighlightColor
		#if not pressed, draw HighlightShape
		if (not butt._pressed):
			ctx.translate( 1, 1 )
			#self.drawShape( ctx, butt._poly, self._colHighlight )
			ctx.translate( -1, -1 )

		ctx.translate( -butt._offX, -butt._offY )
