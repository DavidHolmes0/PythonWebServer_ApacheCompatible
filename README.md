Apache-compatible Python Web Server
===================================

A version of Peter's PythonWebServer that behaves more like Apache.
   
The first priority is to make the PythonWebServer give a good error message if the user's script fails to begin its response with a content-type header, as described in a [StackOverflow posting][].  That posting is unanswered as of 2013-07-25. 
   [StackOverflow posting]: http://stackoverflow.com/questions/17635164/how-can-a-cgi-server-based-on-cgihttprequesthandler-require-that-a-script-start

## References
+ [Apache's rules for CGI][] say "The first thing you see written by your program should be a set of HTTP headers, including the Content-Type, followed by a blank line."

   [Apache's rules for CGI]: http://httpd.apache.org/docs/current/howto/cgi.html#writing

+ [RFC 3875 for the Common Gateway Interface](http://www.ietf.org/rfc/rfc3875)  section 6.3.1 (CGI Response, Content-Type): "If an entity body is returned, the script MUST supply a Content-Type field in the response."
+ [RFC 2616 for HTTP 1.1](http://tools.ietf.org/html/rfc2616#section-4) says that there should be a first line in an HTTP message, specifying that the message is a Response.  This standard is not enforced by Apache and therefore is similarly not enforced by this Apache-compatible Python Web Server.
+ The same [RFC 2616 for HTTP 1.1](http://tools.ietf.org/html/rfc2616#section-14.17) specifies the Content-Type header
+ [The Python docs](http://docs.python.org/2/library/cgi.html#cgi.parse_header) specify the use of the `email.header` package for parsing the MIME headers that are used in HTTP messages

## Behavior
The Apache-compatible Python Web Server checks that the response starts with a content-type header, but Apache is actually more lax than [its own documentation][Apache's rules for CGI] suggests.  I think Apache will accept any line with a colon that is followed by a blank line.  Certainly Apache 2 accepts the following two "headers" that are invalid according the the RFCs cited above: 
```
:\n\n
```
```
junk : more junk\n\n
```
    

