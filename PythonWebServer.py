#! /usr/bin/python

import BaseHTTPServer
from CGIHTTPRequestHandler_ApacheCompatible import CGIHTTPRequestHandler_ApacheCompatible
import sys,os

def main():
    # relocate to the directory holding this file
    path=sys.argv[0]
    pos=path.rfind('\\')
    if pos >= 0:
        curdir=path[:pos+1]
    else:
        curdir='.'
    os.chdir(curdir)
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
