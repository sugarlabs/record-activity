#Copyright (c) 2007 Media Modifications Ltd.

#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:

#The above copyright notice and this permission notice shall be included in
#all copies or substantial portions of the Software.

#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#THE SOFTWARE.

from p5 import P5

class P5Button(P5):

	def __init__(self):
		P5.__init__(self)
		self.noloop()
		self._butts = []
		self._buttonPressed = False


	def button_press(self, widget, event):
		P5.button_press(self, widget, event)

		#iterate through the buttons to see if you've pressed any down
		bp = False
		for i in range ( 0, len(self._butts) ):
			if (self._butts[i]._enabled):
				contains = self._butts[i].contains(event.x, event.y)
				self._butts[i]._pressed = contains
				if (contains):
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


class Polygon:

	def __init__( self, xs, ys ):
		self.setPoints( xs, ys )


	def setPoints( self, xs, ys ):
		self._xs = xs
		self._ys = ys

		self._boundingX = self._xs[0]
		self._boundingY = self._ys[0]
		self._boundingW = self._xs[0]
		self._boundingH = self._ys[0]

		for i in range ( 1, len(self._xs) ):
			if (self._xs[i] > self._boundingW):
				self._boundingW = self._xs[i]
			if (self._ys[i] > self._boundingH):
				self._boundingH = self._ys[i]
			if (self._xs[i] < self._boundingX):
				self._boundingX = self._xs[i]
			if (self._ys[i] < self._boundingY):
				self._boundingY = self._ys[i]


	def contains( self, mx, my ):
		if (not self.bbox_contains(mx, my)):
			return False

		#insert simple path tracing check on the polygon here

		return True


	def bbox_contains( self, mx, my ):
		if ( not((mx>=self._boundingX) and (my>=self._boundingY) and (mx<self._boundingW) and (my<self._boundingH)) ):
			return False
		else:
			return True


class Button:

	def __init__(self, poly, offX, offY):
		self._poly = poly
		self._offX = offX
		self._offY = offY

		self._enabled = True
		self._pressed = False
		self._toggle = False

		self._listeners = []

		self._actionCommand = None

		self._img = None


	def setOffsets(self, offs):
		self._offX = offs[0]
		self._offY = offs[1]


	def addActionListener(self, listen):
		self._listeners.append(listen)


	def removeActionListener(self, listen):
		try:
			self._listeners.remove(listen)
		except ValueError:
			pass


	def setActionCommand(self, command):
		self._actionCommand = command


	def getActionCommand(self):
		return self._actionCommand


	def setImage(self, img):
		self._img = img


	def contains( self, mx, my ):
		x = mx - self._offX
		y = my - self._offY

		contains = self._poly.contains( x, y )
		return contains


	def doPressed( self ):
		for i in range ( 0, len(self._listeners) ):
			self._listeners[i].fireButton( self._actionCommand )


	def isImg( self ):
		return self._img != None