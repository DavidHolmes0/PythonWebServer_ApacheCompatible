#! /usr/bin/python

import BaseHTTPServer
from CGIHTTPRequestHandler_ApacheCompatible import CGIHTTPRequestHandler_ApacheCompatible
import os

def main():
    # relocate to the directory that is the web root
    # This directory corresponds to
    #     ~/public_html
    # in the Apache setup.  For example, Windows user D's files are below
    #     C:\Users\D\Documents
    os.chdir( os.path.normpath( os.path.expanduser('~/Documents')))
    print '***** Web server base directory: '+os.getcwd()
    
    try:
        server = BaseHTTPServer.HTTPServer(('',9000),
                                           CGIHTTPRequestHandler_ApacheCompatible)
        print 'Started CGI Server...'
        server.serve_forever()
    except KeyboardInterrupt:
        print '^C received, shutting down...'
        server.socket.close()

if __name__ == '__main__':
    main()
