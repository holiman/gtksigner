#!/usr/bin/env python3

from gtkapp import *
import os,sys, subprocess
from tinyrpc.transports import ServerTransport
from tinyrpc.protocols.jsonrpc import JSONRPCProtocol
from tinyrpc.dispatch import public, RPCDispatcher
from tinyrpc.server import RPCServer

tx_template ="""
-- Transaction details -----------------

to:         {to}
from:       {from}
value:      {value}
data:       {data}

-- Validation details ------------------

{info}

-- Request details ---------------------

{metastr}

"""
def txToText(req):
    info = ''
    tx = req['transaction']
    if 'call_info' in req.keys():
        info = "\n".join(["  *  {type} : {message}".format(**x) for x in req['call_info']])

    meta = ''
    if 'meta' in req.keys():
        meta = "\n".join(["  *  {k} : {v}".format(k=k,v=v) for k,v in req['meta'].items()])


    return tx_template.format( **tx, metastr=meta, info=info)

signdata_template = """
-- Signing details ---------------------

Account:    {address}
message:    {message}
raw data:   {raw_data}
hash:       {hash}

-- Request details ---------------------

{metastr}

"""
def signDataToText(req):

# {'address': '0x', 'raw_data': '0x01020304', 'message': '\x19Ethereum Signed Message:\n4\x01\x02\x03\x04', 'hash': '0x7e3a4e7a9d1744bc5c675c25e1234ca8ed9162bd17f78b9085e48047c15ac310', 'meta': {'remote': 'signer binary', 'local': 'main', 'scheme': 'in-proc'}}
    meta = ''
    if 'meta' in req.keys():
        meta = "\n".join(["  *  {k} : {v}".format(k=k,v=v) for k,v in req['meta'].items()])

    return signdata_template.format(**req, metastr=meta)

list_template = """
-- Listing  details --------------------
A request has been made to list all accounts. 
The following accounts are available listing:

{accountlist}

Approve to list these accounts?

-- Request details ---------------------

{metastr}
"""

def listingToText(req):
    meta = ''
    if 'meta' in req.keys():
        meta = "\n".join(["  *  {k} : {v}".format(k=k,v=v) for k,v in req['meta'].items()])


    accountlist = ''
    if 'accounts' in req.keys() and req['accounts'] is not None:
        accountlist = "\n".join(["  *  {address}".format(**x) for x in req['accounts']])

    return list_template.format( metastr=meta, accountlist = accountlist)

newAccount_template = """
-- Details --------------------
A request has been made to create a new account, 
and show the address to the caller. 

Do you want to create a new keystore-backed account?

-- Request details ---------------------

{metastr}
"""
def newAccountToText(req):
    meta = ''
    if 'meta' in req.keys():
        meta = "\n".join(["  *  {k} : {v}".format(k=k,v=v) for k,v in req['meta'].items()])
    return newAccount_template.format(metastr = meta)


""" This is a POC example of how to write a custom UI for the signer. The UI starts the 
signer process with the '--stdio-ui' option, and communicates with the signer binary
using standard input / output.

The standard input/output is a relatively secure way to communicate, as it does not require opening any ports
or IPC files. Needless to say, it does not protect against memory inspection mechanisms where an attacker
can access process memory."""

try:
    import urllib.parse as urlparse
except ImportError:
    import urllib as urlparse

class StdIOTransport(ServerTransport):
    """ Uses std input/output for RPC """
    def receive_message(self):
        return None, urlparse.unquote(sys.stdin.readline())

    def send_reply(self, context, reply):
        print(reply)

class PipeTransport(ServerTransport):
    """ Uses std a pipe for RPC """

    def __init__(self,input, output):
        self.input = input
        self.output = output

    def receive_message(self):
        data = self.input.readline()
        print(">> {}".format( data))
        return None, urlparse.unquote(data)

    def send_reply(self, context, reply):
        print("<< {}".format( reply))
        self.output.write(reply)
        self.output.write("\n")


