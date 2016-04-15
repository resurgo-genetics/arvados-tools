from __future__ import print_function

import arvados
import collections
import tail_job_logs.reader
import datetime
import functools
import itertools
import math
import re
import sys
import threading

from arvados.api import OrderedJsonModel
from tail_job_logs import logger


# Workaround datetime.datetime.strptime() thread-safety bug by calling
# it once before starting threads.  https://bugs.python.org/issue7980
datetime.datetime.strptime('1999-12-31_23:59:59', '%Y-%m-%d_%H:%M:%S')


class Task(object):
    def __init__(self):
        self.series = collections.defaultdict(list)


class Summarizer(object):
    def __init__(self, logdata, label=None, include_crunchstat_summary=False,
        follow=False, task=None, ignore_regex=None):
        self._logdata = logdata

        self.label = label
        self._include_crunchstat_summary = include_crunchstat_summary
        self._task_to_print = task
        self._ignore_regex = ignore_regex

        self.seq_to_uuid = {}
        self.tasks = collections.defaultdict(Task)
        self.follow = False

        # We won't bother recommending new runtime constraints if the
        # constraints given when running the job are known to us and
        # are already suitable.  If applicable, the subclass
        # constructor will overwrite this with something useful.
        self.existing_constraints = {}

        logger.debug("%s: logdata %s", self.label, logdata)

    def run(self):
        logger.debug("%s: parsing logdata %s", self.label, self._logdata)
        for line in self._logdata:
            m = re.search(r'^\S+ \S+ \d+ (?P<seq>\d+) job_task (?P<task_uuid>\S+)$', line)
            if m:
                seq = int(m.group('seq'))
                uuid = m.group('task_uuid')
                self.seq_to_uuid[seq] = uuid
                logger.debug('%s: seq %d is task %s', self.label, seq, uuid)
                continue

            m = re.search(r'^\S+ \S+ \d+ (?P<seq>\d+) (success in|failure \(#., permanent\) after) (?P<elapsed>\d+) seconds', line)
            if m:
                task_id = self.seq_to_uuid[int(m.group('seq'))]
                continue

            m = re.search(r'^\S+ \S+ \d+ (?P<seq>\d+) stderr Queued job (?P<uuid>\S+)$', line)
            if m:
                uuid = m.group('uuid')
                logger.debug('%s: follow %s', self.label, uuid)
                child_summarizer = JobSummarizer(uuid)
                child_summarizer.tasks = self.tasks
                child_summarizer.run()
                logger.debug('%s: done %s', self.label, uuid)
                continue

            m = re.search(r'^(?P<timestamp>[^\s.]+)(\.\d+)? (?P<job_uuid>\S+) \d+ (?P<seq>\d+) stderr crunchstat: (?P<category>\S+) (?P<current>.*?)( -- interval (?P<interval>.*))?\n', line)
            if m and not self._include_crunchstat_summary:
                continue

            m = re.search(r'^(?P<timestamp>[^\s.]+)(\.\d+)? (?P<job_uuid>\S+) \d+ (?P<seq>\d+) stderr (?P<log_entry>.*)\n', line)
            if not m:
                #logger.debug("Could not parse line: %s", line)
                continue

            if self.label is None:
                self.label = m.group('job_uuid')
                logger.debug('%s: using job uuid as label', self.label)

            if self._ignore_regex is not None:
                inner_m = re.search(self._ignore_regex, m.group('log_entry'))
                if inner_m:
                    continue

            task_id = self.seq_to_uuid[int(m.group('seq'))]
            task = self.tasks[task_id]
            if self._task_to_print == None or self._task_to_print == m.group('seq'):
                logger.info('[%s] %s', m.group('seq'), m.group('log_entry'))

        logger.debug('%s: done parsing', self.label)


class CollectionSummarizer(Summarizer):
    def __init__(self, collection_id, **kwargs):
        super(CollectionSummarizer, self).__init__(
            tail_job_logs.reader.CollectionReader(collection_id), **kwargs)
        self.label = collection_id


class JobSummarizer(Summarizer):
    def __init__(self, job, **kwargs):
        arv = arvados.api('v1')
        if isinstance(job, basestring):
            self.job = arv.jobs().get(uuid=job).execute()
        else:
            self.job = job
        rdr = None
        if self.job.get('log'):
            try:
                rdr = tail_job_logs.reader.CollectionReader(self.job['log'])
            except arvados.errors.NotFoundError as e:
                logger.warning("Trying event logs after failing to read "
                               "log collection %s: %s", self.job['log'], e)
            else:
                label = self.job['uuid']
        if rdr is None:
            rdr = tail_job_logs.reader.LiveLogReader(self.job['uuid'], kwargs['follow'])
            label = self.job['uuid'] + ' (partial)'
        super(JobSummarizer, self).__init__(rdr, **kwargs)
        self.label = label
