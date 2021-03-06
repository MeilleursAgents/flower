from __future__ import absolute_import

from functools import total_ordering
import copy
import logging

try:
    from itertools import imap
except ImportError:
    imap = map

import couchbase.fulltext as FT
from couchbase.bucket import Bucket
from couchbase.cluster import Cluster, PasswordAuthenticator
from couchbase.n1ql import N1QLQuery

from tornado import web

from ..views import BaseHandler
from ..utils.tasks import iter_tasks, get_task_by_id, as_dict

logger = logging.getLogger(__name__)


class WorkerWrapper:
    def __init__(self, hostname):
        self.hostname


class TaskWrapperFromCB:
    """
        Dirty wrapper to use couchbase result within flower views
    """
    def __init__(self, values):
        self.values = values

    def __getattr__(self, key):
        val = self.values.get(key)
        if key == 'worker':
            return WorkerWrapper(self.values['worker'])
        return val

    @property
    def _fields(self):
        return self.values.keys()


class TaskView(BaseHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.application.options.state_backend_user:
            cluster = Cluster(self.application.options.state_backend_server)
            authenticator = PasswordAuthenticator(
                self.application.options.state_backend_user,
                self.application.options.state_backend_password,
            )
            cluster.authenticate(authenticator)
            self.bucket = cluster.open_bucket(self.application.options.state_backend_bucket_name)
        else:
            self.bucket = Bucket('{}/{}'.format(
                self.application.options.state_backend_server,
                self.application.options.state_backend_bucket_name
            ))

    @web.authenticated
    def get(self, task_id):
        # task = get_task_by_id(self.application.events, task_id)
        task = self.bucket.get(task_id).value
        task = TaskWrapperFromCB(task)

        if task is None:
            raise web.HTTPError(404, "Unknown task '%s'" % task_id)

        self.render("task.html", task=task)


@total_ordering
class Comparable(object):
    """
    Compare two objects, one or more of which may be None.  If one of the
    values is None, the other will be deemed greater.
    """

    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return self.value == other.value

    def __lt__(self, other):
        try:
            return self.value < other.value
        except TypeError:
            return self.value is None


class TasksDataTable(BaseHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.application.options.state_backend_user:
            cluster = Cluster(self.application.options.state_backend_server)
            authenticator = PasswordAuthenticator(
                self.application.options.state_backend_user,
                self.application.options.state_backend_password,
            )
            cluster.authenticate(authenticator)
            self.bucket = cluster.open_bucket(self.application.options.state_backend_bucket_name)
        else:
            self.bucket = Bucket('{}/{}'.format(
                self.application.options.state_backend_server,
                self.application.options.state_backend_bucket_name
            ))

    @web.authenticated
    def get(self):
        app = self.application
        draw = self.get_argument('draw', type=int)
        start = self.get_argument('start', type=int)
        length = self.get_argument('length', type=int)
        search = self.get_argument('search[value]', type=str)

        column = self.get_argument('order[0][column]', type=int)
        sort_by = self.get_argument('columns[%s][data]' % column, type=str)
        sort_order = self.get_argument('order[0][dir]', type=str) == 'desc'

        def key(item):
            return Comparable(getattr(item[1], sort_by))

        def format_cb_task_dict(task_dict):
            task_dict['args'] = task_dict['args'].__repr__()
            task_dict['kwargs'] = task_dict['kwargs'].__repr__()
            task_dict['args'] = task_dict['args'][:25] + '...' if len(task_dict['args']) > 25 else task_dict['args']
            task_dict['kwargs'] = task_dict['kwargs'][:25] + '...' if len(task_dict['kwargs']) > 25 else task_dict['kwargs']

        q = N1QLQuery('select count(*) AS total_doc from `{bucket_name}`'.format(
            bucket_name=self.application.options.state_backend_bucket_name
        ))
        total_doc_count = [r for r in self.bucket.n1ql_query(q)][0]['total_doc']
        recordsTotal = total_doc_count

        filtered_tasks = []
        if search:
            task_count = len([r['id'] for r in self.bucket.search(self.application.options.state_backend_fts_name, FT.TermQuery(search), limit=length)])
            task_ids = [r['id'] for r in self.bucket.search(self.application.options.state_backend_fts_name, FT.TermQuery(search), limit=length, skip=start)]
            recordsFiltered = task_count
            if task_ids:
                for task_dict in self.bucket.get_multi(task_ids).values():
                    task_dict = task_dict.value
                    format_cb_task_dict(task_dict)
                    filtered_tasks.append(task_dict)
        else:
            q = N1QLQuery('select * from `{bucket_name}` order by failed desc limit {limit} offset {offset}'.format(
                bucket_name=self.application.options.state_backend_bucket_name,
                limit=length,
                offset=start
            ))
            for row in self.bucket.n1ql_query(q):
                task_dict = row[self.application.options.state_backend_bucket_name]
                format_cb_task_dict(task_dict)
                filtered_tasks.append(task_dict)
            recordsFiltered = total_doc_count

        self.write(dict(draw=draw, data=filtered_tasks,
                        recordsTotal=recordsTotal,
                        recordsFiltered=recordsFiltered))

    def format_task(self, args):
        uuid, task = args
        custom_format_task = self.application.options.format_task

        if custom_format_task:
            try:
                task = custom_format_task(copy.copy(task))
            except:
                logger.exception("Failed to format '%s' task", uuid)
        return uuid, task


class TasksView(BaseHandler):
    @web.authenticated
    def get(self):
        app = self.application
        capp = self.application.capp

        time = 'natural-time' if app.options.natural_time else 'time'
        if capp.conf.CELERY_TIMEZONE:
            time += '-' + capp.conf.CELERY_TIMEZONE

        self.render(
            "tasks.html",
            tasks=[],
            columns=app.options.tasks_columns,
            time=time,
        )
