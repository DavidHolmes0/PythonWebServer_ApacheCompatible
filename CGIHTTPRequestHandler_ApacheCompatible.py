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

import os
import sys
import urllib
import BaseHTTPServer
import CGIHTTPServer
import select
import copy

class CGIHTTPRequestHandler_ApacheCompatible( CGIHTTPServer.CGIHTTPRequestHandler):
    '''HTTP server that requires scripts to return a Content-type header.

       The requirement is imposed for consistency with the Apache
       server, and (maybe) in accordance with the requirements of the
       CGI RFC 3875, whose CGI Response, Content-Type section 6.3.1
       says "If an entity body is returned, the script MUST supply a
       Content-Type field in the response."

       Imposing this requirement aims to help users of this server
       notice the absence of the header before transferring scripts to
       an Apache server.
    '''
    def run_cgi(self):
        '''Execute a CGI script.

           This code is largely a copy of
           CGIHTTPServer.CGIHTTPRequestHandler.run_cgi, diverging in
           the section marked with the comment "require headers".

           Unlike the original, this version does not fork processes
           on *nix systems, because such forking is thought to deprive
           this code of any opportunity to inspect the text returned
           by the script.
        '''
##        # show attributes that have values and that don't
##        vals = []
##        novals = []
##        for attr in dir(self):
##            try:  vals.append( (attr, repr( vars(self)[attr])))
##            except KeyError: novals.append( attr)
##        print 'attributes with values'
##        for attr in vals:   print '    %s=%s' % (attr[0],  attr[1])
##        print 'attributes withOUT values'
##        for attr in novals: print '    %s' % attr 
        
        # split up the request url.  Comments show sample values from
        #   GET /cgi-bin/sub/test_html.py?name=Noman HTTP/1.1
        path = self.path  # e.g. /cgi-bin/sub/test_html.py?name=Noman
        urlDir, rest = self.cgi_info  # e.g. /cgi-bin/sub, test_get.py?name=Noman

        # unknown intent.  The "find" returns -1 for a request of
        #    GET /cgi-bin/sub/test_html.py?name=Noman HTTP/1.1
        i = path.find('/', len(urlDir) + 1)
        # print 'path="%s"\n urlDir="%s"\n rest="%s"\n i="%s"\n' %\
        #       (path, urlDir, rest, i)
        while i >= 0:
            nextdir = path[:i]
            nextrest = path[i+1:]

            scriptdir = self.translate_path(nextdir)
            if os.path.isdir(scriptdir):
                urlDir, rest = nextDir, nextrest
                i = path.find('/', len(urlDir) + 1)
            else:
                break

        # find an explicit query string, if present.
        i = rest.rfind('?')
        if i >= 0:
            rest, query = rest[:i], rest[i+1:]
        else:
            query = ''

        # dissect the part after the directory name into a script name &
        # a possible additional path, to be stored in PATH_INFO.
        i = rest.find('/')
        if i >= 0:
            script, rest = rest[:i], rest[i:]
        else:
            script, rest = rest, ''

        # scriptname is valid in a url, like /cgi-bin/sub/test_html.py
        # In this example, there is a "cgi-bin" directory somewhere in the
        # host's file system, but that location is omitted from scriptname.
        scriptname = urlDir + '/' + script

        # scriptfile is a location in the host's file system, like
        #    C:\Users\D\Documents\cgi-bin\sub\test_html.py
        # so it includes the directories above the one in which the server
        # starts looking (in this example, C:\Users\D\Documents).
        scriptfile = self.translate_path(scriptname)
        if not os.path.exists(scriptfile):
            self.send_error(404, "No such CGI script (%s)" % scriptname)
            return
        if not os.path.isfile(scriptfile):
            self.send_error(403, "CGI script is not a plain file (%s)" %
                            scriptname)
            return
        ispy = self.is_python(scriptname)
        if not ispy:
            if not (self.have_fork or self.have_popen2 or self.have_popen3):
                self.send_error(403, "CGI script is not a Python script (%s)" %
                                scriptname)
                return
            if not self.is_executable(scriptfile):
                self.send_error(403, "CGI script is not executable (%s)" %
                                scriptname)
                return

        # Reference: http://hoohoo.ncsa.uiuc.edu/cgi/env.html
        # XXX Much of the following could be prepared ahead of time!
        env = copy.deepcopy(os.environ)
        env['SERVER_SOFTWARE'] = self.version_string()
        env['SERVER_NAME'] = self.server.server_name
        env['GATEWAY_INTERFACE'] = 'CGI/1.1'
        env['SERVER_PROTOCOL'] = self.protocol_version
        env['SERVER_PORT'] = str(self.server.server_port)
        env['REQUEST_METHOD'] = self.command
        uqrest = urllib.unquote(rest)
        env['PATH_INFO'] = uqrest
        env['PATH_TRANSLATED'] = self.translate_path(uqrest)
        env['SCRIPT_NAME'] = scriptname
        if query:
            env['QUERY_STRING'] = query
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

        decoded_query = query.replace('+', ' ')

        # Changes to require headers start here.
        # Always use `subprocess`, even when os.fork() exists.
        import subprocess
        cmdline = [scriptfile]
        if self.is_python(scriptfile):
            interp = sys.executable
            if interp.lower().endswith("w.exe"):
                # On Windows, use python.exe, not pythonw.exe
                interp = interp[:-5] + interp[-4:]
            cmdline = [interp, '-u'] + cmdline

        # Why is this next block here?  It was maintained from
        # CGIHTTPServer.py, but typically queries contain '=', as in
        #   ...test_get.py?The-Button=Submit
        if '=' not in query:
            cmdline.append(query)

        self.log_message("command: %s", subprocess.list2cmdline(cmdline))
        try:
            nbytes = int(length)
        except (TypeError, ValueError):
            nbytes = 0
        p = subprocess.Popen(cmdline,
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
        whine = self._apacheObjection( stdout, scriptfile)
        if whine:
            self.send_error(500, whine)  #  Why 500:  when the script's 
              # result lacks a content-type header, Apache returns
              # error 500 "Internal Server Error".  That message seems
              # misleading, but I will grudgingly maintain the error number.
            stderr += whine

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
           that contains a content-type field, such as either of
               Content-type: text/html\n\n
               Date: Tue, 15 Nov 1994 08:12:31 GMT\nContent-type: text/plain\n\n
           Apache accepts both of these.
        '''
        import email.parser
        msgParser = email.parser.HeaderParser()
        msg = msgParser.parsestr( scriptResult)

        # Make sure scriptResult is not a multipart message.
        # Multipart messages are ok for email messages, and thus
        # acceptable to the email package, but not for HTTP (I think).
        if msg.is_multipart():
            return 'The response from script %s looks like a multipart message, '\
                   'rather than the simple header-and-body that is expected.'\
                   '  The script result starts with\n%s' \
                   % (scriptFile, repr( scriptResult)[:80])

        # A "content-type" header will satisfy Apache and RFC 3875
        if not msg.has_key('content-type'):
            return 'The response from script %s lacks a content-type header.  '\
                   'Instead it starts with\n%s'\
                   % (scriptFile, repr( scriptResult)[:80])
        # if all checks pass, implicitly return None

    self.cgiSpecs = {}
    # self.cgiSpecs is a dictionary that accumulates characteristics
    # of the requested resource that are relevant to its use as a cgi
    # script.  These comments define self.cgiSpecs's entries.  The
    # names are derived from the CGI RFC 3875 where appropriate.
    # Examples are based on a sample requested url of
    # http://localhost:9000/tests/test_html.py/extra-path/seeRfc3875?myName=Noman
    # requested on a Windows system by user "D"
    
    # scriptAndExtraPath
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
    #     The part of the scriptAndExtraPath that qualifies the
    #     request as a CGI request.  For example,
    #         .py
    #         .Py  capitals are ok even on case-sensitive systems
    #         .pyw
    # webRoot
    #     The normalized path of the directory below which the server
    #     seeks requested resources.  This directory corresponds to
    #         ~/public_html
    #     in the Apache setup.  For example
    #         C:\Users\D\Documents
    #    This path must be normalized in sense used by
    #    os.path.normpath, so it can be compated to other normalized
    #    paths.
    self.cgiSpecs['webRoot'] = \
        os.path.normpath( os.path.expanduser('~/Documents'))
    # fileSpec
    #     The normalized path in the file system (not in a url) of the
    #     requested resource.  For example,
    #         C:\Users\D\Documents\tests\test_html.py

    
    
    def is_cgi(self):
        '''Return whether a CGI script is requested, populating cgiSpecs.

        When a cgi script is requested, this routine is additionally
        responsible for...
        o  populating self.cgiSpecs, an attribute that is a dictionary 
           of information to be used in subsequent steps, especially
           the run_cgi() method
        o  any useful check that can be done before running the script.
           Checking at this point allows this routine to return False
           when the requested resource looks like a cgi script but is
           deficient in some way.  For example, a file that fails to
           start with a unix shebang (that is, "#! /usr/bin/python")
           is considered to *not* be a valid cgi script by this server.
           Returning False for such files allows the server to send their
           contents to the client browser, rather than executing them.

        This routine defines at least the following elements of the
        self.cgiSpecs dictionary:
            scriptAndExtraPath
            extraPath
            extension
            fileSpec

        Much of this routine's defined role is delegated to routines
        it calls.

        Currently, all and only Python files are considered CGI
        scripts, in keeping with Stuy's current configuration of
        Apache.  There, Apache's configuration option "AddHandler
        cgi-script" defines extensions that indicate cgi scripts.

        The methods defined here are modeled on those in the base
        class.  In particular, this method is retained even though
        most of its functionality is delegated to is_python, in the
        hope of easing future expansion.

        If any exception is raised, the caller should assume that
        self.path was rejected as invalid and act accordingly.  This
        warning is retained from the base class, without knowing
        exactly which exceptions are contemplated.
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
        self.cgiSpecs['scriptAndExtraPath'] = urlparse.urlsplit(self.path).path
        return self.is_python()


    def is_python( self):
        ''' Return whether a Python script is requested, populating cgiSpecs.

        A python script is requested iff the slash-separated parts of
        self.cgiSpecs['scriptAndExtraPath'] have a prefix (often the
        whole string) that ends with a Python file extension (that is,
        .py or .pyw).  In addition, the file at the corresponding
        place in the file system must conform to some requirements,
        such as existence, executability, and starting with a *nix
        shebang (on all systems, not just *nix).

        Populate additional elements of self.cgiSpecs, as defined in
        the comments to is_cgi.
        '''
        
        # If this server is expanded to support other types of cgi
        # scripts, much of this code should be factored out for
        # re-use.
        
        # seek ".py" at the end of a segment of the scriptAndExtraPath
        pat = re.compile(r'''(?P<anteFirstPy>.*?) #non-greedy, so find 1st .py
                             (?P<ext>\.py)
                             (?P<extraPath>/.*)*
                             $   # without this, the patern would matchx.pyJunk
                          ''',
                         re.IGNORECASE | re.VERBOSE)
        ## # demo
        ## matched = pat.match('/dirs/./..//all%20sorts/script.pY/extra/path.py')
        ## print matched.group('anteFirstPy', 'ext', 'extraPath')
        matched = pat.match( self.cgiSpecs['scriptAndExtraPath'])
        if not matched: return False

        # Populate self.cgiSpecs.
        # Empirically, it looks like Apache unquotes path elements
        # before populating the environment variables.
        self.cgiSpecs['extraPath'] = urllib.unquote( matched.group('extraPath'))
        self.cgiSpecs['extension'] = matched.group('ext')

        # build cgiSpecs['fileSpec']
        urlSpec = urllib.unquote( matched.group('anteFirstPy')) +\
                  self.cgiSpecs['extension']
        # ignore any leading /, making a path relative to webRoot
        if urlSpec[0] == '/':  urlSpec = urlSpec[1:]
        self.cgiSpecs['fileSpec'] = \
            os.path.normpath( os.path.join(self.cgiSpecs['webRoot'],
                                           urlSpec))
            
        #  ban reference above webRoot via excessive '..' occurrences
        if not self.cgiSpecs['fileSpec'].startswith(self.cgiSpecs['webRoot']):
            self.send_error(403, 'Request(s) for parent directory exceeded '
                            'root of web in url request "%s"' % urlSpec)
            return False

        # a directory is not a Python script (server may list it)
        if os.path.isdir( self.cgiSpecs['fileSpec']):  return False

        # file exists, is a regular file, is executable?
        if not os.path.exists( self.cgiSpecs['fileSpec']):
            self.send_error(404, '"%s" does not exist.' % urlSpec)
            return False
        if not os.path.isfile( self.cgiSpecs['fileSpec']):
            self.send_error(404, '"%s" is not a regular file.' % urlSpec)
            return False
        if not self.is_executable(self.cgiSpecs['fileSpec']):
            self.send_error(403, '"%s" is not executable by web server.  '
                            'Consider "chmod +x %s".' %
                            (self.cgiSpecs['fileSpec'],) * 2)
            return False

        # all checks passed
        return True
        

        

            
        
