# -*- coding: utf-8 -*-
# send.py
# Copyright (C) 2015 LEAP
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
import json
import logging
from twisted.internet import defer
from leap.soledad.client.events import emit
from leap.soledad.client.events import SOLEDAD_SYNC_SEND_STATUS
from leap.soledad.client.http_target.support import RequestBody
logger = logging.getLogger(__name__)


class HTTPDocSender(object):

    @defer.inlineCallbacks
    def _send_docs(self, docs_by_generation, last_known_generation,
                   last_known_trans_id, sync_id):

        if not docs_by_generation:
            defer.returnValue([None, None])

        # add remote replica metadata to the request
        metadata = RequestBody(
            last_known_generation=last_known_generation,
            last_known_trans_id=last_known_trans_id,
            sync_id=sync_id,
            ensure=self._ensure_callback is not None)
        total = len(docs_by_generation)
        entries = yield self._entries_from_docs(metadata, docs_by_generation)
        while len(entries):
            result = yield self._http_request(
                self._url,
                method='POST',
                body=entries.remove(1),
                content_type='application/x-soledad-sync-put')
            idx = total - len(entries)
            if self._defer_encryption:
                self._delete_sent(idx, docs_by_generation)
            _emit_send_status(idx, total)
        response_dict = json.loads(result)[0]
        gen_after_send = response_dict['new_generation']
        trans_id_after_send = response_dict['new_transaction_id']
        defer.returnValue([gen_after_send, trans_id_after_send])

    def _delete_sent(self, idx, docs_by_generation):
        doc = docs_by_generation[idx - 1][0]
        self._sync_enc_pool.delete_encrypted_doc(
            doc.doc_id, doc.rev)

    @defer.inlineCallbacks
    def _entries_from_docs(self, initial_body, docs_by_generation):
        number_of_docs = len(docs_by_generation)
        for idx, (doc, gen, trans_id) in enumerate(docs_by_generation, 1):
            content = yield self._encrypt_doc(doc)
            initial_body.insert_info(
                id=doc.doc_id, rev=doc.rev, content=content, gen=gen,
                trans_id=trans_id, number_of_docs=number_of_docs,
                doc_idx=idx)
        defer.returnValue(initial_body)

    def _encrypt_doc(self, doc):
        d = None
        if doc.is_tombstone():
            d = defer.succeed(None)
        elif not self._defer_encryption:
            # fallback case, for tests
            d = defer.succeed(self._crypto.encrypt_doc(doc))
        else:

            def _maybe_encrypt_doc_inline(doc_json):
                if doc_json is None:
                    # the document is not marked as tombstone, but we got
                    # nothing from the sync db. As it is not encrypted
                    # yet, we force inline encryption.
                    return self._crypto.encrypt_doc(doc)
                return doc_json

            d = self._sync_enc_pool.get_encrypted_doc(doc.doc_id, doc.rev)
            d.addCallback(_maybe_encrypt_doc_inline)
        return d


def _emit_send_status(idx, total):
    msg = "%d/%d" % (idx, total)
    emit(
        SOLEDAD_SYNC_SEND_STATUS,
        "Soledad sync send status: %s" % msg)
    logger.debug("Sync send status: %s" % msg)