class StdIOHandler():

    def __init__(self):
        pass

    @public
    def ApproveTx(self,req):
        """
        :param transaction: transaction info
        :param call_info: info abou the call, e.g. if ABI info could not be
        :param meta: metadata about the request, e.g. where the call comes from
        :return: 
        """
        (approved, pw ) = questionAndPassword(title="Transaction request",text=txToText(req), width=500)
        return {
            "approved" : approved,
            "transaction" : tx,
            "password" : pw,
        }

    @public
    def ApproveSignData(self,req):
        """ Example request


        """
        (approved, pw ) = questionAndPassword(title="Sign data request",text=signDataToText(req), width=500)
        return {"approved": False,
                "password" : None}

    @public
    def ApproveExport(self,req):
        """ Example request

        """
        return {"approved" : False}

    @public
    def ApproveImport(self,req):
        """ Example request
        """
        return {"approved" : False, "old_password": "", "new_password": ""}

    @public
    def ApproveListing(self,req):
        """ Example request
        """
        approved = question(title="Listing request",text=listingToText(req), width=500)

        if approved and 'accounts' in req.keys():
            return {'accounts' : req['accounts']}

        return {'accounts': []}

    @public
    def ApproveNewAccount(self,req):
        """
        Example request

        :return:
        """
        (approved, pw) = questionAndPassword(title="New account",text=newAccountToText(req))
        return {"approved": approved, "password": pw}

    @public
    def ShowError(self, req):
        """
        Example request:

        :param text: to show
        :return: nothing
        """
        error(req.get('text'))

        return

    @public
    def ShowInfo(self,req):
        """

        :param text: to display
        :return:nothing
        """
        message(req.get('text'))
        return


def connectHandler(cmd, handler):
    dispatcher = RPCDispatcher()
    print("cmd: {}".format(" ".join(cmd)))
    # line buffered
    p = subprocess.Popen(cmd, bufsize=1, universal_newlines=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr = subprocess.PIPE)
    transport = PipeTransport(p.stdout, p.stdin)
    rpc_server = RPCServer(
        transport,
        JSONRPCProtocol(),
        dispatcher
    )
    dispatcher.register_instance(handler, '')
    return (rpc_server, p)

def startSigner(path, test=False, handler = StdIOHandler):

    dir = os.path.dirname(path)
    cmd = ["{}/clef".format(dir),
        "--4bytedb","{}/4byte.json".format(dir),
        "--stdio-ui","--rpc"]

    if test:
        cmd.extend(["--stdio-ui-test"])

    (server, proc) = connectHandler(cmd, handler())
    return (handler, server, proc)


def check_perms(filepath):
    """ Validates the signer binary on the path given"""
    import os
    import stat

    st = os.stat(filepath)
    a_w = bool(st.st_mode & stat.S_IWOTH)
    if a_w:
        return "ERR: Binary is world-writeable. Configure the signer binary to be writeable only by the user.\n\t{}".format(filepath)
    g_w = bool(st.st_mode & stat.S_IWGRP)
    if g_w:
        return "ERR: Binary is group-writeable. Configure the signer binary to be writeable only by the user.\n\t{}".format(filepath)

    return None

def check_hash(filepath):
    import hashlib

    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()

    with open(filepath, 'rb') as f:
        data = f.read(65536)
        while data:
            md5.update(data)
            sha1.update(data)
            sha256.update(data)
            data = f.read(65536)

    print("Hashes for {}:".format(filepath))
    print("{0}".format(md5.hexdigest()))
    print("{0}".format(sha1.hexdigest()))
    print("{0}".format(sha256.hexdigest()))
    # At this point, we have nothing to validate against. 
    return sha256.hexdigest()


description= """
This is a GUI for a signer, based on Gtk.
"""
import argparse
parser = argparse.ArgumentParser(description=description,formatter_class=argparse.RawDescriptionHelpFormatter)

parser.add_argument(
    '-s','--signer', type=str, required=True,
    help="Signer binary (path)", default="/usr/bin/signer")

parser.add_argument(
    '-t','--test', type=bool, default=False,
    help="Do a test-run")


def main(args):
    import os
    binary = args.signer
    bindir = os.path.dirname(os.path.realpath(binary))

#    cmd = ["{}".format(binary),
#        "--4bytedb","{}/4byte.json".format(bindir),
#        "--stdio-ui"]
#        "--stdio-ui-test"]

    # Check as much as we can about the binary
    sha_hash = check_hash(binary)

    err = check_perms(binary)
    if err is not None:
        #sys.exit(0)
        error("Failed to start signer!", err)
        sys.exit(0)
        pass # ... for now....


    (handler, server, proc) = startSigner(binary, args.test)
    server.serve_forever()

if __name__ == '__main__':
    options = parser.parse_args()
    main(options)
