Apache-compatible Python Web Server
===================================

A version of Peter's PythonWebServer ("PWS") that behaves more like Apache.
   
The first priority is to make the PythonWebServer give a good error message if the user's script fails to begin its response with a content-type header, as described in a [StackOverflow posting][].  That posting is unanswered as of 2013-07-25. 
   [StackOverflow posting]: http://stackoverflow.com/questions/17635164/how-can-a-cgi-server-based-on-cgihttprequesthandler-require-that-a-script-start

references
----------
+ [Apache's rules for CGI][] say "The first thing you see written by your program should be a set of HTTP headers, including the Content-Type, followed by a blank line."

   [Apache's rules for CGI]: http://httpd.apache.org/docs/current/howto/cgi.html#writing

+ [RFC 3875 for the Common Gateway Interface](http://www.ietf.org/rfc/rfc3875)  section 6.3.1 (CGI Response, Content-Type): "If an entity body is returned, the script MUST supply a Content-Type field in the response."
+ [RFC 2616 for HTTP 1.1](http://tools.ietf.org/html/rfc2616#section-4) says that there should be a first line in an HTTP message, specifying that the message is a Response.  This standard is not enforced by Apache and therefore is similarly not enforced by this Apache-compatible Python Web Server.
+ The same [RFC 2616 for HTTP 1.1](http://tools.ietf.org/html/rfc2616#section-14.17) specifies the Content-Type header
+ [The Python docs](http://docs.python.org/2/library/cgi.html#cgi.parse_header) specify the use of the `email.header` package for parsing the MIME headers that are used in HTTP messages

behavior
--------
The Apache-compatible Python Web Server checks that the response starts with a content-type header, but Apache is actually more lax than [its own documentation][Apache's rules for CGI] suggests.  I think Apache will accept any line with a colon that is followed by a blank line.  Certainly Apache 2 accepts the following two "headers" that are invalid according the the RFCs cited above: 
```
:\n\n
```
```
junk : more junk\n\n
```

implementation
--------------
Creating an instance of Python's basic `HTTPServer` requires passing the constructor an `HTTPRequestHandler`.  Python supplies an almost-suitable handler, `CGIHTTPRequestHandler` (in module \Python27\lib\CGIHTTPServer.py).  When a client's request specifies a Python script to be executed, this handler's `run_cgi` method invokes the script and sends the output of that script to the client.  The Apache-compatible PWS needs an opportunity to inspect the output before it is sent to the client.  So this implementation derives a new class, `CGIHTTPRequestHandler_ApacheCompatible`, from the standard `CGIHTTPRequestHandler`, overriding the `run_cgi` method with one that implements the appropriate checks between the invoking the script and delivering the output to the client.

The implementation requires a simplification of the standard `CGIHTTPRequestHandler`:  the standard version uses Python's `subprocess` module on Windows systems, but forks a child process on \*nix system.  The fork affords no chance for the handler to inspect the output from the script (as I understand it).  So the implementation of `CGIHTTPRequestHandler_ApacheCompatible` uses the `subprocess` module on \*nix systems, just as it does for Windows.  (As of 2013-07-26, I have yet to test whether this actually *works* on a Mac.  Stay tuned.)
    
future
------
+ Debug the new behavior under Mac OS&nbsp;X 

+ Make PWS execute Python scripts from arbitrary directories.  Apache allows students to put their scripts and data files in any directory under their public_html.  Data files without explicit paths are sought in the script's directory.  PWS, by contrast, currently requires that all scripts reside in cgi-bin, and the default location for data files is in the directory that holds PythonWebServer.py.  I *think* the use of a single directory for executable scripts is a relic of security on centrally-managed web servers; it seems inconsistent with the model used at Stuy.
