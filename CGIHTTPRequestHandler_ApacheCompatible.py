'''Handler for a CGI HTTP Server that aims to resemble Apache.

SECURITY WARNING: DON'T USE THIS CODE UNLESS YOU ARE INSIDE A FIREWALL
-- it may execute arbitrary Python code or external programs.

The resemblances to Apache include
  o  requirement for a content-type header in the response from a cgi script
  o  interpreting a file as a Python script if its name has a ".py" extension,
     rather than requiring that the file be housed in a cgi-bin directory.
     As a consequence, html and Python files are served from any sub-directory.
  o  handling the "extra-path" discussed in the CGI RFC 3875

Note that status code 200 is sent prior to execution of a CGI script, so
scripts cannot send other status codes such as 302 (redirect).
'''

__version__ = "0.0"

__all__ = ["CGIHTTPRequestHandler_ApacheCompatible"]

import CGIHTTPServer
import copy
import os
import re
import select
import sys
import time
import urllib

class CGIHTTPRequestHandler_ApacheCompatible( CGIHTTPServer.CGIHTTPRequestHandler):
    '''HTTP server that enforces compatibility with Apache.
    '''

    server_version = __name__ + '/' + __version__

    def run_cgi(self):
        '''Execute a CGI script.

           This code is largely a copy of
           CGIHTTPServer.CGIHTTPRequestHandler.run_cgi.

           Unlike the original, this version does not fork processes
           on *nix systems, for simplicity in accomplishing
           Apache-compatibility.
        '''

        if not self._cgiSpecs['okToRun']:
            self.log_message(
                'A previously-identified issue precludes running %s' % \
                self._cgiSpecs['scriptFile'])
            return                

        # The normalized path of the directory below which the server
        # seeks requested resources.  Currently set at server startup.
        # This path must be "normalized" as that term is  used by
        # os.path.normpath, so it can be compared to other normalized
        # paths.
        webRoot = os.path.normpath( os.getcwd())

        # calculate environment variables for subprocess      
        # XXX Much of the following could be prepared ahead of time!
        env = copy.deepcopy(os.environ)
        env['SERVER_SOFTWARE'] = self.version_string()
        env['SERVER_NAME'] = self.server.server_name
        env['GATEWAY_INTERFACE'] = 'CGI/1.1'
        env['SERVER_PROTOCOL'] = self.protocol_version
        env['SERVER_PORT'] = str(self.server.server_port)
        env['REQUEST_METHOD'] = self.command
        if 'extraPath' in self._cgiSpecs:
            env['PATH_INFO'] = self._cgiSpecs['extraPath']
            env['PATH_TRANSLATED'] =\
              os.path.normpath( os.path.join( webRoot,
                  self._cgiSpecs['extraPath'][1:]))  # ignore leading /
        env['SCRIPT_NAME'] = self._cgiSpecs['scriptUrl']

        # SCRIPT_FILENAME is not defined by CGI RFC 3875, but is created
        # by Apache, with little documentation.  The best I found is
        # http://wiki.apache.org/httpd/RewriteContext
        env['SCRIPT_FILENAME'] = self._cgiSpecs['scriptFile']
        
        if 'query' in self._cgiSpecs:
            env['QUERY_STRING'] = self._cgiSpecs['query']
        host = self.address_string()
        if host != self.client_address[0]:
            env['REMOTE_HOST'] = host
        env['REMOTE_ADDR'] = self.client_address[0]
        authorization = self.headers.getheader("authorization")
        if authorization:
            authorization = authorization.split()
            if len(authorization) == 2:
                import base64, binascii
                env['AUTH_TYPE'] = authorization[0]
                if authorization[0].lower() == "basic":
                    try:
                        authorization = base64.decodestring(authorization[1])
                    except binascii.Error:
                        pass
                    else:
                        authorization = authorization.split(':')
                        if len(authorization) == 2:
                            env['REMOTE_USER'] = authorization[0]
        # XXX REMOTE_IDENT
        if self.headers.typeheader is None:
            env['CONTENT_TYPE'] = self.headers.type
        else:
            env['CONTENT_TYPE'] = self.headers.typeheader
        length = self.headers.getheader('content-length')
        if length:
            env['CONTENT_LENGTH'] = length
        referer = self.headers.getheader('referer')
        if referer:
            env['HTTP_REFERER'] = referer
        accept = []
        for line in self.headers.getallmatchingheaders('accept'):
            if line[:1] in "\t\n\r ":
                accept.append(line.strip())
            else:
                accept = accept + line[7:].split(',')
        env['HTTP_ACCEPT'] = ','.join(accept)
        ua = self.headers.getheader('user-agent')
        if ua:
            env['HTTP_USER_AGENT'] = ua
        co = filter(None, self.headers.getheaders('cookie'))
        if co:
            env['HTTP_COOKIE'] = ', '.join(co)
        # XXX Other HTTP_* headers
        # Since we're setting the env in the parent, provide empty
        # values to override previously set values
        for k in ('QUERY_STRING', 'REMOTE_HOST', 'CONTENT_LENGTH',
                  'HTTP_USER_AGENT', 'HTTP_COOKIE', 'HTTP_REFERER'):
            env.setdefault(k, "")

        self.send_response(200, "Script output follows")

        # Always use `subprocess`, even when os.fork exists (unlike base class).
        scriptDir, scriptNameAndExt = os.path.split( self._cgiSpecs['scriptFile'])
        cmdline = [ self._cgiSpecs['interpreter'], '-u', scriptNameAndExt]

        # Why is this next block here?  It was maintained from
        # CGIHTTPServer.py, but typically queries contain '=', as in
        #   ...test_get.py?The-Button=Submit
        if 'query' in self._cgiSpecs and '=' not in self._cgiSpecs['query']:
            cmdline.append( self._cgiSpecs['query'])

        import subprocess
        self.log_message(
            'command: %s\n   in directory "%s"\n   Starting script on %s...',
             subprocess.list2cmdline(cmdline),
             scriptDir,
             time.strftime('%A, %Y-%m-%d %H:%M:%S'),
            )
        try:
            nbytes = int(length)
        except (TypeError, ValueError):
            nbytes = 0
        p = subprocess.Popen(cmdline,
                             cwd = scriptDir,
                             stdin = subprocess.PIPE,
                             stdout = subprocess.PIPE,
                             stderr = subprocess.PIPE,
                             env = env
                            )
        if self.command.lower() == "post" and nbytes > 0:
            data = self.rfile.read(nbytes)
        else:
            data = None
        # throw away additional data [see bug #427345]
        while select.select([self.rfile._sock], [], [], 0)[0]:
            if not self.rfile._sock.recv(1):
                break
        stdout, stderr = p.communicate(data)

        # Check that stdout matches Apache's requirements
        whine = self._apacheObjection( stdout, self._cgiSpecs['scriptFile'])
        if whine:  self.send_error(500, whine)
            #  Why 500:  when the script's result lacks a content-type
            # header, Apache returns error 500 "Internal Server
            # Error".  That message seems misleading, but I will
            # grudgingly maintain the error number.
        else:  # script output is expected to satisfy Apache
            self.wfile.write(stdout)
        if stderr:
            self.log_error('%s', stderr)
        p.stderr.close()
        p.stdout.close()
        status = p.returncode
        if status:
            self.log_error("CGI script exit status %#x", status)
        else:
            self.log_message("CGI script exited OK")

    @staticmethod
    def _apacheObjection( scriptResult, scriptFile):
        '''What objection (if any) is Apache expected to make to scriptResult?

           To analyze headers, the Python docs recommend "since
           version 2.3: The email package should be used in preference
           to the mimetools module."  But the email package accepts
           messages that can be more complicated than the message
           headers and message body in an HTTP message (as I
           understand RFC 2616).  So this routine checks that
           scriptResult is free of these complications.

           Empirically I find that Apache will accept a response whose header
           lacks a content-type field, including either of
               :\n\n
               junk : more junk\n\n
           Sad.  This routine imposes a more stringent requirement,
           namely, text that the email package considers to be header
           that contains a content-type field, for example, either of
               Content-type: text/html\n\n
               Date: Tue, 15 Nov 1994 08:12:31 GMT\nContent-type: text/plain\n\n
           Apache accepts both of these samples.
        '''
        import email.parser
        msgParser = email.parser.HeaderParser()
        msg = msgParser.parsestr( scriptResult)

        # Make sure scriptResult is not a multipart message.
        # Multipart messages are ok for email messages, and thus
        # acceptable to the email package, but not for HTTP (I think).
        if msg.is_multipart():
            return 'A multipart message was received from script "%s", '\
                   'rather than the simple header-and-body that is expected.  '\
                   'The script result starts with\n%s' \
                   % (scriptFile, repr( scriptResult)[:80])

        # A "content-type" header will satisfy Apache and RFC 3875
        if not msg.has_key('content-type'):
            return 'The required content-type header is missing in the '\
                'output from script "%s".  Instead the output starts with\n%s'\
                   % (scriptFile, repr( scriptResult)[:80])
        # if all checks pass, implicitly return None

    _cgiSpecs = {}
    # self._cgiSpecs is a dictionary that accumulates characteristics
    # of the requested resource that are relevant to its use as a cgi
    # script.  These comments define self._cgiSpecs's entries.  The
    # names of dictionary entries are derived from the CGI RFC 3875
    # where appropriate. They aim to maintain the distinction between
    # the specification of the requested resource in the url versus in
    # the file system.  Examples are based on a sample requested url of
    # http://localhost:9000/tests/test_html.py/extra-path/seeRfc3875?myName=Noman
    # requested on a Windows system by user "D"
    
    # scriptAndExtraPathUrl
    #     contains the portions of the url that the rfc calls
    #     "script-path" and "extra-path".  The extra-path is optional.
    #     Begins with a slash for consistency with urlparse.  For
    #     example
    #         /tests/test_html.py/extra-path/seeRfc3875
    # extraPath
    #     The CGI RFC 3875 and Apache allow an "extra-path"
    #     specification to appear after the script name.  For example
    #         /extra-path/seeRfc3875
    # extension
    #     The part of the scriptAndExtraPathUrl that qualifies the
    #     request as a CGI request.  For example,
    #         .py
    #         .Py  capitals are ok even on case-sensitive systems
    #         .pyw
    # scriptUrl
    #     The portion of the url that identifies the script, destined
    #     for the SCRIPT_NAME environment variable.  See the
    #     definition of SCRIPT_NAME in the CGI RFC 3875.  For example,
    #          /tests/test_html.py   
    # scriptFile
    #     The normalized path in the file system (not in a url) of the
    #     requested resource.  For example,
    #         C:\Users\D\Documents\tests\test_html.py
    # interpreter
    #     The command to invoke the appropriate interpreteter for the
    #     cgi script.
    # okToRun
    #     Whether the script passed all checks so far, so that it
    #     should be run.  The resource requested by the client might
    #     be a cgi script (based on its url), but that script should
    #     not be run (say, because it is not executable).  In that
    #     case is_cgi() must return True, so that the server doesn't
    #     treat the file as plain text to be displayed.  But run_cgi()
    #     should not attempt to run the script, since an error message
    #     will already have been generated.  The information to eschew
    #     running is communicated by setting okToRun to False.
    # query
    #     the query from the url, if one was specified; otherwise the
    #     dictionary contains no 'query' key.  The value excludes the
    #     '?' delimeter.

    
    
    def is_cgi(self):
        '''Return whether a CGI script is requested, populating _cgiSpecs.

        When a cgi script is requested, this routine is additionally
        responsible for...
        o  populating self._cgiSpecs
        o  any useful checks that can be done before running the script.
           Checking at this point allows this routine to return False
           when the requested resource looks like a cgi script but is
           deficient in some way.  For example, a file that fails to
           start with a unix shebang (that is, "#! /usr/bin/python")
           is considered to *not* be a valid cgi script by this server.
           Returning False for such files allows the server to send their
           contents to the client browser, rather than executing them.

        This routine defines at least the following elements of the
        self._cgiSpecs dictionary:
            scriptAndExtraPathUrl
            extraPath
            extension
            scriptUrl
            scriptFile
            interpreter
            okToRun
            query, if a query was specified in the url

        Much of this routine's operation is delegated to routines
        it calls.

        Currently, all and only Python files are considered CGI
        scripts, in keeping with Stuy's current configuration of
        Apache.  There, Apache's configuration option
            AddHandler cgi-script
        defines extensions that indicate cgi scripts.

        The methods defined here are modeled on those in the base
        class, in the hope of easing future expansion.  In particular,
        this method is retained even though most of its functionality
        is delegated to is_python.

        If any exception is raised, the caller should assume that
        self.path was rejected as invalid and act accordingly.  This
        warning is retained from the base class, without knowing which
        -- if any -- exceptions are still expected.
        '''

        # When this method is called, self.path can contain a query, like
        #   /cgi-bin/test_get.py?first_text=first&The-Button=Submit
        # even though BaseHTTPServer.BaseHTTPRequestHandler.parse_request()
        # sets self.path to the path alone, like /cgi-bin/test_get.py
        # (without using the standard urlparse).  But this routine is being
        # called before parse_request, so sadly the processing is
        # duplicated here.  Who decided self.path should have different
        # meanings at different times?
        import urlparse
        urlParts = urlparse.urlsplit(self.path)
        self._cgiSpecs['scriptAndExtraPathUrl'] = urlParts.path
        if urlParts.query:  self._cgiSpecs['query'] = urlParts.query
        return self.is_python()


    def is_python( self):
        ''' Return whether a Python script is requested, populating _cgiSpecs.

        A Python script is requested iff the slash-separated parts of
        self._cgiSpecs['scriptAndExtraPathUrl'] have a part that ends
        with a Python file extension (that is, .py or .pyw).  In
        addition, the file at the corresponding place in the file
        system must conform to some requirements, such as existence,
        executability, and starting with a *nix shebang (on all
        systems, not just *nix).

        Populate additional elements of self._cgiSpecs, as defined in
        the comments to is_cgi.
        '''
        
        # If this server code is expanded to support other types of
        # cgi scripts, much of this code should be factored out for
        # re-use.

        # The normalized path of the directory below which the server
        # seeks requested resources.  Currently set at server startup.
        # This path must be "normalized" as that term is  used by
        # os.path.normpath, so it can be compared to other normalized
        # paths.
        webRoot = os.path.normpath( os.getcwd())
        
        # seek ".py" at the end of a segment of the scriptAndExtraPathUrl
        pat = re.compile(r'''(?P<anteFirstPy>.*?) #non-greedy, so find 1st .py
                             (?P<ext>\.py)
                             (?P<extraPath>/.*)*
                             $   # without this, the patern would matchx.pyJunk
                          ''',
                         re.IGNORECASE | re.VERBOSE)
        ## # demo
        ## matched = pat.match('/dirs/./..//all%20sorts/script.pY/extra/path.py')
        ## print matched.group('anteFirstPy', 'ext', 'extraPath')
        matched = pat.match( self._cgiSpecs['scriptAndExtraPathUrl'])
        if not matched: return False

        # Populate self._cgiSpecs.
        self._cgiSpecs['okToRun'] = False  # a priori; change if pass all tests
        # From the CGI RFC 3875 and from empirical tests of Apache,
        # the values are url-decoded (for example, convert "%20" to space).
        self._cgiSpecs['scriptUrl'] = urllib.unquote( matched.group('anteFirstPy'))+\
                                     matched.group('ext')  # already no url encoding
        if matched.group('extraPath'):
            self._cgiSpecs['extraPath'] = urllib.unquote( matched.group('extraPath'))
        self._cgiSpecs['extension'] = matched.group('ext')

        # build _cgiSpecs['scriptFile']; see definition above
        urlSpec = urllib.unquote( matched.group('anteFirstPy')) +\
                  self._cgiSpecs['extension']
        # ignore any leading /, making a path relative to webRoot, not absolute
        if urlSpec[0] == '/':  urlSpec = urlSpec[1:]
        self._cgiSpecs['scriptFile'] = \
            os.path.normpath( os.path.join( webRoot, urlSpec))
            
        # Ban reference above webRoot via excessive '..' occurrences.
        # '..' is apparently removed from addresses by IE10, Chrome,
        # Firefox, and Safari.  Test this code using
        #     telnet localhost 9000
        #     GET /../x.py  <return><return>
        if not self._cgiSpecs['scriptFile'].startswith(webRoot):
            self.send_error(403, 'Request(s) for parent directory using ".." '
                            'exceed root of web, in url request "%s"' % urlSpec)
            return True

        # file exists, is a regular file, is executable?
        if not os.path.exists( self._cgiSpecs['scriptFile']):
            self.send_error(404, 'The requested script is not found at "%s"' %\
                            self._cgiSpecs['scriptFile'])
            return True
        if not os.path.isfile( self._cgiSpecs['scriptFile']):
            self.send_error(404, '"%s" is not a regular file' % self._cgiSpecs['scriptFile'])
            return True

        # is the file non-executable?  It would be nice to determine
        # this by calling self.is_executable.  Sadly, that method
        # returns False for Windows files!  Check executability only
        # on non-Windows systems.
        import stat, platform
        if platform.system() != 'Windows' and \
           not os.stat( self._cgiSpecs['scriptFile']).st_mode & stat.S_IXUSR:
            self.send_error(403, 'The web server cannot execute the file '
                            'at "%s".  Consider "chmod +x %s"' %\
                            ((self._cgiSpecs['scriptFile'],) * 2))
            return True

        if self._lacksShebang():
            self.send_error(403, 'The shebang line is missing at the start of '
                                 'script "%s".  Make the first line of the '
                                 'script "#! /usr/bin/python " (without '
                                 'the quotes)' % self._cgiSpecs['scriptFile'])
            return True
            

        # all checks passed
        self._cgiSpecs['okToRun'] = True
        
        # set Python as the interpreter for this Python cgi script
        if sys.executable.lower().endswith("w.exe"):
            # On Windows, use python.exe, not pythonw.exe
            self._cgiSpecs['interpreter'] = sys.executable[:-5] + sys.executable[-4:]
        else:  self._cgiSpecs['interpreter'] = sys.executable
            
        return True
        
    def _lacksShebang( self):
        '''Returns whether the script file fails to start with a shebang.'''

        pat = re.compile(r'#![\t ]*/usr/bin/(env[\t ]+)?python')
        f = open( self._cgiSpecs['scriptFile'])
        matched = pat.match( f.readline())
        f.close()
        return not bool(matched)
        
    
        
