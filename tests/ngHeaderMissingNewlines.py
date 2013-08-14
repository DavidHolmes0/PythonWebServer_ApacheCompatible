#! /usr/bin/python

import cgitb; cgitb.enable()
print 'there should be a Content-type header here: text/html\n'\
      '<head></head> <body>'
print "Yo!"
print '</body></head>'
