HTML_HEADER='Content-type: text/html\n\n'

import cgi, cgitb; cgitb.enable()

def Main():
    print HTML_HEADER+'<html><body><b>Success in GET/POST Processing</b><p>'
    print 'Here are the fields and their values...<p>'
    form=cgi.FieldStorage()
    if len(form)>0:
        for key in form.keys():
            print 'Key: <b>%s</b>  Value: <b>%s</b><br>' % (key,form[key].value)
    else:
        print 'No fields<p>'
    print '<p>(Hit the BACK button)'
    print '</body></html>'

Main()
