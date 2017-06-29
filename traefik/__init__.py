from escapism import escape
import json
import etcd
import os
from jupyterhub.proxy import Proxy
from tornado import gen


class Traefik(Proxy):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = etcd.Client(port=2379)
        self.prefix = '/traefik'

    def _k(self, *args):
        return os.path.join(self.prefix, *args)

    @gen.coroutine
    def add_route(self, routespec, backend, data=None):
        if routespec.startswith('/'):
            # url only spec
            host = None
            url_prefix = routespec
        else:
            host, url_prefix = routespec.split('/', 1)

        name = escape(routespec, escape_char='-')
        self.log.info(name)
        self.client.write(
            self._k('backends', name, 'servers', 'notebook', 'url'), backend)

        self.client.write(
            self._k('frontends', name, 'backend'), name)

        self.client.write(
            self._k('frontends', name, 'routes', 'prefix', 'rule'), 'PathPrefix:{}'.format(url_prefix))
        if host:
            self.client.write(self._k(
                'frontends', name, 'routes', 'host', 'rule'), 'Host:{}'.format(host))

        if data:
            self.client.write(
                self._k('frontends', name, 'extra'), json.dumps(data))

    @gen.coroutine
    def get_route(self, routespec):
        name = escape(routespec, escape_char='-')
        target = self.client.read(
            self._k('backends', name, 'servers', 'notebook', 'url'))
        data = json.loads(self.client.read(
            self._k('frontends', name, 'extra')
        ))


    @gen.coroutine
    def delete_route(self, routespec):
        name = escape(routespec)
        self.client.delete(os.path.join(self.prefix, 'backends', name), recursive=True)
        self.client.delete(os.path.join(self.prefix, 'frontends', name), recursive=True)
