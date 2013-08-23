Apache-compatible Python Web Server ("ACPWS")
=============================================

A version of Peter Brook's PythonWebServer ("PWS") that behaves more like Apache.

security warnings
-----------------
The docstring for a base class warns against using this server unless you are inside a firewall, because "it may execute arbitrary Python code or external programs."

The choice of the web root probably exposes excessive amounts of the directory tree to browsing.  

The intentionally-explicit error messages raise vulnerability to [cross-site scripting](http://en.wikipedia.org/wiki/Cross-site_scripting).

background
----------
For an introductory comp sci course, students develop html and server-side Python 2.7 scripts for eventual deployment to an Apache server.  For initial development, programmers can run this Apache-compatible server on their local machine, thereby reducing network issues and dependency on the remote, weak machine that is running Apache. Eventual porting to the Apache-running machine has the benefit of publishing their results for others to see.

For the local development to be most useful, the local server should closely resemble the Apache server.  Apache imposes more standards than the Python-standard modules on which ACPWS is based.  The problem with the more relaxed approach is that a programmer could create a script that worked with the local server but for which Apache returned an unhelpful error message like "Internal Server Error".  

behavior
--------
The behavior of ACPWS differs from that of its base `CGIHTTPRequestHandler` class in several respects:

**serve from any directory**  Html files and Python CGI scripts can be stored in any directory below the web root.  The base class required special-purpose, single-level `cgi-bin` and `html-stuff` directories below the server's directory.  The new behavior, by contrast, supports arbitrary levels of subdirectories and organizing files into directories based on projects, rather than by the technology used for those files.  For example, Windows user Ernie, while working on homework #5, might create the directory `C:\Users\Ernie\Documents\homework\5\` and populate it with the files `ask.html`, `answer.py`, and `data.csv`.

**paths relative to script's directory** An `open` statement in a Python cgi script in directory *x* looks for files starting in directory *x*.  More precisely, relative paths are relative to the directory holding the script.  The aim is to support storing a script's data files in the script's directory, or one of its subdirectories, as is commonly done with Apache.  Before this change, scripts in `PythonWebServer/cgi-bin/` by default opened files in the parent `PythonWebServer/` directory.

**restrictions like Apache's**  Before this change, PWS accepted scripts that Apache rejected.  The new version aims to produce understandable error messages for violating Apache's rules, including...

+ CGI scripts must start with a shebang (such as `#! /usr/bin/python`), even on Windows.

+ Python CGI scripts on \*nix systems, including Mac OS&nbsp;X, must be marked as executable, just as they must on the Apache servers.

+ Script output must start with HTML header(s) that include at least the content-type, like `Content-type: text/html\n\n`  This restriction accords with the [CGI standard][] section 6.3.1 (CGI Response, Content-Type).  Apache is more lax, even more lax than [its own documentation][Apache's rules for CGI] suggests.  I think Apache will accept any line with a colon that is followed by a blank line.  Certainly Apache&nbsp;2 accepts the following two "headers" that are invalid according the the standards cited in the "references" section: 
```
:\n\n
```
```
junk : more junk\n\n
```

Minor changes include...

**extra-path support**  The [CGI standard][] section 3.3 discusses adding "extra-path" information to a requested URL, *after* the name of the CGI script.  Apache supports that syntax, so that http://homer.stuy.edu/~dholmes/showEnv.py/extraPath/seeRfc3875?myQuery runs the showEnv.py script, making the information "/extraPath/seeRfc3875" available to that script in the environment variables `PATH_INFO` and `PATH_TRANSLATED`.  No one wants to use this feature, but implementing it was cheap given the significant changes.

**SCRIPT_FILENAME**  For CGI scripts, environment variable `SCRIPT_FILENAME` is set to to the location in the file system of the CGI script.  This environment variable is not defined in the [CGI standard][], but it is [set by Apache](http://wiki.apache.org/httpd/RewriteContext) .

implementation
--------------
Implementation is based on Python's basic `HTTPServer` and the `CGIHTTPRequestHandler` class, which is defined in Python 2.7's CGIHTTPServer.py.  

When a client's request specifies a Python script to be executed, the handler's `run_cgi` method invokes the script and sends the output of that script to the client.  The Apache-compatible PWS needs an opportunity to inspect the output before it is sent to the client.  So this implementation derives a new class, `CGIHTTPRequestHandler_ApacheCompatible`, from the standard `CGIHTTPRequestHandler`, overriding the `run_cgi` method with one that implements the appropriate checks, between invoking the script and delivering the output to the client.

The implementation simplifies the standard `CGIHTTPRequestHandler`:  the base class uses Python's `subprocess` module on Windows systems, but forks a child process on \*nix system.  The fork affords no chance for the handler to inspect the output from the script (as I understand it).  So the implementation of `CGIHTTPRequestHandler_ApacheCompatible` uses the `subprocess` module on \*nix systems, just as it does for Windows.

Others have wanted to eliminate the fork, as shown by [this Python patch] (http://bugs.python.org/review/16945/diff/7464/Lib/http/server.py).  I am ignorant concerning the context for this patch.  Is it in some later version of Python?  At any rate, it is reassuring that the author and reviewer of the patch seem to have made the same simplification that I did.

testing
-------
Preliminary testing has been done...
+ on Windows&nbsp;7, with Python 2.7.3 and 4 browsers (Internet Explorer v10, Chrome, Firefox, Safari) 
+ on Windows&nbsp;8, with Python 2.7.5 and the same 4 browsers 
+ on Mac OS&nbsp;X, with Python 2.7.5 and 3 browsers (Chrome, Firefox, Safari)

The test_get.py cgi script has been modified from the form used in Peter Brooks's PWS, so that it now accesses the values past to it from test_post.html using `FieldStorage.getfirst()`, rather than indexing FieldStorage like a dictionary whose keys are field names.  This is unfortunate because students have been taught to use the dictionary-like syntax.  But test_get.py would intermittently fail because the object returned by FieldStorage had a list of buttons, rather than a single button.  A sample traceback from cgitb [appears here] (http://www.davidmholmes.net/Stuy/PythonWebServer/buttonListError.htm).  The failure would cease to reproduce, making it difficult to investigate.  The cause might be in the ACPWS, in FieldStorage, or even in the data sent by browsers.  The divergence from the syntax taught is unfortunate, but perhaps the course should switch to the more modern `FieldStorage.getfirst()` for the reasons discussed in the [Python docs] (http://docs.python.org/2/library/cgi.html#higher-level-interface).

More testing and bug reports are welcome.
    
known issues
------------
Internet Explorer 10 has a few issues.  The worst is that it intermittently fails to complete communication with the server.  The server issues no messages and makes no response to `control+C`, while the browser's tab says "Waiting for localhost".  The wait is sometimes a few minutes, but sometimes is more than 15 (and possibly indefinite; tests have been terminated).  The server can be unlocked by closing the browser (not just the tab).  This issue has not been seen in Chrome, Safari, or Firefox. 

A minor issues with Internet Explorer issue keeps the user from browsing to the standard loopback address 127.0.0.1, because IE interprets the periods in an unexpected way.  The workaround for this second problem is to browse to `http://localhost:9000`.

For these reasons, using Internet Explorer with ACPWS is deprecated. 

references on content-type headers
----------------------------------
+ [Apache's rules for CGI][] say "The first thing... written by your program should be a set of HTTP headers, including the Content-Type, followed by a blank line."

   [Apache's rules for CGI]: http://httpd.apache.org/docs/current/howto/cgi.html#writing

+ [RFC 3875 for the Common Gateway Interface][CGI standard]  section 6.3.1 (CGI Response, Content-Type): "If an entity body is returned, the script MUST supply a Content-Type field in the response."
+ [RFC 2616 for HTTP 1.1](http://tools.ietf.org/html/rfc2616#section-4) says that there should be a first line in an HTTP message, specifying that the message is a Response.  This standard is not enforced by Apache and therefore is similarly not enforced by this Apache-compatible Python Web Server.
+ The same [RFC 2616 for HTTP 1.1](http://tools.ietf.org/html/rfc2616#section-14.17) specifies the Content-Type header
+ [The Python docs](http://docs.python.org/2/library/cgi.html#cgi.parse_header) specify the use of the `email.header` package for parsing the MIME headers that are used in HTTP messages


[CGI standard]:  http://www.ietf.org/rfc/rfc3875
