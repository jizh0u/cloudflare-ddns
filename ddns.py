"""A tool for cloudflare ddns."""
import json
import time
import requests
from absl import app
from absl import flags
from absl import logging

FLAGS = flags.FLAGS

flags.DEFINE_string('config_file', None, 'The filename of the config file.')


class CloudflareUpdater:
    def __init__(
        self,
        api_token: str,
        zone_id: str,
        domain: str,
        proxied: bool) -> None:

        self.api_token = api_token
        self.zone_id = zone_id
        self.domain = domain
        self.proxied = proxied


    @staticmethod
    def _get_ipv4_addr() -> str:
        responses = requests.get("https://1.1.1.1/cdn-cgi/trace", timeout=30).text.split("\n")
        responses.pop()
        ipv4_addr = dict(line.split("=") for line in responses)["ip"]

        logging.info("Your current IPV4 address is %s.", ipv4_addr)
        return ipv4_addr


    def _get_headers(self) -> dict:
        return {
            'Authorization': 'Bearer ' + self.api_token,
            'Content-Type': 'application/json'
        }


    def _base_api_url(self) -> str:
        return 'https://api.cloudflare.com/client/v4/' + 'zones/' + self.zone_id


    def _cf_api(self, method: str, url: str, data: dict):
        return requests.request(method=method, url=url, headers=self._get_headers(), json=data, timeout=30)


    def _commit_dns(self, ipv4_addr: str) -> None:
        # Lists all related IPV4 DNS records under the given zone id.
        response = self._cf_api('GET', self._base_api_url() + '/dns_records?type=A', {})

        if not response.ok or not response.json()['success']:
            raise RuntimeError('Error to list related DNS records under the given zone id: ' + response.text)

        dns_records = response.json()['result']

        need_create = True
        need_update = False
        existing_record_id = ''
        for record in dns_records:
            if record['name'] == self.domain:
                existing_record_id = record['id']
                need_create = False
                
                if record['content'] != ipv4_addr or record['proxied'] != self.proxied:
                    need_update = True

        new_record = {
            'type': 'A',
            'name': self.domain,
            'content': ipv4_addr,
            'ttl': 1, # auto
            'proxied': self.proxied
        }

        if need_update:
            logging.info('Update DNS record for %s to %s...', self.domain, ipv4_addr)
            response = self._cf_api('PUT', self._base_api_url() + '/dns_records/' + existing_record_id, new_record)

            if response.ok and response.json()['success']:
                logging.info('Update successfully!')
            else:
                logging.warn('Failed to update: %s', response.text)
                logging.warn(response.request.headers)

        else:
            logging.info('Skip updating because the existing DNS record is up-to-date...')

        if need_create:
            logging.info('Create DNS record for %s to %s...', self.domain, ipv4_addr)
            response = self._cf_api('POST', self._base_api_url() + '/dns_records', new_record)

            if response.ok and response.json()['success']:
                logging.info('Create successfully!')
            else:
                logging.warn('Failed to create: %s', response.text)


    def update(self) -> None:
        self._commit_dns(self._get_ipv4_addr())


def main(argv):
    del argv

    with open(FLAGS.config_file) as config_file:
        config = json.loads(config_file.read())

    cloudflare_updater = CloudflareUpdater(
        config['api_token'],
        config['zone_id'],
        config['domain'],
        config['proxied'])

    update_interval_mins = config['update_interval_mins']

    if update_interval_mins == 0:
        logging.info('Update DNS...')
        cloudflare_updater.update()
    else:
        logging.info('Update DNS every %d mins...', update_interval_mins)
        while True:
            cloudflare_updater.update()
            time.sleep(update_interval_mins * 60)


if __name__ == '__main__':
    app.run(main)
