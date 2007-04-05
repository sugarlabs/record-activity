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
