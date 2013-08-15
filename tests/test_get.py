#! /usr/bin/python
HTML_HEADER='Content-type: text/html\n\n'

import cgi, cgitb; cgitb.enable()

def Main():
    print HTML_HEADER+'<html><body>'
    print 'Here are the fields and their values...<p>'
    form=cgi.FieldStorage()
    if len(form)>0:
        for key in form.keys():
            print 'Key: <b>%s</b>  Value: <b>%s</b><br>' % (key,form[key].value)
    else:
        print 'No fields'
    print '</p><p><b>Success in GET/POST Processing</b><br>'
    print '(Hit the BACK button)</p>'
    print '</body></html>'

Main()
