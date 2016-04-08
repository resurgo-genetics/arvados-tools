import argparse
import logging
import sys

from cat_job_logs import logger, summarizer


class ArgumentParser(argparse.ArgumentParser):
    def __init__(self):
        super(ArgumentParser, self).__init__(
            description='Tail logs output by an Arvados Crunch job')
        src = self.add_mutually_exclusive_group()
        src.add_argument(
            '--job', type=str, metavar='UUID',
            help='Look up the specified job and read its log data from Keep'
            ' (or from the Arvados event log, if the job is still running)')
        self.add_argument(
            '--include-crunchstat-summary', action='store_true',
            help='Include crunchstat-summary logs')
        self.add_argument(
            '--verbose', '-v', action='count', default=0,
            help='Log more information (once for progress, twice for debug)')


class Command(object):
    def __init__(self, args):
        self.args = args
        logger.setLevel(logging.WARNING - 10 * args.verbose)

    def run(self):
        kwargs = {
            'include_crunchstat_summary': self.args.include_crunchstat_summary,
        }
        if self.args.job:
            self.summer = summarizer.JobSummarizer(self.args.job, **kwargs)
        else:
            self.summer = summarizer.Summarizer(sys.stdin, **kwargs)
        return self.summer.run()
