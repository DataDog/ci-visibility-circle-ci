#!/usr/bin/env python
import argparse
import logging
import os
import sys
from concurrent import futures
from itertools import product

import requests
from requests.adapters import HTTPAdapter, Retry


logger = logging.getLogger(__name__)


CIRCLE_CI_API_HOST = os.getenv('CIRCLE_CI_API_HOST', 'circleci.com')
CIRCLE_CI_API_ROOT = 'https://' + CIRCLE_CI_API_HOST
_MAX_RETRIES = Retry(total=5, backoff_factor=0.1)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Install service hooks for Datadog CI Visibility on your Circle CI organization')

    def validate_api_key(name):
        if len(name) < 32:
            raise ValueError('Datadog API Key must be at least 32 characters long')
        return name

    dd_args = parser.add_argument_group('Datadog')
    dd_args.add_argument('--dd-api-key', type=validate_api_key, help='Datadog API Key')
    dd_args.add_argument('--dd-site', help='Datadog Site (default: datadoghq.com)')

    cci_args = parser.add_argument_group('Circle CI')
    cci_args.add_argument('-t', '--circle-token', help='Circle CI personal API token')

    parser.add_argument('--uninstall', action='store_true', help='Uninstall ALL Datadog service hooks')
    parser.add_argument('--threads', type=int, default=1, help='Number of threads for concurrency on the Circle CI API (default: 1)')
    parser.add_argument('--log-level', default='INFO', help='Logging level (default: INFO)')

    parser.set_defaults(
        dd_api_key=os.getenv('DD_API_KEY'),
        dd_site=os.getenv('DD_SITE', 'datadoghq.com'),
        circle_token=os.getenv('CIRCLE_CI_TOKEN'),
    )

    args = parser.parse_args()

    if not args.dd_api_key and not args.uninstall:
        parser.error('the following arguments are required to install webhooks: --dd-api-key')
    if not args.circle_token:
        parser.error('the following arguments are required: -t/--circle-token')
    return args


def create_http_session(auth):
    _adapter = HTTPAdapter(
        max_retries=_MAX_RETRIES, pool_maxsize=5, pool_block=True
    )
    session = requests.Session()
    session.mount(CIRCLE_CI_API_ROOT, _adapter)
    session.auth = auth
    session.headers.update({
        'Accept': 'application/json;api-version=7.0'
    })
    return session

class CircleCIClient:

    def __init__(self, session, dd_intake_url):
        self.session = session
        self.dd_intake_url = dd_intake_url

    def list_followed_projects(self):
        response = self.session.get(CIRCLE_CI_API_ROOT + '/api/v1.1/projects')
        response.raise_for_status()
        return response.json()

    def get_project_id(self, project_slug):
        response = self.session.get(CIRCLE_CI_API_ROOT + f'/api/v2/project/{project_slug}')
        response.raise_for_status()
        data = response.json()
        return data['id']

    def get_project_slug(self, project_v1):
        vcs_type = project_v1['vcs_type']
        vcs_url_parts = project_v1['vcs_url'].split('/')
        org_and_repo = '/'.join(vcs_url_parts[-2:])
        return f'{vcs_type}/{org_and_repo}'

    def list_webhooks(self, project_id, next_page_token=None):
        params = {
            'scope-id': project_id,
            'scope-type': 'project'
        }
        if next_page_token:
            params['page-token'] = next_page_token

        response = self.session.get(CIRCLE_CI_API_ROOT + '/api/v2/webhook', params=params)
        response.raise_for_status()
        data = response.json()

        webhooks = data['items']

        next_page_token = data.get('continuation_token')
        if next_page_token:
            webhooks += self.list_webhooks(project_id, next_page_token)

        return webhooks

    def create_webhook(self, project_id):
        params = {
            'name': 'DataDog',
            'events': ['workflow-completed', 'job-completed'],
            'url': self.dd_intake_url,
            'verify-tls': True,
            'signing-secret': '',
            'scope': {
                'id': project_id,
                'type': 'project'
            }
        }
        response = self.session.post(CIRCLE_CI_API_ROOT + '/api/v2/webhook', json=params)
        response.raise_for_status()

    def delete_webhook(self, webhook_id):
        response = self.session.delete(CIRCLE_CI_API_ROOT + f'/api/v2/webhook/{webhook_id}')
        response.raise_for_status()
        return response.json()



if __name__ == '__main__':
    args = parse_args()

    dd_intake_url_path = f'https://webhook-intake.{args.dd_site}/api/v2/webhook/'
    dd_intake_url = f'{dd_intake_url_path}?dd-api-key={args.dd_api_key}'

    logging.basicConfig(
        level=args.log_level,
        format='[%(levelname)s - %(asctime)s - %(threadName)s]:  %(message)s',
        handlers=[logging.StreamHandler(sys.stderr)],
    )
    session = create_http_session((args.circle_token, ''))
    client = CircleCIClient(session, dd_intake_url)

    action = 'Installing' if not args.uninstall else 'Uninstalling'
    logger.info('%s hooks for all followed projects', action)

    projects = client.list_followed_projects()
    def contains_dd_webook(webhooks):
        for webhook in webhooks:
            if webhook['url'] == dd_intake_url:
                return True

    def handle_project(project):
        project_slug = client.get_project_slug(project)
        project_id = client.get_project_id(project_slug)
        webhooks = client.list_webhooks(project_id)
        if args.uninstall:
            for webhook in webhooks:
                if dd_intake_url_path in webhook['url']:
                    msg = client.delete_webhook(webhook['id'])
                    logger.debug('Hook %s for project id %s deleted (response from Circle CI API: %s)', webhook['name'], project_id, msg)
        else:
            if not contains_dd_webook(webhooks):
                client.create_webhook(project_id)
                logger.debug('Hook for project id %s created', project_id)
        logger.info('hook installed for %s (%s)', project_slug, project_id)

    with futures.ThreadPoolExecutor(max_workers=args.threads) as executor:
        list(executor.map(lambda p: handle_project(p), projects))

    logger.info('Finished!')
