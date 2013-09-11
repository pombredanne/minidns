from zope.interface import implements
from twisted.application import internet
from twisted.web.server import Site
from twisted.web.resource import Resource, NoResource
import socket

class RecordResource(Resource):

    def __init__(self, name, zone):
        Resource.__init__(self)
        self.name = name
        self.zone = zone

    def render_PUT(self, request):
        data = request.content.read()
        try:
            self.zone.set_record(self.name, data)
        except socket.error:
            request.setResponseCode(400)
            return ""
        request.setResponseCode(201)
        return ""

    def render_DELETE(self, request):
        try:
            self.zone.delete_record(self.name)
        except KeyError:
            request.setResponseCode(404)
            return ""
        request.setResponseCode(204)
        return ""

    def render_GET(self, request):
        type_, ip = self.zone.get_record(self.name)
        return "%s %s" % (type_, ip)

class DomainResource(Resource):

    def __init__(self, zone, dnsserver):
        Resource.__init__(self)
        self.zone = zone
        self.dnsserver = dnsserver

    def render_GET(self, request):
        l = []
        for type_, name, value in self.zone.a_records():
            l.append("%s %s %s" % (type_, name, value))
        return "\n".join(l)

    def render_DELETE(self, request):
        self.dnsserver.delete_zone(self.zone.soa[0])
        request.setResponseCode(204)
        return ""

    def render_PUT(self, request):
        request.setResponseCode(405)
        return ""

    def getChild(self, path, request):
        return RecordResource(path, self.zone)

class MissingDomainResource(Resource):

    """ A resource that can only be PUT to to create a new zone """

    def __init__(self, name, factory):
        Resource.__init__(self)
        self.name = name
        self.factory = factory

    def render_PUT(self, request):
        self.factory.add_zone(self.name)
        request.setResponseCode(201)
        return ""

    def render_GET(self, request):
        request.setResponseCode(404)
        return ""

    def render_HEAD(self, request):
        request.setResponseCode(404)
        return ""

    def render_DELETE(self, request):
        request.setResponseCode(404)
        return ""

class RootResource(Resource):

    def __init__(self, config, dnsserver):
        Resource.__init__(self)
        self.config = config
        self.dnsserver = dnsserver

    def render_GET(self, request):
        return "\n".join(self.dnsserver.zones())

    def getChild(self, path, request):
        if path == "":
            return self
        path = path.rstrip(".")
        try:
            zone = self.dnsserver.get_zone(path)
            return DomainResource(zone, self.dnsserver)
        except KeyError:
            return MissingDomainResource(path, self.dnsserver.factory)

class MiniDNSSite(Site):

    def log(self, *a, **kw):
        pass

def webservice(config, dnsserver):
    root = RootResource(config, dnsserver)
    site = MiniDNSSite(root)
    return internet.TCPServer(config['www_port'], site)
