# -*- coding: utf-8 -*-
# _http.py
# Copyright (C) 2017 LEAP
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
"""
A twisted-based, TLS-pinned, token-authenticated HTTP client.
"""
import base64

from twisted.internet import reactor
from twisted.web.iweb import IAgent
from twisted.web.client import Agent
from twisted.web.http_headers import Headers

from treq.client import HTTPClient as _HTTPClient

from zope.interface import implementer

from leap.common.certs import get_compatible_ssl_context_factory


__all__ = ['HTTPClient', 'PinnedTokenAgent']


class HTTPClient(object):

    def __init__(self, uuid, token, cert_file):
        self._agent = PinnedTokenAgent(uuid, token, cert_file)
        self._client = _HTTPClient(self._agent)

    def set_token(self, token):
        self._agent.set_token(token)

    def head(self, url, **kwargs):
        return self._client.head(url, **kwargs)

    def get(self, url, headers=None, **kwargs):
        return self._client.get(url, headers=headers, **kwargs)

    def post(self, url, data=None, **kwargs):
        return self._client.post(url, data=data, **kwargs)

    def put(self, url, data=None, **kwargs):
        return self._client.put(url, data=data, **kwargs)

    def patch(self, url, data=None, **kwargs):
        return self._client.patch(url, data=data, **kwargs)

    def delete(self, url, **kwargs):
        return self._client.delete(url, **kwargs)

    def request(self, method, url, **kwargs):
        return self._client.request(method, url, **kwargs)


@implementer(IAgent)
class PinnedTokenAgent(Agent):

    def __init__(self, uuid, token, cert_file):
        self._uuid = uuid
        self._token = None
        self._creds = None
        self.set_token(token)
        # pin this agent with the platform TLS certificate
        factory = get_compatible_ssl_context_factory(cert_file)
        Agent.__init__(self, reactor, contextFactory=factory)

    def set_token(self, token):
        self._token = token
        self._creds = self._encoded_creds()

    def _encoded_creds(self):
        creds = '%s:%s' % (self._uuid, self._token)
        encoded = base64.b64encode(creds)
        return 'Token %s' % encoded

    def request(self, method, uri, headers=None, bodyProducer=None):
        # authenticate the request
        if not headers:
            headers = Headers()
        headers.addRawHeader('Authorization', self._creds)
        # perform the authenticated request
        return Agent.request(
            self, method, uri, headers=headers, bodyProducer=bodyProducer)
