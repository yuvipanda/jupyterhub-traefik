from escapism import escape, unescape
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
    def add_route(self, routespec, backend, data):
        if routespec.startswith('/'):
            # url only spec
            host = None
            url_prefix = routespec
        else:
            host, url_prefix = routespec.split('/', 1)

        if data is None:
            data = {}
        data.update({'jupyterhub-route': True})

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
    def get_all_routes(self):
        routes = {}
        items = self.client.read(self.prefix, recursive=True)
        for item in items.children:
            key = item.key[len(self.prefix):]
            if key.startswith("/backends"):
                routespec = unescape(key.split("/")[1], escape_char='-')
                target = item.value

                if routespec not in routes:
                    routes[routespec] = {}
                routes[routespec].update({
                    'routespec': routespec,
                    'target': target
                })
            elif key.startswith("/frontends"):
                parts = key.split("/")
                if parts[-1] == 'extra':
                    routespec = unescape(parts[1], escape_char='-')
                    if routespec not in routes:
                        routes[routespec] = {}
                    routes[routespec].update({
                        'routespec': routespec,
                        'data': json.loads(item.value)
                    })
            else:
                continue
        return {k: v for k, v in routes.items if v['data'].get('jupyterhub-route', False)}

    @gen.coroutine
    def delete_route(self, routespec):
        name = escape(routespec, escape_char='-')
        self.client.delete(os.path.join(self.prefix, 'backends', name), recursive=True)
        self.client.delete(os.path.join(self.prefix, 'frontends', name), recursive=True)
