#! /usr/bin/python
HTML_HEADER='Content-type: text/html\n\n'

import cgi, cgitb; cgitb.enable()

def Main():
    print HTML_HEADER+'<html><body>'
    print 'Here are the fields and their values...<p>'
    form=cgi.FieldStorage()
    if len(form)>0:
        for key in form.keys():
            # referring to form[key].value would intermittently produce
            #      'list' object has no attribute 'value'
            # for key = 'C1', form = FieldStorage(None, None, [MiniFieldStorage('firs...'ON'), MiniFieldStorage('The-Button', 'Submit')]), ]
            print 'Key: <b>%s</b>  Value: <b>%s</b><br>' % \
                  (key, form.getfirst(key))
    else:
        print 'No fields'
    print '</p><p><b>Success in GET/POST Processing</b><br>'
    print '(Hit the BACK button)</p>'
    print '</body></html>'

Main()
