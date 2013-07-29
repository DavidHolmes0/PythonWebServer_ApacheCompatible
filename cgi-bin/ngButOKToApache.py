#! /usr/bin/python

import cgitb; cgitb.enable()
print ':\n\n'\
      '<head></head> <body>'
print "No content type, but Apache displays this "\
      "as though content were of type plain text 16"
print '</body></head>'
