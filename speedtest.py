import subprocess
import json
import requests
import logging
import argparse
import sys

def run_speedtest(server_id):
    LOGGER.info('Executing an internet speed test')
    if server_id:
        server_id_flag = f'--server {server_id}'
    else:
        server_id_flag = ''
    json_results = subprocess.check_output(f'speedtest-cli {server_id_flag} --json', shell=True)
    return parse_results(json_results)

def parse_results(results_json):
    LOGGER.info('Parsing speed test results')
    try:
        parsed_results = json.loads(results_json)
    except json.decoder.JSONDecodeError as e:
        LOGGER.error('Could not parse json')
        LOGGER.error('Ensure speedtest-cli binary is installed and in environment path')
        raise e
    return parsed_results

def check_quality(latency_threshold, download_threshold, upload_threshold, hook_name, hook_key):
    LOGGER.info('Checking speed quality')
    message = 'Internet was unstable'
    post_alert = False
    if LATENCY > latency_threshold:
        post_alert = True
        message = message + f', latency of {LATENCY} is higher than threshold'

    if DOWNLOAD < download_threshold:
        post_alert = True
        message = message + f', download speed of {DOWNLOAD} is lower than threshold'

    if UPLOAD < upload_threshold:
        post_alert = True
        message = message + f', upload speed of {UPLOAD} is lower than threshold'

    message = message + '.'
    LOGGER.info(message)
    if ALERT and post_alert:
        alert_quality(message, hook_name, hook_key)

def alert_quality(alert_message, hook_name, hook_key):
    LOGGER.info('Posting alert to IFTTT notification hook')
    post_data = {'value1': alert_message}
    make_request(hook_name, hook_key, post_data)

def notify_results(hook_name, hook_key):
    LOGGER.info('Posting results to IFTTT notification hook')
    message = f'Speed test completed with latency of {LATENCY}ms, download speed of {DOWNLOAD}mbps and upload speed of {UPLOAD}mbps'
    post_data = {'value1': message}
    make_request(hook_name, hook_key, post_data)

def post_results(hook_name, hook_key):
    LOGGER.info('Posting results to IFTTT Google sheets hook')
    post_data = {'value1': LATENCY, 'value2': DOWNLOAD, 'value3': UPLOAD}
    make_request(hook_name, hook_key, post_data)

def make_request(hook_name, hook_key, post_data):
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(f'https://maker.ifttt.com/trigger/{hook_name}/with/key/{hook_key}',
                          data = json.dumps(post_data),
                          headers = headers,
                          timeout = 10)
        status_code = response.status_code
        response.raise_for_status()
    except requests.HTTPError as http_err:
        LOGGER.error(f'IFTTT webhook trigger for {hook_name} failed HTTP error occurred: {http_err}')
    except requests.ConnectTimeout:
        LOGGER.error(f'IFTTT webhook trigger for {hook_name} failed request timed out')
    except Exception as err:
        LOGGER.error(f'IFTTT webhook trigger for {hook_name} failed other error occurred: {err}')
        raise err
    else:
        LOGGER.info(f'IFTTT webhook trigger for {hook_name} successful with status code {status_code}')

if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stdout, level=logging.INFO)
    LOGGER = logging.getLogger()
    LOGGER.info('Starting')

    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--result_hook_name", help="IFTTT maker event result logger hook name")
    parser.add_argument("-a", "--alert_hook_name", help="IFTTT maker event alerting hook name")
    parser.add_argument("-k", "--hook_secret_key", help="IFTTT maker event secret key")
    parser.add_argument("-u", "--upload_threshold", help="Alert if upload below threshold", type=int)
    parser.add_argument("-d", "--download_threshold", help="Alert if download below threshold", type=int)
    parser.add_argument("-l", "--latency_threshold", help="Alert if latency above threshold", type=int)
    parser.add_argument("-s", "--speedtest_server_id", help="Preferred speedtest.net server id")
    parser.add_argument("-n", "--notify", help="Notify IFTTT on current results")
    args = parser.parse_args()

    results = run_speedtest(args.speedtest_server_id)

    DOWNLOAD = round((results['download'] / 1024 / 1024), 2)
    UPLOAD = round((results['upload'] / 1024 / 1024), 2)
    LATENCY = round((results['server']['latency']), 2)

    LOGGER.info(f'Download: {DOWNLOAD}, Upload: {UPLOAD}, Latency: {LATENCY}')

    if args.alert_hook_name and args.hook_secret_key:
        ALERT = True
    else:
        ALERT = False

    if args.result_hook_name and args.hook_secret_key:
        post_results(args.result_hook_name, args.hook_secret_key)

    if args.upload_threshold and args.download_threshold and args.latency_threshold:
        check_quality(args.latency_threshold, args.download_threshold, args.upload_threshold, args.alert_hook_name, args.hook_secret_key)

    if args.notify and ALERT:
        notify_results(args.alert_hook_name, args.hook_secret_key)
