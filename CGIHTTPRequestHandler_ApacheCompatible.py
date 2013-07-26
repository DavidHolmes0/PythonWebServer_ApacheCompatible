#! /usr/bin/python

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
        path = self.path
        dir, rest = self.cgi_info

        i = path.find('/', len(dir) + 1)
        while i >= 0:
            nextdir = path[:i]
            nextrest = path[i+1:]

            scriptdir = self.translate_path(nextdir)
            if os.path.isdir(scriptdir):
                dir, rest = nextdir, nextrest
                i = path.find('/', len(dir) + 1)
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

        scriptFile = dir + '/' + script
        scriptfile = self.translate_path(scriptFile)
        if not os.path.exists(scriptfile):
            self.send_error(404, "No such CGI script (%r)" % scriptFile)
            return
        if not os.path.isfile(scriptfile):
            self.send_error(403, "CGI script is not a plain file (%r)" %
                            scriptFile)
            return
        ispy = self.is_python(scriptFile)
        if not ispy:
            if not (self.have_fork or self.have_popen2 or self.have_popen3):
                self.send_error(403, "CGI script is not a Python script (%r)" %
                                scriptFile)
                return
            if not self.is_executable(scriptfile):
                self.send_error(403, "CGI script is not executable (%r)" %
                                scriptFile)
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
        env['SCRIPT_NAME'] = scriptFile
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
        if whine:   # content-type is missing; send client an error
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
            return 'The response from script %r looks like a multipart message, '\
                   'rather than the simple header-and-body that is expected.'\
                   '  The script result starts with\n%s' \
                   % (scriptFile, repr( scriptResult)[:80])

        # A "content-type" header will satisfy Apache and RFC 3875
        if not msg.has_key('content-type'):
            return 'The response from script %r lacks a content-type header.  '\
                   'Instead it starts with\n%s'\
                   % (scriptFile, repr( scriptResult)[:80])
        # if all checks pass, implicitly return None
